from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.models.user import User
from app.repositories.booking_repository import BookingRepository
from app.schemas.booking import BookingCreateRequest
from app.utils.enums import BookingStatus, UserRole
from app.utils.exceptions import (
    AuthorizationError,
    BusinessRuleViolationError,
    EntityNotFoundError,
    InvalidStateTransitionError,
)

# Centralized Booking State Transition Rules
VALID_TRANSITIONS = {
    BookingStatus.PENDING.value: {
        BookingStatus.CONFIRMED.value,
        BookingStatus.FAILED.value,
        BookingStatus.CANCELLED.value,
    },
    BookingStatus.CONFIRMED.value: set(),
    BookingStatus.FAILED.value: set(),
    BookingStatus.CANCELLED.value: set(),
}


class BookingService:
    """Service encapsulating all booking workflows, pricing snapshots, and state transitions."""

    @staticmethod
    def validate_transition(
        current_status: str,
        target_status: str,
        reason: str | None = None,
        allow_same_state: bool = False,
    ) -> None:
        """Validate if a status transition is permitted according to state machine rules."""
        if current_status == target_status:
            if allow_same_state:
                return
            raise InvalidStateTransitionError(
                current_status=current_status,
                target_status=target_status,
                reason=f"Booking is already in '{current_status}' state.",
            )

        allowed = VALID_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise InvalidStateTransitionError(
                current_status=current_status,
                target_status=target_status,
                reason=reason or f"Transitions from {current_status} to {target_status} are forbidden.",
            )

    @classmethod
    def apply_transition(
        cls,
        booking: Booking,
        target_status: str,
        reason: str | None = None,
        allow_same_state: bool = False,
    ) -> None:
        """Apply a validated state transition to a booking."""
        cls.validate_transition(booking.status, target_status, reason, allow_same_state=allow_same_state)
        booking.status = target_status

    @staticmethod
    def create_booking(db: Session, request: BookingCreateRequest, current_user: User) -> Booking:
        """
        Create a new diagnostic booking.
        Snapshots test price from centre_tests table at creation time so future price changes do not alter historical records.
        """
        # 1. Verify centre exists and is active
        centre = db.get(DiagnosticCentre, request.centre_id)
        if not centre:
            raise EntityNotFoundError("Diagnostic Centre", request.centre_id)
        if not centre.is_active:
            raise BusinessRuleViolationError("Diagnostic centre is currently inactive.")

        # 2. Verify test exists and is active
        test = db.get(DiagnosticTest, request.test_id)
        if not test:
            raise EntityNotFoundError("Diagnostic Test", request.test_id)
        if not test.is_active:
            raise BusinessRuleViolationError("Diagnostic test is currently inactive.")

        # 3. Verify centre offers this test and fetch snapshot price
        centre_test = db.scalar(
            select(CentreTest).where(
                CentreTest.centre_id == request.centre_id,
                CentreTest.test_id == request.test_id,
            )
        )
        if not centre_test:
            raise BusinessRuleViolationError(
                f"Diagnostic centre '{centre.name}' does not offer the test '{test.name}'."
            )

        # 4. Create booking with snapshotted amount
        booking = Booking(
            user_id=current_user.id,
            centre_id=request.centre_id,
            test_id=request.test_id,
            appointment_at=request.appointment_at,
            amount=centre_test.price,  # Snapshot price at creation
            status=BookingStatus.PENDING.value,
        )
        BookingRepository.create(db, booking)
        db.commit()
        db.refresh(booking)
        return BookingRepository.get_by_id_with_details(db, booking.id) or booking

    @staticmethod
    def get_booking(db: Session, booking_id: int, current_user: User) -> Booking:
        """Retrieve a booking with authorization check (owner or admin only)."""
        booking = BookingRepository.get_by_id_with_details(db, booking_id)
        if not booking:
            raise EntityNotFoundError("Booking", booking_id)

        # Authorization check: only the patient owner or an ADMIN may view
        if current_user.role != UserRole.ADMIN.value and booking.user_id != current_user.id:
            raise AuthorizationError("You do not have access to view this booking.")

        return booking

    @staticmethod
    def list_bookings(db: Session, current_user: User, skip: int = 0, limit: int = 100) -> list[Booking]:
        """List bookings for the current user, or all bookings if admin."""
        if current_user.role == UserRole.ADMIN.value:
            return BookingRepository.list_all(db, skip=skip, limit=limit)
        return BookingRepository.list_by_user(db, user_id=current_user.id, skip=skip, limit=limit)

    @classmethod
    def cancel_booking(cls, db: Session, booking_id: int, current_user: User) -> Booking:
        """Cancel an eligible booking (owner or admin only, must be PENDING)."""
        booking = BookingRepository.get_by_id(db, booking_id)
        if not booking:
            raise EntityNotFoundError("Booking", booking_id)

        # Authorization check
        if current_user.role != UserRole.ADMIN.value and booking.user_id != current_user.id:
            raise AuthorizationError("You do not have permission to cancel this booking.")

        # Validate and apply transition to CANCELLED
        cls.apply_transition(
            booking=booking,
            target_status=BookingStatus.CANCELLED.value,
            reason="User or Administrator initiated cancellation.",
        )
        BookingRepository.update(db, booking)
        db.commit()
        db.refresh(booking)
        return booking
