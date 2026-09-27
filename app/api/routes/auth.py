from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserResponse,
    UserSignUpRequest,
)
from app.utils.enums import UserRole
from app.utils.exceptions import (
    AuthenticationError,
    EntityAlreadyExistsError,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def signup(request: UserSignUpRequest, db: Session = Depends(get_db)) -> User:
    """Register a new user with email, full name, and secure Argon2-hashed password."""
    # Check if user already exists
    existing = db.scalar(select(User).where(User.email == request.email))
    if existing:
        raise EntityAlreadyExistsError("User", "email", request.email)

    role_val = request.role.value if request.role else UserRole.PATIENT.value

    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
        role=role_val,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT access token",
)
def login(request: UserLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate credentials and generate a signed JWT bearer token."""
    user = db.scalar(select(User).where(User.email == request.email))
    if not user or not verify_password(request.password, user.password_hash):
        raise AuthenticationError("Invalid email or password.")

    token = create_access_token(subject=user.id, role=user.role)
    expires_in_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=expires_in_seconds,
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return profile details for the currently authenticated user identity."""
    return current_user
