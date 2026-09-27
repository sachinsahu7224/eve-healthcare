from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DiagnosticTestBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True


class DiagnosticTestCreate(DiagnosticTestBase):
    pass


class DiagnosticTestUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class DiagnosticTestResponse(DiagnosticTestBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiagnosticTestWithPrice(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    price: Decimal

    model_config = ConfigDict(from_attributes=True)
