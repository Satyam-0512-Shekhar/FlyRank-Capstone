"""
FlyRank Capstone — Unit tests for UsageRepository and IdempotencyRepository.
Verifies aggregation, date range filtering, tenant isolation, and idempotency records.
"""

import datetime
import uuid
import pytest

from app.models.tenant import Tenant
from app.models.usage_event import UsageEvent
from app.models.idempotency import IdempotencyRecord
from app.repositories.usage_repository import UsageRepository
from app.repositories.idempotency_repository import IdempotencyRepository


@pytest.mark.asyncio
async def test_usage_repository_crud_and_aggregation(db_session):
    tenant = Tenant(name="Acme Repo Test")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(days=1)
    end_time = now + datetime.timedelta(days=1)

    # 1. Insert 2 events within window
    e1 = UsageEvent(
        tenant_id=tenant.id,
        usage_type="generate",
        api_calls=1,
        total_tokens=1000,
        fresh_input_tokens=500,
        cached_input_tokens=200,
        output_tokens=200,
        reasoning_tokens=100,
        cost_micro_inr=50_000,
        idempotency_key="key-1",
        timestamp=now,
    )
    e2 = UsageEvent(
        tenant_id=tenant.id,
        usage_type="generate",
        api_calls=1,
        total_tokens=500,
        fresh_input_tokens=250,
        cached_input_tokens=100,
        output_tokens=100,
        reasoning_tokens=50,
        cost_micro_inr=25_000,
        idempotency_key="key-2",
        timestamp=now,
    )
    await UsageRepository.create(db_session, e1)
    await UsageRepository.create(db_session, e2)

    # 2. Insert 1 event outside window (10 days ago)
    e_old = UsageEvent(
        tenant_id=tenant.id,
        usage_type="generate",
        api_calls=1,
        total_tokens=9999,
        cost_micro_inr=999_999,
        timestamp=now - datetime.timedelta(days=10),
    )
    await UsageRepository.create(db_session, e_old)

    # 3. Insert 1 event for another tenant
    other_tenant = Tenant(name="Other Tenant")
    db_session.add(other_tenant)
    await db_session.commit()
    await db_session.refresh(other_tenant)

    e_other = UsageEvent(
        tenant_id=other_tenant.id,
        usage_type="generate",
        api_calls=5,
        total_tokens=50_000,
        cost_micro_inr=1_000_000,
        timestamp=now,
    )
    await UsageRepository.create(db_session, e_other)

    # 4. Aggregate usage for tenant
    api_calls, tokens, cost = await UsageRepository.get_period_usage(
        db_session, tenant.id, start_time, end_time
    )
    assert api_calls == 2
    assert tokens == 1500
    assert cost == 75_000

    # 5. Token breakdown
    breakdown = await UsageRepository.get_period_token_breakdown(
        db_session, tenant.id, start_time, end_time
    )
    assert breakdown["fresh_input_tokens"] == 750
    assert breakdown["cached_input_tokens"] == 300
    assert breakdown["output_tokens"] == 300
    assert breakdown["reasoning_tokens"] == 150

    # 6. List events
    events = await UsageRepository.list_events(db_session, tenant.id, limit=10, offset=0)
    assert len(events) == 3


@pytest.mark.asyncio
async def test_idempotency_repository_crud(db_session):
    tenant = Tenant(name="Idem Tenant")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    record = IdempotencyRecord(
        tenant_id=tenant.id,
        idempotency_key="probe-test-key",
        request_hash="a"*64,
        response_status_code=200,
        response_body={"message": "ok"},
    )
    saved = await IdempotencyRepository.create(db_session, record)
    assert saved.id is not None

    found = await IdempotencyRepository.get(db_session, tenant.id, "probe-test-key")
    assert found is not None
    assert found.request_hash == "a"*64
    assert found.response_body == {"message": "ok"}

    not_found = await IdempotencyRepository.get(db_session, tenant.id, "nonexistent-key")
    assert not_found is None
