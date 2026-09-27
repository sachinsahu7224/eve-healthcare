from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.booking import Booking


class BookingRepository:
    """Repository handling database operations for Bookings."""

    @staticmethod
    def get_by_id(db: Session, booking_id: int) -> Booking | None:
        return db.get(Booking, booking_id)

    @staticmethod
    def get_by_id_with_details(db: Session, booking_id: int) -> Booking | None:
        stmt = (
            select(Booking)
            .options(
                joinedload(Booking.user),
                joinedload(Booking.centre),
                joinedload(Booking.test),
            )
            .where(Booking.id == booking_id)
        )
        return db.scalar(stmt)

    @staticmethod
    def list_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> list[Booking]:
        stmt = (
            select(Booking)
            .options(
                joinedload(Booking.centre),
                joinedload(Booking.test),
            )
            .where(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def list_all(db: Session, skip: int = 0, limit: int = 100) -> list[Booking]:
        stmt = (
            select(Booking)
            .options(
                joinedload(Booking.centre),
                joinedload(Booking.test),
            )
            .order_by(Booking.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def create(db: Session, booking: Booking) -> Booking:
        db.add(booking)
        db.flush()
        return booking

    @staticmethod
    def update(db: Session, booking: Booking) -> Booking:
        db.flush()
        return booking
