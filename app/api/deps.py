import jwt
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token, verify_webhook_signature
from app.models.user import User
from app.utils.enums import UserRole
from app.utils.exceptions import (
    AuthenticationError,
    AuthorizationError,
    WebhookVerificationError,
)

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    auth_credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Authenticate request via JWT Bearer token.
    Decodes subject claim and returns active User entity.
    """
    if not auth_credentials:
        raise AuthenticationError("Authentication token is missing.")

    token = auth_credentials.credentials
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as err:
        raise AuthenticationError("Authentication token has expired.") from err
    except jwt.InvalidTokenError as err:
        raise AuthenticationError("Invalid authentication token.") from err

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("Token payload missing subject.")

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError) as err:
        raise AuthenticationError("Token subject is malformed.") from err

    user = db.get(User, user_id)
    if not user:
        raise AuthenticationError("User associated with this token no longer exists.")

    return user


def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Authorize that the authenticated user possesses the ADMIN role."""
    if current_user.role != UserRole.ADMIN.value:
        raise AuthorizationError("Administrator access required for this action.")
    return current_user


async def verify_simulated_webhook_signature(
    request: Request,
    x_webhook_signature: str | None = Header(None, alias="X-Webhook-Signature"),
    x_webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
) -> None:
    """
    Simulated provider webhook authentication:
    Allows either:
    1. Direct secret header match (X-Webhook-Secret == settings.WEBHOOK_SECRET)
    2. HMAC-SHA256 signature verification over raw request body (X-Webhook-Signature)
    If neither is supplied and in production, rejects with 401.
    If dev mode and no header supplied, logs warning or permits for easy testing if configured.
    """
    # If shared secret header is present and valid
    if x_webhook_secret and x_webhook_secret == settings.WEBHOOK_SECRET:
        return

    # If HMAC signature header is present
    if x_webhook_signature:
        body = await request.body()
        if verify_webhook_signature(body, x_webhook_signature):
            return
        raise WebhookVerificationError("Invalid webhook HMAC signature.")

    # In production, require authentication headers
    if settings.ENVIRONMENT == "production":
        raise WebhookVerificationError("Webhook authentication header is required in production.")
