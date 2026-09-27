import uuid

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.user import User
from app.repositories.booking_repository import BookingRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment import SimulatePaymentRequest
from app.services.booking_service import BookingService
from app.utils.enums import BookingStatus, PaymentStatus, UserRole
from app.utils.exceptions import (
    AuthorizationError,
    BusinessRuleViolationError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
)


class PaymentService:
    """Service handling simulated payments with transactional consistency."""

    @staticmethod
    def simulate_payment(db: Session, request: SimulatePaymentRequest, current_user: User) -> Payment:
        """
        Simulate processing a payment for a booking.
        Updates both Payment and Booking atomically within a single database transaction.
        """
        # 1. Fetch booking
        booking = BookingRepository.get_by_id(db, request.booking_id)
        if not booking:
            raise EntityNotFoundError("Booking", request.booking_id)

        # 2. Check authorization: only the booking owner or an admin can initiate payment
        if current_user.role != UserRole.ADMIN.value and booking.user_id != current_user.id:
            raise AuthorizationError("You do not have permission to pay for this booking.")

        # 3. Ensure booking is eligible for payment (must be PENDING)
        if booking.status != BookingStatus.PENDING.value:
            raise BusinessRuleViolationError(
                f"Cannot process payment for booking with status '{booking.status}'. Only PENDING bookings can be paid."
            )

        # 4. Generate or validate provider payment identifier
        provider_payment_id = request.provider_payment_id or f"pay_sim_{uuid.uuid4().hex[:16]}"
        existing_payment = PaymentRepository.get_by_provider_payment_id(db, provider_payment_id)
        if existing_payment:
            raise EntityAlreadyExistsError("Payment", "provider_payment_id", provider_payment_id)

        # 5. Determine target booking status based on payment outcome
        if request.simulate_status == PaymentStatus.SUCCESS:
            target_booking_status = BookingStatus.CONFIRMED.value
        else:
            target_booking_status = BookingStatus.FAILED.value

        # 6. Apply state transition to booking
        BookingService.apply_transition(
            booking=booking,
            target_status=target_booking_status,
            reason=f"Payment simulation completed with status: {request.simulate_status.value}",
        )

        # 7. Create Payment record
        payment = Payment(
            booking_id=booking.id,
            provider_payment_id=provider_payment_id,
            amount=booking.amount,
            status=request.simulate_status.value,
        )

        PaymentRepository.create(db, payment)
        BookingRepository.update(db, booking)

        # 8. Commit atomic transaction
        db.commit()
        db.refresh(payment)
        return payment
