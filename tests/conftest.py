from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.booking import Booking
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.models.user import User
from app.utils.enums import BookingStatus, UserRole

# In-memory SQLite for rapid, isolated, zero-dependency testing
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a clean database session for test verification."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden get_db dependency."""

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session: Session) -> User:
    user = User(
        email="admin_test@evehealth.com",
        password_hash=hash_password("AdminPass123!"),
        full_name="Admin Tester",
        role=UserRole.ADMIN.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def patient_user(db_session: Session) -> User:
    user = User(
        email="patient_test@evehealth.com",
        password_hash=hash_password("PatientPass123!"),
        full_name="Patient Tester",
        role=UserRole.PATIENT.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_patient_user(db_session: Session) -> User:
    user = User(
        email="other_patient@evehealth.com",
        password_hash=hash_password("OtherPass123!"),
        full_name="Other Patient",
        role=UserRole.PATIENT.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(admin_user: User) -> dict:
    token = create_access_token(subject=admin_user.id, role=admin_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def patient_headers(patient_user: User) -> dict:
    token = create_access_token(subject=patient_user.id, role=patient_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_patient_headers(other_patient_user: User) -> dict:
    token = create_access_token(subject=other_patient_user.id, role=other_patient_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_centre(db_session: Session) -> DiagnosticCentre:
    centre = DiagnosticCentre(
        name="Apollo Diagnostic Centre",
        location="Indiranagar, Bangalore",
        is_active=True,
    )
    db_session.add(centre)
    db_session.commit()
    db_session.refresh(centre)
    return centre


@pytest.fixture
def sample_test(db_session: Session) -> DiagnosticTest:
    diag_test = DiagnosticTest(
        name="Complete Blood Count",
        description="Standard 18 parameter CBC test",
        is_active=True,
    )
    db_session.add(diag_test)
    db_session.commit()
    db_session.refresh(diag_test)
    return diag_test


@pytest.fixture
def sample_offering(db_session: Session, sample_centre: DiagnosticCentre, sample_test: DiagnosticTest) -> CentreTest:
    ct = CentreTest(
        centre_id=sample_centre.id,
        test_id=sample_test.id,
        price=Decimal("500.00"),
    )
    db_session.add(ct)
    db_session.commit()
    db_session.refresh(ct)
    return ct


@pytest.fixture
def sample_booking(
    db_session: Session,
    patient_user: User,
    sample_centre: DiagnosticCentre,
    sample_test: DiagnosticTest,
    sample_offering: CentreTest,
) -> Booking:
    booking = Booking(
        user_id=patient_user.id,
        centre_id=sample_centre.id,
        test_id=sample_test.id,
        appointment_at=datetime.now(timezone.utc) + timedelta(days=2),
        amount=sample_offering.price,
        status=BookingStatus.PENDING.value,
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)
    return booking
