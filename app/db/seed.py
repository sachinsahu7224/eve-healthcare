import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.models.user import User
from app.utils.enums import UserRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed")


def seed_database(db: Session) -> None:
    """Populate database with development seed data idempotently."""
    logger.info("Starting database seeding...")

    # 1. Seed Admin User
    admin = db.scalar(select(User).where(User.email == settings.SEED_ADMIN_EMAIL))
    if not admin:
        admin = User(
            email=settings.SEED_ADMIN_EMAIL,
            password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
            full_name=settings.SEED_ADMIN_NAME,
            role=UserRole.ADMIN.value,
        )
        db.add(admin)
        logger.info(f"Created Admin user: {settings.SEED_ADMIN_EMAIL}")
    else:
        logger.info(f"Admin user already exists: {settings.SEED_ADMIN_EMAIL}")

    # 2. Seed Normal Patient User
    patient = db.scalar(select(User).where(User.email == settings.SEED_PATIENT_EMAIL))
    if not patient:
        patient = User(
            email=settings.SEED_PATIENT_EMAIL,
            password_hash=hash_password(settings.SEED_PATIENT_PASSWORD),
            full_name=settings.SEED_PATIENT_NAME,
            role=UserRole.PATIENT.value,
        )
        db.add(patient)
        logger.info(f"Created Patient user: {settings.SEED_PATIENT_EMAIL}")
    else:
        logger.info(f"Patient user already exists: {settings.SEED_PATIENT_EMAIL}")

    db.commit()

    # 3. Seed Diagnostic Centres
    centres_data = [
        {
            "name": "EVE Central Diagnostic Hub",
            "location": "100 Feet Rd, Indiranagar, Bengaluru",
        },
        {
            "name": "EVE South Diagnostic Clinic",
            "location": "80 Feet Rd, Koramangala, Bengaluru",
        },
        {
            "name": "EVE West Pathology & Imaging",
            "location": "Sampige Rd, Malleshwaram, Bengaluru",
        },
    ]
    centres_dict = {}
    for c_data in centres_data:
        centre = db.scalar(select(DiagnosticCentre).where(DiagnosticCentre.name == c_data["name"]))
        if not centre:
            centre = DiagnosticCentre(name=c_data["name"], location=c_data["location"], is_active=True)
            db.add(centre)
            db.commit()
            db.refresh(centre)
            logger.info(f"Created Centre: {centre.name} (ID: {centre.id})")
        centres_dict[centre.name] = centre

    # 4. Seed Diagnostic Tests
    tests_data = [
        {
            "name": "Complete Blood Count (CBC)",
            "description": "Evaluates overall health and detects a variety of disorders, including anemia and infection.",
        },
        {
            "name": "Lipid Profile Panel",
            "description": "Measures cholesterol and triglycerides in your blood to assess cardiovascular risk.",
        },
        {
            "name": "Thyroid Profile (T3, T4, TSH)",
            "description": "Checks thyroid hormone levels to evaluate thyroid gland functionality.",
        },
        {
            "name": "HbA1c (Glycated Hemoglobin)",
            "description": "Reflects average blood sugar levels over the past 2 to 3 months for diabetes management.",
        },
        {
            "name": "Vitamin D (25-OH)",
            "description": "Measures 25-hydroxyvitamin D concentration to screen for deficiency or bone disorders.",
        },
    ]
    tests_dict = {}
    for t_data in tests_data:
        test = db.scalar(select(DiagnosticTest).where(DiagnosticTest.name == t_data["name"]))
        if not test:
            test = DiagnosticTest(name=t_data["name"], description=t_data["description"], is_active=True)
            db.add(test)
            db.commit()
            db.refresh(test)
            logger.info(f"Created Test: {test.name} (ID: {test.id})")
        tests_dict[test.name] = test

    # 5. Seed Centre-Test Associations with Prices
    # Central Hub offers all 5 tests
    # South Clinic offers CBC, Lipid, HbA1c
    # West Pathology offers CBC, Thyroid, Vitamin D
    offerings = [
        # Central Hub
        ("EVE Central Diagnostic Hub", "Complete Blood Count (CBC)", Decimal("450.00")),
        ("EVE Central Diagnostic Hub", "Lipid Profile Panel", Decimal("850.00")),
        (
            "EVE Central Diagnostic Hub",
            "Thyroid Profile (T3, T4, TSH)",
            Decimal("750.00"),
        ),
        (
            "EVE Central Diagnostic Hub",
            "HbA1c (Glycated Hemoglobin)",
            Decimal("600.00"),
        ),
        ("EVE Central Diagnostic Hub", "Vitamin D (25-OH)", Decimal("1200.00")),
        # South Clinic
        (
            "EVE South Diagnostic Clinic",
            "Complete Blood Count (CBC)",
            Decimal("400.00"),
        ),
        ("EVE South Diagnostic Clinic", "Lipid Profile Panel", Decimal("800.00")),
        (
            "EVE South Diagnostic Clinic",
            "HbA1c (Glycated Hemoglobin)",
            Decimal("550.00"),
        ),
        # West Pathology
        (
            "EVE West Pathology & Imaging",
            "Complete Blood Count (CBC)",
            Decimal("420.00"),
        ),
        (
            "EVE West Pathology & Imaging",
            "Thyroid Profile (T3, T4, TSH)",
            Decimal("700.00"),
        ),
        ("EVE West Pathology & Imaging", "Vitamin D (25-OH)", Decimal("1150.00")),
    ]

    for centre_name, test_name, price in offerings:
        c = centres_dict.get(centre_name)
        t = tests_dict.get(test_name)
        if c and t:
            existing_ct = db.scalar(select(CentreTest).where(CentreTest.centre_id == c.id, CentreTest.test_id == t.id))
            if not existing_ct:
                ct = CentreTest(centre_id=c.id, test_id=t.id, price=price)
                db.add(ct)
                logger.info(f"Assigned test '{t.name}' to centre '{c.name}' at price {price}")

    db.commit()
    logger.info("Database seeding completed successfully.")


def run_seed() -> None:
    """Run seeding using application engine."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
