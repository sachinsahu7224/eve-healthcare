from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BookingCreateRequest(BaseModel):
    centre_id: int = Field(..., gt=0, description="Diagnostic Centre ID")
    test_id: int = Field(..., gt=0, description="Diagnostic Test ID")
    appointment_at: datetime = Field(..., description="Desired appointment datetime (must be in the future)")

    @field_validator("appointment_at")
    @classmethod
    def validate_future_datetime(cls, v: datetime) -> datetime:
        # Normalize to UTC or check against current time
        now = datetime.now(timezone.utc)
        target = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if target <= now:
            raise ValueError("Appointment date and time must be in the future.")
        return target


class BookingResponse(BaseModel):
    id: int
    user_id: int
    centre_id: int
    centre_name: str | None = None
    test_id: int
    test_name: str | None = None
    appointment_at: datetime
    amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingCancelResponse(BaseModel):
    id: int
    status: str
    message: str = "Booking cancelled successfully."
