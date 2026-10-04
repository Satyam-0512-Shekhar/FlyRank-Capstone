"""
Razorpay Webhook receiver API endpoint.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.billing import WebhookResponse
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/razorpay",
    response_model=WebhookResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Receive and verify Razorpay webhook events",
)
async def handle_razorpay_webhook(
    request: Request,
    x_razorpay_signature: Annotated[str | None, Header(alias="X-Razorpay-Signature")] = None,
    x_razorpay_event_id: Annotated[str | None, Header(alias="x-razorpay-event-id")] = None,
    session: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """
    Receive, cryptographically verify, and idempotently process Razorpay webhooks.
    """
    raw_body = await request.body()
    service = WebhookService(session)
    result = await service.process_razorpay_webhook(
        raw_body=raw_body,
        signature=x_razorpay_signature,
        event_id=x_razorpay_event_id,
    )
    return WebhookResponse(**result)
