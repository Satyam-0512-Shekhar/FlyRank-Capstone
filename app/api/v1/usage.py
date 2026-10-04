"""
FlyRank Capstone — GET /api/v1/usage and GET /api/v1/usage/events API Router.
Provides real-time quota consumption analytics, breakdowns, and immutable event ledger listings.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.tenant import Tenant
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.usage_repository import UsageRepository
from app.schemas.usage import (
    ApiCallUsage,
    BillingPeriod,
    TokenBreakdown,
    TokenUsage,
    TotalCost,
    UsageEventItem,
    UsageSummaryResponse,
)
from app.services.pricing_service import PricingService
from app.services.quota_service import QuotaService

router = APIRouter(prefix="/usage", tags=["Usage"])


@router.get(
    "",
    response_model=UsageSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregated usage, quotas, and cost for current billing window",
)
async def get_usage_summary(
    current_tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> UsageSummaryResponse:
    """
    Returns dual-quota metrics (API calls and AI tokens) and accumulated integer micro-INR costs.
    """
    sub_repo = SubscriptionRepository(session)
    subscription = await sub_repo.get_by_tenant_id(current_tenant.id)
    if not subscription:
        raise NotFoundError("Subscription not found for current tenant.")

    plan_repo = PlanRepository(session)
    plan = await plan_repo.get_by_id(subscription.plan_id)
    if not plan:
        raise NotFoundError("Plan not found for subscription.")

    start_time, end_time = await QuotaService.resolve_billing_period(session, subscription)
    used_calls, used_tokens, used_cost = await UsageRepository.get_period_usage(
        session=session,
        tenant_id=current_tenant.id,
        start_time=start_time,
        end_time=end_time,
    )
    breakdown_dict = await UsageRepository.get_period_token_breakdown(
        session=session,
        tenant_id=current_tenant.id,
        start_time=start_time,
        end_time=end_time,
    )

    remaining_calls = max(plan.api_call_quota - used_calls, 0)
    remaining_tokens = max(plan.token_quota - used_tokens, 0)

    return UsageSummaryResponse(
        tenant_id=current_tenant.id,
        plan=plan.name,
        billing_period=BillingPeriod(start=start_time, end=end_time),
        api_calls=ApiCallUsage(
            used=used_calls,
            limit=plan.api_call_quota,
            remaining=remaining_calls,
        ),
        ai_tokens=TokenUsage(
            used=used_tokens,
            limit=plan.token_quota,
            remaining=remaining_tokens,
            breakdown=TokenBreakdown(**breakdown_dict),
        ),
        total_cost=TotalCost(
            micro_inr=used_cost,
            formatted=PricingService.format_micro_inr(used_cost),
        ),
    )


@router.get(
    "/events",
    response_model=list[UsageEventItem],
    status_code=status.HTTP_200_OK,
    summary="List paginated immutable usage events for current tenant",
)
async def list_usage_events(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page (max 100)"),
    current_tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> list[UsageEventItem]:
    """Returns chronologically ordered usage events strictly scoped to current tenant."""
    offset = (page - 1) * page_size
    events = await UsageRepository.list_events(
        session=session,
        tenant_id=current_tenant.id,
        limit=page_size,
        offset=offset,
    )

    return [
        UsageEventItem(
            id=e.id,
            timestamp=e.timestamp,
            usage_type=e.usage_type,
            api_calls=e.api_calls,
            total_tokens=e.total_tokens,
            fresh_input_tokens=e.fresh_input_tokens,
            cached_input_tokens=e.cached_input_tokens,
            output_tokens=e.output_tokens,
            reasoning_tokens=e.reasoning_tokens,
            cost_micro_inr=e.cost_micro_inr,
            formatted_cost=PricingService.format_micro_inr(e.cost_micro_inr),
            idempotency_key=e.idempotency_key,
        )
        for e in events
    ]
