from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.utils.enums import WebhookEventType


class PaymentWebhookPayload(BaseModel):
    event_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique event identifier from payment provider",
    )
    event_type: WebhookEventType = Field(..., description="payment.succeeded or payment.failed")
    provider_payment_id: str = Field(..., min_length=1, max_length=255, description="Provider payment reference ID")
    booking_id: int = Field(..., gt=0, description="Associated Booking ID")
    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Payment amount")


class PaymentWebhookResponse(BaseModel):
    status: str = Field(..., description="'processed' or 'already_processed'")
    event_id: str
    message: str
    booking_status: str | None = None
    payment_status: str | None = None

    model_config = ConfigDict(from_attributes=True)
