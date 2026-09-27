from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.booking import Booking
from app.models.user import User
from app.schemas.booking import (
    BookingCancelResponse,
    BookingCreateRequest,
    BookingResponse,
)
from app.services.booking_service import BookingService

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def _format_booking_response(booking: Booking) -> BookingResponse:
    """Helper to convert Booking ORM model with joined relationships to BookingResponse schema."""
    return BookingResponse(
        id=booking.id,
        user_id=booking.user_id,
        centre_id=booking.centre_id,
        centre_name=booking.centre.name if booking.centre else None,
        test_id=booking.test_id,
        test_name=booking.test.name if booking.test else None,
        appointment_at=booking.appointment_at,
        amount=booking.amount,
        status=booking.status,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
    )


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new diagnostic test booking",
)
def create_booking(
    request: BookingCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    """
    Create a new booking for an authenticated patient.
    Snapshots the test price from the diagnostic centre at the time of booking.
    """
    booking = BookingService.create_booking(db=db, request=request, current_user=current_user)
    return _format_booking_response(booking)


@router.get(
    "",
    response_model=list[BookingResponse],
    summary="List bookings for the authenticated user",
)
def list_bookings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BookingResponse]:
    """
    List bookings.
    Regular patients see only their own bookings; administrators see all bookings.
    """
    bookings = BookingService.list_bookings(db=db, current_user=current_user, skip=skip, limit=limit)
    return [_format_booking_response(b) for b in bookings]


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Get details of a specific booking",
)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    """Retrieve booking by ID. Patients may only view their own bookings; Admins may view any."""
    booking = BookingService.get_booking(db=db, booking_id=booking_id, current_user=current_user)
    return _format_booking_response(booking)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingCancelResponse,
    summary="Cancel a pending booking",
)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingCancelResponse:
    """
    Cancel an existing booking.
    Only PENDING bookings can be cancelled. Once CONFIRMED or FAILED, cancellation is forbidden.
    """
    booking = BookingService.cancel_booking(db=db, booking_id=booking_id, current_user=current_user)
    return BookingCancelResponse(
        id=booking.id,
        status=booking.status,
        message=f"Booking {booking.id} was successfully cancelled.",
    )
