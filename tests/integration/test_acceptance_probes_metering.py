"""
FlyRank Capstone — Acceptance Probes 1, 2, and 5 Automated Verification.
Verifies:
- PROBE 1: Idempotent Metering (Sequential & Concurrent duplicate protection)
- PROBE 2: Quota Boundary Honesty (1000th call allowed, 1001st rejected with 429 and Retry-After)
- PROBE 5: AI Token Pricing Verification (Exact 172,000 µINR formula & GET /usage breakdown)
"""

import asyncio
import datetime
import uuid
import pytest
from httpx import AsyncClient

from app.models.usage_event import UsageEvent
from app.repositories.usage_repository import UsageRepository


@pytest.mark.asyncio
async def test_probe_1_idempotent_metering_sequential_and_concurrent(client: AsyncClient, db_session):
    """
    PROBE 1:
    Seed clean tenant T1 on Free plan.
    Send POST /generate twice with identical Idempotency-Key: probe-1-key-001.
    Expected:
    - Call 1: 200 OK, X-Cache-Lookup: MISS
    - Call 2: 200 OK, X-Cache-Lookup: HIT, identical response body
    - DB: Exactly 1 row in usage_events, exactly 1 row in idempotency_records
    - Also test concurrent execution across parallel tasks with same key.
    """
    # 1. Setup clean tenant T1
    create_resp = await client.post("/api/v1/tenants", json={"name": "Probe 1 Tenant"})
    assert create_resp.status_code == 201
    tenant_id = create_resp.json()["id"]

    idempotency_key = "probe-1-key-001"
    payload = {
        "prompt": "Probe 1 test prompt",
        "model": "gpt-simulated",
        "simulated_tokens": {
            "fresh_input_tokens": 500,
            "cached_input_tokens": 200,
            "output_tokens": 100,
            "reasoning_tokens": 50,
        },
    }

    # 2. Sequential Call 1 (Fresh MISS)
    resp1 = await client.post(
        "/api/v1/generate",
        json=payload,
        headers={"X-Tenant-ID": tenant_id, "Idempotency-Key": idempotency_key},
    )
    assert resp1.status_code == 200
    assert resp1.headers["X-Cache-Lookup"] == "MISS"
    data1 = resp1.json()
    assert data1["metering"]["api_calls_metered"] == 1
    assert data1["metering"]["total_tokens_metered"] == 850

    # 3. Sequential Call 2 (Duplicate HIT)
    resp2 = await client.post(
        "/api/v1/generate",
        json=payload,
        headers={"X-Tenant-ID": tenant_id, "Idempotency-Key": idempotency_key},
    )
    assert resp2.status_code == 200
    assert resp2.headers["X-Cache-Lookup"] == "HIT"
    data2 = resp2.json()
    assert data2 == data1

    # 4. Verify DB state: Exactly 1 usage event in database
    events = await UsageRepository.list_events(db_session, uuid.UUID(tenant_id))
    assert len(events) == 1
    assert events[0].total_tokens == 850
    assert events[0].api_calls == 1

    # 5. Concurrent duplicate check with a new key
    concurrent_key = "probe-1-concurrent-key"
    concurrent_payload = {
        "prompt": "Concurrent probe test",
        "simulated_tokens": {"fresh_input_tokens": 100, "output_tokens": 50},
    }

    # Send 5 concurrent requests with identical key
    tasks = [
        client.post(
            "/api/v1/generate",
            json=concurrent_payload,
            headers={"X-Tenant-ID": tenant_id, "Idempotency-Key": concurrent_key},
        )
        for _ in range(5)
    ]
    responses = await asyncio.gather(*tasks)

    # All 5 must succeed with 200 OK
    for r in responses:
        assert r.status_code == 200
        assert r.json()["id"] == responses[0].json()["id"]

    # Exactly 1 MISS and 4 HITs across concurrent requests
    lookup_headers = [r.headers["X-Cache-Lookup"] for r in responses]
    assert lookup_headers.count("MISS") == 1
    assert lookup_headers.count("HIT") == 4

    # DB state must have exactly 2 usage events in total for tenant (event 1 + event 2)
    events_resp = await client.get("/api/v1/usage/events", headers={"X-Tenant-ID": tenant_id})
    assert events_resp.status_code == 200
    all_events = events_resp.json()
    assert len(all_events) == 2


