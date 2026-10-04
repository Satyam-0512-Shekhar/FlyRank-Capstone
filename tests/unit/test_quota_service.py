"""
FlyRank Capstone — Unit tests for QuotaService.
Verifies dual-quota boundary conditions, budget guard, and billing period rollover.
"""

import datetime
import uuid
import pytest

from app.models.tenant import Tenant
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.usage_event import UsageEvent
from app.core.exceptions import QuotaExceededError, BudgetGuardError
from app.services.quota_service import QuotaService
from app.repositories.usage_repository import UsageRepository


@pytest.mark.asyncio
async def test_resolve_billing_period_rollover(db_session):
    now = datetime.datetime.now(datetime.timezone.utc)
    expired_start = datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    expired_end = datetime.datetime(2025, 1, 31, 23, 59, 59, tzinfo=datetime.timezone.utc)

    tenant = Tenant(name="Rollover Tenant")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    plan = Plan(
        name="free_test",
        api_call_quota=1000,
        token_quota=100000,
        max_cost_per_call_micro_inr=10000000,
        price_micro_inr=0,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)

    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        current_period_start=expired_start,
        current_period_end=expired_end,
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    # Calling resolve_billing_period should rollover to current month
    start, end = await QuotaService.resolve_billing_period(db_session, sub)
    assert start.year == now.year
    assert start.month == now.month
    assert start.day == 1
    assert end.month == now.month
    assert end > now


@pytest.mark.asyncio
async def test_quota_checks_under_limit(db_session):
    tenant = Tenant(name="Under Limit Tenant")
    plan = Plan(
        name="test_plan_under",
        api_call_quota=1000,
        token_quota=100000,
        max_cost_per_call_micro_inr=10000000,
        price_micro_inr=0,
    )
    db_session.add_all([tenant, plan])
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    start = now - datetime.timedelta(days=2)
    end = now + datetime.timedelta(days=28)

    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        current_period_start=start,
        current_period_end=end,
    )
    db_session.add(sub)
    await db_session.commit()

    # Pre-populate 999 calls, 50,000 tokens
    e = UsageEvent(
        tenant_id=tenant.id,
        usage_type="generate",
        api_calls=999,
        total_tokens=50_000,
        cost_micro_inr=1_000_000,
        timestamp=now,
    )
    await UsageRepository.create(db_session, e)

    # 1. 1000th call with 500 tokens should PASS (boundary allowed)
    await QuotaService.check_quota_and_budget(
        session=db_session,
        tenant_id=tenant.id,
        subscription=sub,
        plan=plan,
        requested_tokens=500,
        projected_cost_micro_inr=50_000,
    )


@pytest.mark.asyncio
async def test_quota_api_calls_exceeded(db_session):
    tenant = Tenant(name="Call Limit Tenant")
    plan = Plan(
        name="test_plan_calls",
        api_call_quota=1000,
        token_quota=100000,
        max_cost_per_call_micro_inr=10000000,
        price_micro_inr=0,
    )
    db_session.add_all([tenant, plan])
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        current_period_start=now - datetime.timedelta(days=1),
        current_period_end=now + datetime.timedelta(days=29),
    )
    db_session.add(sub)
    await db_session.commit()

    # Pre-populate exactly 1000 calls
    e = UsageEvent(
        tenant_id=tenant.id,
        usage_type="generate",
        api_calls=1000,
        total_tokens=50_000,
        cost_micro_inr=1_000_000,
        timestamp=now,
    )
    await UsageRepository.create(db_session, e)

    # Next call (1001) should raise QuotaExceededError for api_calls
    with pytest.raises(QuotaExceededError) as exc_info:
        await QuotaService.check_quota_and_budget(
            session=db_session,
            tenant_id=tenant.id,
            subscription=sub,
            plan=plan,
            requested_tokens=500,
            projected_cost_micro_inr=50_000,
        )
    assert exc_info.value.quota_dimension == "api_calls"
    assert exc_info.value.used == 1000
    assert exc_info.value.limit == 1000


@pytest.mark.asyncio
async def test_quota_tokens_exceeded(db_session):
    tenant = Tenant(name="Token Limit Tenant")
    plan = Plan(
        name="test_plan_tokens",
        api_call_quota=1000,
        token_quota=100000,
        max_cost_per_call_micro_inr=10000000,
        price_micro_inr=0,
    )
    db_session.add_all([tenant, plan])
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        current_period_start=now - datetime.timedelta(days=1),
        current_period_end=now + datetime.timedelta(days=29),
    )
    db_session.add(sub)
    await db_session.commit()

    # Pre-populate 99,500 tokens
    e = UsageEvent(
        tenant_id=tenant.id,
        usage_type="generate",
        api_calls=500,
        total_tokens=99_500,
        cost_micro_inr=1_000_000,
        timestamp=now,
    )
    await UsageRepository.create(db_session, e)

    # Next request of 600 tokens exceeds 100,000 limit
    with pytest.raises(QuotaExceededError) as exc_info:
        await QuotaService.check_quota_and_budget(
            session=db_session,
            tenant_id=tenant.id,
            subscription=sub,
            plan=plan,
            requested_tokens=600,
            projected_cost_micro_inr=50_000,
        )
    assert exc_info.value.quota_dimension == "ai_tokens"
    assert exc_info.value.used == 99_500
    assert exc_info.value.limit == 100_000


@pytest.mark.asyncio
async def test_budget_guard_exceeded(db_session):
    tenant = Tenant(name="Budget Guard Tenant")
    plan = Plan(
        name="test_plan_budget",
        api_call_quota=1000,
        token_quota=100000,
        max_cost_per_call_micro_inr=10_000_000,  # ₹10 ceiling
        price_micro_inr=0,
    )
    db_session.add_all([tenant, plan])
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        current_period_start=now - datetime.timedelta(days=1),
        current_period_end=now + datetime.timedelta(days=29),
    )
    db_session.add(sub)
    await db_session.commit()

    # Call with projected cost of ₹11 (11,000,000 µINR) exceeds ₹10 ceiling
    with pytest.raises(BudgetGuardError) as exc_info:
        await QuotaService.check_quota_and_budget(
            session=db_session,
            tenant_id=tenant.id,
            subscription=sub,
            plan=plan,
            requested_tokens=1000,
            projected_cost_micro_inr=11_000_000,
        )
    assert exc_info.value.details["quota_dimension"] == "budget_guard"
    assert exc_info.value.details["projected_cost_micro_inr"] == 11_000_000
