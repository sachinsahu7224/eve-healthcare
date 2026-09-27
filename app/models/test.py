from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.centre_test import CentreTest


class DiagnosticTest(Base, TimestampMixin):
    __tablename__ = "diagnostic_tests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)

    # Relationships
    centre_tests: Mapped[list["CentreTest"]] = relationship(
        "CentreTest", back_populates="test", cascade="all, delete-orphan"
    )
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="test")
