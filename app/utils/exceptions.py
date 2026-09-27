from typing import Any


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, status_code: int = 400, details: Any | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class EntityNotFoundError(AppException):
    def __init__(self, entity_name: str, identifier: Any):
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' was not found.",
            status_code=404,
        )


class EntityAlreadyExistsError(AppException):
    def __init__(self, entity_name: str, field: str, value: Any):
        super().__init__(
            message=f"{entity_name} with {field} '{value}' already exists.",
            status_code=409,
        )


class InvalidStateTransitionError(AppException):
    def __init__(self, current_status: str, target_status: str, reason: str | None = None):
        detail_msg = f"Cannot transition from {current_status} to {target_status}."
        if reason:
            detail_msg += f" Reason: {reason}"
        super().__init__(
            message=detail_msg,
            status_code=400,
        )


class AuthenticationError(AppException):
    def __init__(self, message: str = "Could not validate credentials."):
        super().__init__(message=message, status_code=401)


class AuthorizationError(AppException):
    def __init__(self, message: str = "You do not have permission to perform this action."):
        super().__init__(message=message, status_code=403)


class BusinessRuleViolationError(AppException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=400)


class WebhookVerificationError(AppException):
    def __init__(self, message: str = "Invalid webhook signature or authentication."):
        super().__init__(message=message, status_code=401)
