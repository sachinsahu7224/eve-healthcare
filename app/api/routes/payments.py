from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, verify_simulated_webhook_signature
from app.core.database import get_db
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import PaymentResponse, SimulatePaymentRequest
from app.schemas.webhook import PaymentWebhookPayload, PaymentWebhookResponse
from app.services.payment_service import PaymentService
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/payments", tags=["Payments & Webhooks"])


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Simulate a payment for a booking",
)
def simulate_payment(
    request: SimulatePaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Payment:
    """
    Simulate a payment transaction (SUCCESS or FAILED) without real payment gateways.
    Atomically updates the associated booking to CONFIRMED or FAILED.
    """
    payment = PaymentService.simulate_payment(db=db, request=request, current_user=current_user)
    return payment


@router.post(
    "/webhook",
    response_model=PaymentWebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive simulated payment provider webhook (Idempotent)",
)
async def payment_webhook(
    request: Request,
    payload: PaymentWebhookPayload,
    db: Session = Depends(get_db),
    _auth: None = Depends(verify_simulated_webhook_signature),
) -> PaymentWebhookResponse:
    """
    Idempotent payment webhook handler.
    Guarantees that repeated transmissions of the same event_id:
    - Never produce duplicate payments or duplicate bookings
    - Never corrupt state machine transitions
    - Safely return a 200 OK idempotent response
    """
    raw_body = await request.body()
    raw_payload_str = raw_body.decode("utf-8") if raw_body else None

    return WebhookService.process_payment_webhook(db=db, payload=payload, raw_payload_str=raw_payload_str)
