"""
FlyRank Capstone — Integration tests for GET /api/v1/usage and GET /api/v1/usage/events.
"""

import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_usage_summary_and_events_api(client: AsyncClient):
    create_resp = await client.post("/api/v1/tenants", json={"name": "Usage API Tenant"})
    tenant_id = create_resp.json()["id"]

    # 1. Initially usage is 0
    init_usage = await client.get("/api/v1/usage", headers={"X-Tenant-ID": tenant_id})
    assert init_usage.status_code == 200
    data = init_usage.json()
    assert data["plan"] == "free"
    assert data["api_calls"]["used"] == 0
    assert data["api_calls"]["limit"] == 1000
    assert data["api_calls"]["remaining"] == 1000
    assert data["ai_tokens"]["used"] == 0
    assert data["ai_tokens"]["limit"] == 100000

    # 2. Perform 1 generate call
    gen_resp = await client.post(
        "/api/v1/generate",
        json={
            "prompt": "Test generate for usage rollup",
            "simulated_tokens": {
                "fresh_input_tokens": 1000,
                "cached_input_tokens": 2000,
                "output_tokens": 500,
                "reasoning_tokens": 200,
            },
        },
        headers={"X-Tenant-ID": tenant_id, "Idempotency-Key": f"usage-key-{uuid.uuid4()}"},
    )
    assert gen_resp.status_code == 200

    # 3. Check updated usage
    updated_usage = await client.get("/api/v1/usage", headers={"X-Tenant-ID": tenant_id})
    assert updated_usage.status_code == 200
    up_data = updated_usage.json()
    assert up_data["api_calls"]["used"] == 1
    assert up_data["api_calls"]["remaining"] == 999
    assert up_data["ai_tokens"]["used"] == 3700
    assert up_data["ai_tokens"]["remaining"] == 100000 - 3700
    assert up_data["ai_tokens"]["breakdown"]["fresh_input_tokens"] == 1000
    assert up_data["ai_tokens"]["breakdown"]["cached_input_tokens"] == 2000
    assert up_data["ai_tokens"]["breakdown"]["output_tokens"] == 500
    assert up_data["ai_tokens"]["breakdown"]["reasoning_tokens"] == 200
    assert up_data["total_cost"]["micro_inr"] == 172000

    # 4. Check events list
    events_resp = await client.get("/api/v1/usage/events", headers={"X-Tenant-ID": tenant_id})
    assert events_resp.status_code == 200
    events = events_resp.json()
    assert len(events) == 1
    assert events[0]["cost_micro_inr"] == 172000
    assert events[0]["api_calls"] == 1
