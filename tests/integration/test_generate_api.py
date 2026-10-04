"""
FlyRank Capstone — Integration tests for POST /api/v1/generate.
Verifies successful generation, idempotency headers, conflict detection, and quota errors.
"""

import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_generate_endpoint_success_and_cache_lookup_headers(client: AsyncClient):
    # 1. Create a tenant
    create_resp = await client.post("/api/v1/tenants", json={"name": "Generate Tenant"})
    assert create_resp.status_code == 201
    tenant_id = create_resp.json()["id"]

    idempotency_key = f"gen-key-{uuid.uuid4()}"
    payload = {
        "prompt": "Write a python function to compute fibonacci",
        "model": "gpt-simulated",
        "simulated_tokens": {
            "fresh_input_tokens": 1000,
            "cached_input_tokens": 2000,
            "output_tokens": 500,
            "reasoning_tokens": 200,
        },
    }

    # 2. First call: MISS
    resp1 = await client.post(
        "/api/v1/generate",
        json=payload,
        headers={"X-Tenant-ID": tenant_id, "Idempotency-Key": idempotency_key},
    )
    assert resp1.status_code == 200
    assert resp1.headers["X-Cache-Lookup"] == "MISS"
    data1 = resp1.json()
    assert data1["metering"]["cost_micro_inr"] == 172000
    assert data1["metering"]["api_calls_metered"] == 1
    assert data1["metering"]["total_tokens_metered"] == 3700

    # 3. Second call: HIT (identical key and payload)
    resp2 = await client.post(
        "/api/v1/generate",
        json=payload,
        headers={"X-Tenant-ID": tenant_id, "Idempotency-Key": idempotency_key},
    )
    assert resp2.status_code == 200
    assert resp2.headers["X-Cache-Lookup"] == "HIT"
    data2 = resp2.json()
    assert data2["id"] == data1["id"]
    assert data2["metering"] == data1["metering"]


@pytest.mark.asyncio
async def test_generate_endpoint_idempotency_conflict_409(client: AsyncClient):
    create_resp = await client.post("/api/v1/tenants", json={"name": "Conflict Tenant"})
    tenant_id = create_resp.json()["id"]

    idempotency_key = f"gen-conflict-{uuid.uuid4()}"
    payload1 = {
        "prompt": "Prompt 1",
        "simulated_tokens": {"fresh_input_tokens": 100},
    }
    payload2 = {
        "prompt": "Different Prompt 2",
        "simulated_tokens": {"fresh_input_tokens": 100},
    }

    # Call 1 succeeds
    r1 = await client.post(
        "/api/v1/generate",
        json=payload1,
        headers={"X-Tenant-ID": tenant_id, "Idempotency-Key": idempotency_key},
    )
    assert r1.status_code == 200

    # Call 2 with same key but different body -> 409 Conflict
    r2 = await client.post(
        "/api/v1/generate",
        json=payload2,
        headers={"X-Tenant-ID": tenant_id, "Idempotency-Key": idempotency_key},
    )
    assert r2.status_code == 409
    assert r2.json()["error"] == "idempotency_conflict"


@pytest.mark.asyncio
async def test_generate_endpoint_missing_idempotency_key(client: AsyncClient):
    create_resp = await client.post("/api/v1/tenants", json={"name": "No Key Tenant"})
    tenant_id = create_resp.json()["id"]

    resp = await client.post(
        "/api/v1/generate",
        json={"prompt": "Hello"},
        headers={"X-Tenant-ID": tenant_id},
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_generate_endpoint_budget_guard_exceeded_429(client: AsyncClient):
    create_resp = await client.post("/api/v1/tenants", json={"name": "Budget Guard Tenant"})
    tenant_id = create_resp.json()["id"]

    # Free plan ceiling is ₹10.00 (10,000,000 µINR).
    # Requesting 100,000 output tokens * 160 µINR = 16,000,000 µINR (₹16.00)
    payload = {
        "prompt": "Massive generation",
        "simulated_tokens": {"output_tokens": 100_000},
    }

    resp = await client.post(
        "/api/v1/generate",
        json=payload,
        headers={"X-Tenant-ID": tenant_id, "Idempotency-Key": "budget-test-key"},
    )
    assert resp.status_code == 429
    body = resp.json()
    assert body["error"] == "budget_guard_exceeded"
