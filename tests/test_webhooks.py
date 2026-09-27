from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.webhook_event import PaymentWebhookEvent


def test_valid_webhook_payment_succeeded(client: TestClient, sample_booking: Booking, db_session):
    event_payload = {
        "event_id": "evt_test_001",
        "event_type": "payment.succeeded",
        "provider_payment_id": "pay_provider_001",
        "booking_id": sample_booking.id,
        "amount": "500.00",
    }
    response = client.post(
        "/api/v1/payments/webhook",
        headers={"X-Webhook-Secret": settings.WEBHOOK_SECRET},
        json=event_payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["event_id"] == "evt_test_001"
    assert data["booking_status"] == "CONFIRMED"
    assert data["payment_status"] == "SUCCESS"

    # Verify payment record created
    payment = db_session.scalar(select(Payment).where(Payment.provider_payment_id == "pay_provider_001"))
    assert payment is not None
    assert payment.status == "SUCCESS"
    assert Decimal(str(payment.amount)) == Decimal("500.00")

    # Verify booking state transitioned to CONFIRMED
    db_session.refresh(sample_booking)
    assert sample_booking.status == "CONFIRMED"

    # Verify webhook event recorded
    event = db_session.scalar(select(PaymentWebhookEvent).where(PaymentWebhookEvent.event_id == "evt_test_001"))
    assert event is not None


def test_idempotent_duplicate_webhook_no_duplicate_records(client: TestClient, sample_booking: Booking, db_session):
    event_payload = {
        "event_id": "evt_idempotent_999",
        "event_type": "payment.succeeded",
        "provider_payment_id": "pay_provider_999",
        "booking_id": sample_booking.id,
        "amount": "500.00",
    }
    headers = {"X-Webhook-Secret": settings.WEBHOOK_SECRET}

    # 1. First webhook transmission
    res1 = client.post("/api/v1/payments/webhook", headers=headers, json=event_payload)
    assert res1.status_code == 200
    assert res1.json()["status"] == "processed"

    # Count payments and webhook events
    initial_payment_count = len(list(db_session.scalars(select(Payment)).all()))
    initial_event_count = len(list(db_session.scalars(select(PaymentWebhookEvent)).all()))

    # 2. Second (duplicate) webhook transmission
    res2 = client.post("/api/v1/payments/webhook", headers=headers, json=event_payload)
    assert res2.status_code == 200
    assert res2.json()["status"] == "already_processed"
    assert "previously processed" in res2.json()["message"]

    # 3. Third (duplicate) webhook transmission
    res3 = client.post("/api/v1/payments/webhook", headers=headers, json=event_payload)
    assert res3.status_code == 200
    assert res3.json()["status"] == "already_processed"

    # Ensure no duplicates were created
    new_payment_count = len(list(db_session.scalars(select(Payment)).all()))
    new_event_count = len(list(db_session.scalars(select(PaymentWebhookEvent)).all()))

    assert new_payment_count == initial_payment_count
    assert new_event_count == initial_event_count

    # Ensure booking is still CONFIRMED
    db_session.refresh(sample_booking)
    assert sample_booking.status == "CONFIRMED"


def test_valid_webhook_payment_failed(client: TestClient, sample_booking: Booking, db_session):
    event_payload = {
        "event_id": "evt_fail_101",
        "event_type": "payment.failed",
        "provider_payment_id": "pay_failed_101",
        "booking_id": sample_booking.id,
        "amount": "500.00",
    }
    response = client.post(
        "/api/v1/payments/webhook",
        headers={"X-Webhook-Secret": settings.WEBHOOK_SECRET},
        json=event_payload,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert response.json()["booking_status"] == "FAILED"
    assert response.json()["payment_status"] == "FAILED"

    db_session.refresh(sample_booking)
    assert sample_booking.status == "FAILED"


def test_webhook_nonexistent_booking(client: TestClient):
    event_payload = {
        "event_id": "evt_invalid_booking",
        "event_type": "payment.succeeded",
        "provider_payment_id": "pay_unknown",
        "booking_id": 999999,
        "amount": "500.00",
    }
    response = client.post(
        "/api/v1/payments/webhook",
        headers={"X-Webhook-Secret": settings.WEBHOOK_SECRET},
        json=event_payload,
    )
    assert response.status_code == 404
    assert "Booking with identifier '999999' was not found" in response.json()["detail"]


def test_webhook_unsupported_event_type(client: TestClient, sample_booking: Booking):
    event_payload = {
        "event_id": "evt_unsupported",
        "event_type": "refund.created",  # Not a valid WebhookEventType enum value
        "provider_payment_id": "pay_ref_1",
        "booking_id": sample_booking.id,
        "amount": "500.00",
    }
    response = client.post(
        "/api/v1/payments/webhook",
        headers={"X-Webhook-Secret": settings.WEBHOOK_SECRET},
        json=event_payload,
    )
    # Validation error from Pydantic
    assert response.status_code == 422


def test_webhook_hmac_signature_verification(client: TestClient, sample_booking: Booking):
    import json

    from app.core.security import generate_webhook_signature

    event_payload = {
        "event_id": "evt_hmac_valid_1",
        "event_type": "payment.succeeded",
        "provider_payment_id": "pay_hmac_1",
        "booking_id": sample_booking.id,
        "amount": "500.00",
    }
    raw_payload_bytes = json.dumps(event_payload).encode("utf-8")
    valid_signature = generate_webhook_signature(raw_payload_bytes)

    # 1. Valid HMAC signature
    res_valid = client.post(
        "/api/v1/payments/webhook",
        headers={
            "X-Webhook-Signature": valid_signature,
            "Content-Type": "application/json",
        },
        content=raw_payload_bytes,
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "processed"

    # 2. Invalid HMAC signature
    res_invalid = client.post(
        "/api/v1/payments/webhook",
        headers={
            "X-Webhook-Signature": "invalid_hex_signature_9999",
            "Content-Type": "application/json",
        },
        content=raw_payload_bytes,
    )
    assert res_invalid.status_code == 401
    assert "Invalid webhook HMAC signature" in res_invalid.json()["detail"]
