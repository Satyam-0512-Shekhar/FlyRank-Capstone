"""
Billing & Subscription API endpoints.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant
from app.core.database import get_db
from app.models.tenant import Tenant
from app.schemas.billing import (
    CreateSubscriptionRequest,
    CreateSubscriptionResponse,
    SubscriptionStatusResponse,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/billing", tags=["Billing & Subscriptions"])


@router.post(
    "/subscription",
    response_model=CreateSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate subscription upgrade",
)
async def create_subscription(
    body: CreateSubscriptionRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> CreateSubscriptionResponse:
    """Initiate a recurring subscription upgrade with payment gateway."""
    service = SubscriptionService(session)
    response = await service.create_or_upgrade_subscription(
        tenant_id=current_tenant.id,
        plan_name=body.plan_name,
    )
    return response


@router.get(
    "/subscription",
    response_model=SubscriptionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="View active tenant subscription",
)
async def get_subscription(
    current_tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> SubscriptionStatusResponse:
    """Fetch current tenant subscription details."""
    service = SubscriptionService(session)
    response = await service.get_subscription_status(tenant_id=current_tenant.id)
    return response
