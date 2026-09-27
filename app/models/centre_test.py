from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.centre import DiagnosticCentre
    from app.models.test import DiagnosticTest


class CentreTest(Base):
    """Association table connecting a Diagnostic Centre with an available Diagnostic Test and its price."""

    __tablename__ = "centre_tests"

    centre_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_centres.id", ondelete="CASCADE"),
        primary_key=True,
    )
    test_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_tests.id", ondelete="CASCADE"),
        primary_key=True,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Relationships
    centre: Mapped["DiagnosticCentre"] = relationship("DiagnosticCentre", back_populates="centre_tests")
    test: Mapped["DiagnosticTest"] = relationship("DiagnosticTest", back_populates="centre_tests")
