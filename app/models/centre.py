from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.centre_test import CentreTest


class DiagnosticCentre(Base, TimestampMixin):
    __tablename__ = "diagnostic_centres"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)

    # Relationships
    centre_tests: Mapped[list["CentreTest"]] = relationship(
        "CentreTest", back_populates="centre", cascade="all, delete-orphan"
    )
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="centre")
