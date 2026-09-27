from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.webhook_event import PaymentWebhookEvent


class PaymentRepository:
    """Repository handling database operations for Payments and Webhook Events."""

    @staticmethod
    def get_by_id(db: Session, payment_id: int) -> Payment | None:
        return db.get(Payment, payment_id)

    @staticmethod
    def get_by_provider_payment_id(db: Session, provider_payment_id: str) -> Payment | None:
        stmt = select(Payment).where(Payment.provider_payment_id == provider_payment_id)
        return db.scalar(stmt)

    @staticmethod
    def list_by_booking_id(db: Session, booking_id: int) -> list[Payment]:
        stmt = select(Payment).where(Payment.booking_id == booking_id).order_by(Payment.created_at.desc())
        return list(db.scalars(stmt).all())

    @staticmethod
    def create(db: Session, payment: Payment) -> Payment:
        db.add(payment)
        db.flush()
        return payment

    # Webhook Event Persistence
    @staticmethod
    def get_webhook_event_by_id(db: Session, event_id: str) -> PaymentWebhookEvent | None:
        stmt = select(PaymentWebhookEvent).where(PaymentWebhookEvent.event_id == event_id)
        return db.scalar(stmt)

    @staticmethod
    def record_webhook_event(db: Session, webhook_event: PaymentWebhookEvent) -> PaymentWebhookEvent:
        db.add(webhook_event)
        db.flush()
        return webhook_event