@pytest.mark.asyncio
async def test_probe_2_quota_boundary_honesty(client: AsyncClient, db_session):
    """
    PROBE 2:
    Seed tenant T2 on Free plan (limits: 1,000 API calls, 100,000 tokens).
    Pre-populate usage to exactly 999 API calls and 99,000 tokens.
    Request:
    - Boundary Call #1000: 1 call, 500 tokens -> Expected 200 OK. Total in DB: 1,000 calls, 99,500 tokens.
    - Beyond Boundary Call #1001: 1 call, 500 tokens -> Expected 429 Too Many Requests, Retry-After header.
    - Zero usage events recorded for Call #1001. Total in DB remains 1,000 calls.
    """
    # 1. Setup tenant T2
    create_resp = await client.post("/api/v1/tenants", json={"name": "Probe 2 Tenant"})
    assert create_resp.status_code == 201
    tenant_id = create_resp.json()["id"]
    tenant_uuid = uuid.UUID(tenant_id)

    # 2. Pre-populate usage: 999 calls, 99,000 tokens
    now = datetime.datetime.now(datetime.timezone.utc)
    pre_event = UsageEvent(
        tenant_id=tenant_uuid,
        usage_type="generate",
        api_calls=999,
        total_tokens=99_000,
        fresh_input_tokens=99_000,
        cached_input_tokens=0,
        output_tokens=0,
        reasoning_tokens=0,
        cost_micro_inr=3_960_000,
        timestamp=now,
    )
    await UsageRepository.create(db_session, pre_event)
    await db_session.commit()

    # 3. Boundary Call #1000: requesting 1 API call and 500 tokens
    resp_1000 = await client.post(
        "/api/v1/generate",
        json={
            "prompt": "Call 1000 boundary call",
            "simulated_tokens": {"fresh_input_tokens": 500},
        },
        headers={"X-Tenant-ID": tenant_id, "Idempotency-Key": "call-1000-key"},
    )
    assert resp_1000.status_code == 200
    assert resp_1000.headers["X-Cache-Lookup"] == "MISS"

    # Verify DB state after Call #1000: exactly 1000 calls, 99,500 tokens
    start_of_month = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    end_of_month = datetime.datetime(now.year, now.month, 28, 23, 59, 59, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=4)
    calls, tokens, _ = await UsageRepository.get_period_usage(db_session, tenant_uuid, start_of_month, end_of_month)
    assert calls == 1000
    assert tokens == 99_500

    # 4. Beyond Boundary Call #1001: requesting 1 API call and 500 tokens
    resp_1001 = await client.post(
        "/api/v1/generate",
        json={
            "prompt": "Call 1001 beyond boundary call",
            "simulated_tokens": {"fresh_input_tokens": 500},
        },
        headers={"X-Tenant-ID": tenant_id, "Idempotency-Key": "call-1001-key"},
    )
    assert resp_1001.status_code == 429
    assert "Retry-After" in resp_1001.headers
    retry_after = int(resp_1001.headers["Retry-After"])
    assert retry_after > 0

    err_body = resp_1001.json()
    assert err_body["error"] == "quota_exceeded"
    assert err_body["quota_dimension"] == "api_calls"
    assert err_body["limit"] == 1000
    assert err_body["used"] == 1000
    assert err_body["requested"] == 1

    # 5. Verify DB state: Call #1001 recorded ZERO events, totals remain 1000 calls & 99,500 tokens
    calls_after, tokens_after, _ = await UsageRepository.get_period_usage(
        db_session, tenant_uuid, start_of_month, end_of_month
    )
    assert calls_after == 1000
    assert tokens_after == 99_500


@pytest.mark.asyncio
async def test_probe_5_ai_token_pricing_verification(client: AsyncClient):
    """
    PROBE 5:
    Seed clean tenant T5.
    POST /generate with:
    - 1,000 Fresh Input tokens (40 µINR each = 40,000)
    - 2,000 Cached Input tokens (10 µINR each = 20,000)
    - 500 Output tokens (160 µINR each = 80,000)
    - 200 Reasoning tokens (160 µINR each = 32,000)
    Expected cost = 172,000 µINR.
    Verify:
    1. POST /generate returns cost_micro_inr = 172000, formatted = '₹0.17'
    2. GET /usage returns total_cost.micro_inr = 172000, and exact token breakdown
    """
    # 1. Setup tenant T5
    create_resp = await client.post("/api/v1/tenants", json={"name": "Probe 5 Tenant"})
    assert create_resp.status_code == 201
    tenant_id = create_resp.json()["id"]

    # 2. Call POST /generate
    gen_resp = await client.post(
        "/api/v1/generate",
        json={
            "prompt": "Probe 5 token pricing prompt",
            "simulated_tokens": {
                "fresh_input_tokens": 1000,
                "cached_input_tokens": 2000,
                "output_tokens": 500,
                "reasoning_tokens": 200,
            },
        },
        headers={"X-Tenant-ID": tenant_id, "Idempotency-Key": "probe-5-key-001"},
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["metering"]["cost_micro_inr"] == 172_000
    assert gen_data["metering"]["formatted_cost"] == "₹0.17"
    assert gen_data["metering"]["total_tokens_metered"] == 3700

    # 3. Call GET /usage
    usage_resp = await client.get("/api/v1/usage", headers={"X-Tenant-ID": tenant_id})
    assert usage_resp.status_code == 200
    usage_data = usage_resp.json()

    assert usage_data["total_cost"]["micro_inr"] == 172_000
    assert usage_data["total_cost"]["formatted"] == "₹0.17"
    assert usage_data["api_calls"]["used"] == 1
    assert usage_data["ai_tokens"]["used"] == 3700
    breakdown = usage_data["ai_tokens"]["breakdown"]
    assert breakdown["fresh_input_tokens"] == 1000
    assert breakdown["cached_input_tokens"] == 2000
    assert breakdown["output_tokens"] == 500
    assert breakdown["reasoning_tokens"] == 200
