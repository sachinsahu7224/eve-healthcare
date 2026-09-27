from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.test import DiagnosticTestWithPrice


class DiagnosticCentreBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    location: str = Field(..., min_length=2, max_length=255)
    is_active: bool = True


class DiagnosticCentreCreate(DiagnosticCentreBase):
    pass


class DiagnosticCentreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    location: str | None = Field(default=None, min_length=2, max_length=255)
    is_active: bool | None = None


class DiagnosticCentreResponse(DiagnosticCentreBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiagnosticCentreDetailResponse(DiagnosticCentreResponse):
    tests: list[DiagnosticTestWithPrice] = []


class CentreTestAssignRequest(BaseModel):
    test_id: int
    price: Decimal = Field(..., gt=Decimal("0.00"), description="Test price must be strictly positive.")


class CentreTestAssignResponse(BaseModel):
    centre_id: int
    test_id: int
    price: Decimal
    message: str = "Test successfully configured for diagnostic centre."
