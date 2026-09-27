from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.utils.enums import BookingStatus

if TYPE_CHECKING:
    from app.models.centre import DiagnosticCentre
    from app.models.payment import Payment
    from app.models.test import DiagnosticTest
    from app.models.user import User


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    centre_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_centres.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    test_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_tests.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    appointment_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # The price is snapshotted at creation time to protect against future price changes
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default=BookingStatus.PENDING.value,
        index=True,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="bookings")
    centre: Mapped["DiagnosticCentre"] = relationship("DiagnosticCentre", back_populates="bookings")
    test: Mapped["DiagnosticTest"] = relationship("DiagnosticTest", back_populates="bookings")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="booking", cascade="all, delete-orphan")
