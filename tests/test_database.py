from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.payment import Payment
from app.models.test import DiagnosticTest
from app.models.user import User
from app.models.webhook_event import PaymentWebhookEvent
from app.utils.enums import UserRole


def test_user_email_unique_constraint(db_session: Session):
    user1 = User(
        email="unique@evehealth.com",
        password_hash="hash1",
        full_name="User One",
        role=UserRole.PATIENT.value,
    )
    db_session.add(user1)
    db_session.commit()

    user2 = User(
        email="unique@evehealth.com",  # Duplicate email
        password_hash="hash2",
        full_name="User Two",
        role=UserRole.PATIENT.value,
    )
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_payment_provider_id_unique_constraint(db_session: Session, sample_booking: Booking):
    payment1 = Payment(
        booking_id=sample_booking.id,
        provider_payment_id="tx_unique_123",
        amount=Decimal("500.00"),
        status="SUCCESS",
    )
    db_session.add(payment1)
    db_session.commit()

    payment2 = Payment(
        booking_id=sample_booking.id,
        provider_payment_id="tx_unique_123",  # Duplicate provider ID
        amount=Decimal("500.00"),
        status="SUCCESS",
    )
    db_session.add(payment2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_webhook_event_id_unique_constraint(db_session: Session):
    event1 = PaymentWebhookEvent(
        event_id="evt_unique_abc",
        event_type="payment.succeeded",
        payload='{"foo": "bar"}',
    )
    db_session.add(event1)
    db_session.commit()

    event2 = PaymentWebhookEvent(
        event_id="evt_unique_abc",  # Duplicate event_id
        event_type="payment.succeeded",
        payload='{"foo": "bar"}',
    )
    db_session.add(event2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_centre_test_composite_pk_constraint(
    db_session: Session, sample_centre: DiagnosticCentre, sample_test: DiagnosticTest
):
    ct1 = CentreTest(
        centre_id=sample_centre.id,
        test_id=sample_test.id,
        price=Decimal("400.00"),
    )
    db_session.add(ct1)
    db_session.commit()
    db_session.expunge_all()

    ct2 = CentreTest(
        centre_id=sample_centre.id,
        test_id=sample_test.id,  # Duplicate composite PK
        price=Decimal("500.00"),
    )
    db_session.add(ct2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
