from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.utils.enums import UserRole


class UserSignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password must be at least 8 characters.",
    )
    full_name: str = Field(..., min_length=2, max_length=255)
    role: UserRole | None = Field(default=UserRole.PATIENT, description="Defaults to PATIENT")


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserResponse
