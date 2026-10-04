"""
FlyRank Capstone — Unit tests for MeterService.
Verifies double-checked locking, request hashing, conflict handling, and usage recording.
"""

import uuid
import pytest

from app.models.tenant import Tenant
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.schemas.usage import GenerateRequest, SimulatedTokens
from app.core.exceptions import IdempotencyConflictError, QuotaExceededError, BudgetGuardError
from app.services.meter_service import MeterService
from app.repositories.usage_repository import UsageRepository


@pytest.mark.asyncio
async def test_fresh_generate_creates_event_and_idempotency_record(db_session):
    tenant = Tenant(name="Meter Tenant")
    plan = Plan(
        name="meter_plan",
        api_call_quota=1000,
        token_quota=100000,
        max_cost_per_call_micro_inr=10000000,
        price_micro_inr=0,
    )
    db_session.add_all([tenant, plan])
    await db_session.commit()

    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
    )
    db_session.add(sub)
    await db_session.commit()

    req = GenerateRequest(
        prompt="Test prompt",
        simulated_tokens=SimulatedTokens(
            fresh_input_tokens=1000,
            cached_input_tokens=2000,
            output_tokens=500,
            reasoning_tokens=200,
        ),
    )

    resp, is_cache_hit = await MeterService.process_generate(
        session=db_session,
        tenant_id=tenant.id,
        idempotency_key="key-test-001",
        request_data=req,
    )

    assert is_cache_hit is False
    assert resp["metering"]["api_calls_metered"] == 1
    assert resp["metering"]["total_tokens_metered"] == 3700
    assert resp["metering"]["cost_micro_inr"] == 172000
    assert resp["metering"]["formatted_cost"] == "₹0.17"

    # Verify 1 usage event recorded in DB
    events = await UsageRepository.list_events(db_session, tenant.id)
    assert len(events) == 1
    assert events[0].cost_micro_inr == 172000


@pytest.mark.asyncio
async def test_duplicate_key_same_payload_returns_cached(db_session):
    tenant = Tenant(name="Dup Tenant")
    plan = Plan(
        name="dup_plan",
        api_call_quota=1000,
        token_quota=100000,
        max_cost_per_call_micro_inr=10000000,
        price_micro_inr=0,
    )
    db_session.add_all([tenant, plan])
    await db_session.commit()

    sub = Subscription(tenant_id=tenant.id, plan_id=plan.id, status="active")
    db_session.add(sub)
    await db_session.commit()

    req = GenerateRequest(
        prompt="Identical prompt",
        simulated_tokens=SimulatedTokens(fresh_input_tokens=100, output_tokens=50),
    )

    # First call
    resp1, hit1 = await MeterService.process_generate(
        session=db_session,
        tenant_id=tenant.id,
        idempotency_key="probe-1-key",
        request_data=req,
    )
    assert hit1 is False

    # Second call (exact same key and payload)
    resp2, hit2 = await MeterService.process_generate(
        session=db_session,
        tenant_id=tenant.id,
        idempotency_key="probe-1-key",
        request_data=req,
    )
    assert hit2 is True
    assert resp2["id"] == resp1["id"]
    assert resp2["metering"] == resp1["metering"]

    # Verify ledger STILL has exactly 1 event (zero double-counting)
    events = await UsageRepository.list_events(db_session, tenant.id)
    assert len(events) == 1


@pytest.mark.asyncio
async def test_duplicate_key_different_payload_raises_409(db_session):
    tenant = Tenant(name="Conflict Tenant")
    plan = Plan(
        name="conflict_plan",
        api_call_quota=1000,
        token_quota=100000,
        max_cost_per_call_micro_inr=10000000,
        price_micro_inr=0,
    )
    db_session.add_all([tenant, plan])
    await db_session.commit()

    sub = Subscription(tenant_id=tenant.id, plan_id=plan.id, status="active")
    db_session.add(sub)
    await db_session.commit()

    req1 = GenerateRequest(
        prompt="Initial prompt",
        simulated_tokens=SimulatedTokens(fresh_input_tokens=100),
    )
    req2 = GenerateRequest(
        prompt="DIFFERENT prompt with same key",
        simulated_tokens=SimulatedTokens(fresh_input_tokens=100),
    )

    # First call succeeds
    await MeterService.process_generate(
        session=db_session,
        tenant_id=tenant.id,
        idempotency_key="reused-key",
        request_data=req1,
    )

    # Second call with DIFFERENT body raises IdempotencyConflictError (409)
    with pytest.raises(IdempotencyConflictError):
        await MeterService.process_generate(
            session=db_session,
            tenant_id=tenant.id,
            idempotency_key="reused-key",
            request_data=req2,
        )
