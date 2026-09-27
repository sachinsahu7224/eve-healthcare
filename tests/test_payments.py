from fastapi.testclient import TestClient

from app.models.booking import Booking


def test_simulate_payment_success(client: TestClient, sample_booking: Booking, patient_headers: dict):
    response = client.post(
        "/api/v1/payments",
        headers=patient_headers,
        json={
            "booking_id": sample_booking.id,
            "simulate_status": "SUCCESS",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["booking_id"] == sample_booking.id
    assert data["status"] == "SUCCESS"
    assert "pay_sim_" in data["provider_payment_id"]

    # Verify booking status transitioned to CONFIRMED
    booking_res = client.get(f"/api/v1/bookings/{sample_booking.id}", headers=patient_headers)
    assert booking_res.json()["status"] == "CONFIRMED"


def test_simulate_payment_failed(client: TestClient, sample_booking: Booking, patient_headers: dict):
    response = client.post(
        "/api/v1/payments",
        headers=patient_headers,
        json={
            "booking_id": sample_booking.id,
            "simulate_status": "FAILED",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "FAILED"

    # Verify booking status transitioned to FAILED
    booking_res = client.get(f"/api/v1/bookings/{sample_booking.id}", headers=patient_headers)
    assert booking_res.json()["status"] == "FAILED"


def test_cannot_pay_for_already_confirmed_booking(client: TestClient, sample_booking: Booking, patient_headers: dict):
    # First payment succeeds
    client.post(
        "/api/v1/payments",
        headers=patient_headers,
        json={"booking_id": sample_booking.id, "simulate_status": "SUCCESS"},
    )
    # Second payment attempt on confirmed booking
    response = client.post(
        "/api/v1/payments",
        headers=patient_headers,
        json={"booking_id": sample_booking.id, "simulate_status": "SUCCESS"},
    )
    assert response.status_code == 400
    assert "Only PENDING bookings can be paid" in response.json()["detail"]


def test_cannot_pay_for_cancelled_booking(client: TestClient, sample_booking: Booking, patient_headers: dict):
    # Cancel first
    client.post(f"/api/v1/bookings/{sample_booking.id}/cancel", headers=patient_headers)

    # Attempt to pay for cancelled booking
    response = client.post(
        "/api/v1/payments",
        headers=patient_headers,
        json={"booking_id": sample_booking.id, "simulate_status": "SUCCESS"},
    )
    assert response.status_code == 400
    assert "Only PENDING bookings can be paid" in response.json()["detail"]


def test_unauthorized_user_cannot_pay_for_booking(
    client: TestClient, sample_booking: Booking, other_patient_headers: dict
):
    response = client.post(
        "/api/v1/payments",
        headers=other_patient_headers,
        json={"booking_id": sample_booking.id, "simulate_status": "SUCCESS"},
    )
    assert response.status_code == 403
    assert "do not have permission" in response.json()["detail"]
