from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.utils.enums import PaymentStatus


class SimulatePaymentRequest(BaseModel):
    booking_id: int = Field(..., gt=0, description="Target Booking ID to pay for")
    simulate_status: PaymentStatus = Field(
        default=PaymentStatus.SUCCESS,
        description="Simulated outcome: SUCCESS or FAILED",
    )
    provider_payment_id: str | None = Field(
        default=None,
        description="Optional custom provider transaction ID for simulation testing",
    )


class PaymentResponse(BaseModel):
    id: int
    booking_id: int
    provider_payment_id: str
    amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
