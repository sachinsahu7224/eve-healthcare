import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.webhook_event import PaymentWebhookEvent
from app.repositories.booking_repository import BookingRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.webhook import PaymentWebhookPayload, PaymentWebhookResponse
from app.services.booking_service import BookingService
from app.utils.enums import BookingStatus, PaymentStatus, WebhookEventType
from app.utils.exceptions import BusinessRuleViolationError, EntityNotFoundError


class WebhookService:
    """Service handling payment webhooks with guaranteed database-level idempotency."""

    @staticmethod
    def process_payment_webhook(
        db: Session, payload: PaymentWebhookPayload, raw_payload_str: str | None = None
    ) -> PaymentWebhookResponse:
        """
        Process an incoming payment webhook event idempotently:
        1. Check if event_id already exists in the database.
        2. If already processed, return immediate 200 OK idempotent response.
        3. Otherwise, begin transaction, record event, update payment & booking state, and commit.
        4. Guard against concurrent race conditions via database UNIQUE constraint on event_id.
        """
        # Step 1 & 2: Pre-check if event has already been recorded
        existing_event = PaymentRepository.get_webhook_event_by_id(db, payload.event_id)
        if existing_event:
            # Event was already handled; fetch current booking and payment status for informational response
            booking = BookingRepository.get_by_id(db, payload.booking_id)
            payment = PaymentRepository.get_by_provider_payment_id(db, payload.provider_payment_id)
            return PaymentWebhookResponse(
                status="already_processed",
                event_id=payload.event_id,
                message="Webhook event was previously processed (idempotent response).",
                booking_status=booking.status if booking else None,
                payment_status=payment.status if payment else None,
            )

        # Step 3: Validate related business entities exist prior to writing
        booking = BookingRepository.get_by_id(db, payload.booking_id)
        if not booking:
            raise EntityNotFoundError("Booking", payload.booking_id)

        # Step 4: Map event_type to domain statuses
        if payload.event_type == WebhookEventType.PAYMENT_SUCCEEDED:
            target_payment_status = PaymentStatus.SUCCESS.value
            target_booking_status = BookingStatus.CONFIRMED.value
        elif payload.event_type == WebhookEventType.PAYMENT_FAILED:
            target_payment_status = PaymentStatus.FAILED.value
            target_booking_status = BookingStatus.FAILED.value
        else:
            raise BusinessRuleViolationError(f"Unsupported webhook event type: {payload.event_type}")

        # Step 5: Execute atomic database transaction
        try:
            # Record webhook event (enforcing UNIQUE constraint on event_id)
            webhook_record = PaymentWebhookEvent(
                event_id=payload.event_id,
                event_type=payload.event_type.value,
                payload=raw_payload_str or json.dumps(payload.model_dump(mode="json")),
            )
            db.add(webhook_record)

            # Locate or create payment record
            payment = PaymentRepository.get_by_provider_payment_id(db, payload.provider_payment_id)
            if not payment:
                payment = Payment(
                    booking_id=booking.id,
                    provider_payment_id=payload.provider_payment_id,
                    amount=payload.amount,
                    status=target_payment_status,
                )
                db.add(payment)
            else:
                payment.status = target_payment_status

            # Apply state transition to booking (centralized state machine)
            BookingService.apply_transition(
                booking=booking,
                target_status=target_booking_status,
                reason=f"Webhook event '{payload.event_id}' processed ({payload.event_type.value})",
            )
            db.add(booking)

            # Commit the transaction
            db.commit()

            return PaymentWebhookResponse(
                status="processed",
                event_id=payload.event_id,
                message="Webhook processed successfully.",
                booking_status=booking.status,
                payment_status=payment.status,
            )

        except IntegrityError:
            # Concurrent race condition: another concurrent worker committed the same event_id first
            db.rollback()
            refreshed_booking = BookingRepository.get_by_id(db, payload.booking_id)
            refreshed_payment = PaymentRepository.get_by_provider_payment_id(db, payload.provider_payment_id)
            return PaymentWebhookResponse(
                status="already_processed",
                event_id=payload.event_id,
                message="Webhook event was processed concurrently (idempotent response).",
                booking_status=refreshed_booking.status if refreshed_booking else None,
                payment_status=refreshed_payment.status if refreshed_payment else None,
            )
