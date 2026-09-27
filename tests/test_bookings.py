from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.models.booking import Booking
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest


def test_create_booking_success(
    client: TestClient,
    patient_headers: dict,
    sample_centre: DiagnosticCentre,
    sample_test: DiagnosticTest,
    sample_offering: CentreTest,
):
    future_date = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    response = client.post(
        "/api/v1/bookings",
        headers=patient_headers,
        json={
            "centre_id": sample_centre.id,
            "test_id": sample_test.id,
            "appointment_at": future_date,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["centre_id"] == sample_centre.id
    assert data["test_id"] == sample_test.id
    assert data["status"] == "PENDING"
    # Price is snapshotted from centre_tests
    assert Decimal(str(data["amount"])) == sample_offering.price


def test_price_snapshot_immutability(
    client: TestClient,
    admin_headers: dict,
    patient_headers: dict,
    sample_centre: DiagnosticCentre,
    sample_test: DiagnosticTest,
    sample_offering: CentreTest,
):
    """Verify that updating centre test price later does NOT change historical booking amount."""
    # 1. Create booking when price is 500.00
    future_date = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    res1 = client.post(
        "/api/v1/bookings",
        headers=patient_headers,
        json={
            "centre_id": sample_centre.id,
            "test_id": sample_test.id,
            "appointment_at": future_date,
        },
    )
    assert res1.status_code == 201
    booking_id = res1.json()["id"]
    assert Decimal(str(res1.json()["amount"])) == Decimal("500.00")

    # 2. Admin increases price to 800.00
    res2 = client.post(
        f"/api/v1/centres/{sample_centre.id}/tests",
        headers=admin_headers,
        json={"test_id": sample_test.id, "price": "800.00"},
    )
    assert res2.status_code == 200

    # 3. Retrieve historical booking - amount must still be 500.00
    res3 = client.get(f"/api/v1/bookings/{booking_id}", headers=patient_headers)
    assert res3.status_code == 200
    assert Decimal(str(res3.json()["amount"])) == Decimal("500.00")


def test_create_booking_unauthenticated(
    client: TestClient, sample_centre: DiagnosticCentre, sample_test: DiagnosticTest
):
    future_date = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    response = client.post(
        "/api/v1/bookings",
        json={
            "centre_id": sample_centre.id,
            "test_id": sample_test.id,
            "appointment_at": future_date,
        },
    )
    assert response.status_code == 401


def test_create_booking_invalid_centre(client: TestClient, patient_headers: dict, sample_test: DiagnosticTest):
    future_date = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    response = client.post(
        "/api/v1/bookings",
        headers=patient_headers,
        json={
            "centre_id": 99999,
            "test_id": sample_test.id,
            "appointment_at": future_date,
        },
    )
    assert response.status_code == 404
    assert "Diagnostic Centre" in response.json()["detail"]


def test_create_booking_invalid_test(client: TestClient, patient_headers: dict, sample_centre: DiagnosticCentre):
    future_date = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    response = client.post(
        "/api/v1/bookings",
        headers=patient_headers,
        json={
            "centre_id": sample_centre.id,
            "test_id": 99999,
            "appointment_at": future_date,
        },
    )
    assert response.status_code == 404
    assert "Diagnostic Test" in response.json()["detail"]


def test_create_booking_unoffered_test(
    client: TestClient,
    patient_headers: dict,
    sample_centre: DiagnosticCentre,
    db_session,
):
    # Create test not offered by sample_centre
    unoffered = DiagnosticTest(name="Rare Genetic Sequence", is_active=True)
    db_session.add(unoffered)
    db_session.commit()
    db_session.refresh(unoffered)

    future_date = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    response = client.post(
        "/api/v1/bookings",
        headers=patient_headers,
        json={
            "centre_id": sample_centre.id,
            "test_id": unoffered.id,
            "appointment_at": future_date,
        },
    )
    assert response.status_code == 400
    assert "does not offer the test" in response.json()["detail"]


def test_user_cannot_access_another_users_booking(
    client: TestClient,
    sample_booking: Booking,
    other_patient_headers: dict,
):
    response = client.get(
        f"/api/v1/bookings/{sample_booking.id}",
        headers=other_patient_headers,
    )
    assert response.status_code == 403
    assert "do not have access" in response.json()["detail"]


def test_admin_can_access_any_booking(
    client: TestClient,
    sample_booking: Booking,
    admin_headers: dict,
):
    response = client.get(
        f"/api/v1/bookings/{sample_booking.id}",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["id"] == sample_booking.id


def test_cancel_booking_success(
    client: TestClient,
    sample_booking: Booking,
    patient_headers: dict,
):
    response = client.post(
        f"/api/v1/bookings/{sample_booking.id}/cancel",
        headers=patient_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"

    # Verify status in database
    get_res = client.get(f"/api/v1/bookings/{sample_booking.id}", headers=patient_headers)
    assert get_res.json()["status"] == "CANCELLED"


def test_cancel_already_cancelled_booking_fails(
    client: TestClient,
    sample_booking: Booking,
    patient_headers: dict,
):
    # First cancel
    client.post(f"/api/v1/bookings/{sample_booking.id}/cancel", headers=patient_headers)
    # Second cancel attempt (invalid state transition from CANCELLED to CANCELLED)
    res = client.post(f"/api/v1/bookings/{sample_booking.id}/cancel", headers=patient_headers)
    assert res.status_code == 400
    assert "Cannot transition from CANCELLED to CANCELLED" in res.json()["detail"]
