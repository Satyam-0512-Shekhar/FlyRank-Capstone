"""
Integration tests for Razorpay Webhook endpoint (/api/v1/webhooks/razorpay).
"""

import hmac
import hashlib
import json
import pytest
from httpx import AsyncClient
from app.core.config import settings
from app.repositories.tenant_repository import TenantRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository


def compute_signature(payload_bytes: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_webhook_missing_signature_returns_400(client: AsyncClient):
    resp = await client.post(
        "/api/v1/webhooks/razorpay",
        content=b'{"event": "subscription.activated"}',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_signature"


@pytest.mark.asyncio
async def test_webhook_forged_signature_returns_400(client: AsyncClient):
    payload = b'{"event": "subscription.activated"}'
    resp = await client.post(
        "/api/v1/webhooks/razorpay",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "forged_hex_signature_12345",
            "x-razorpay-event-id": "evt_forged_001",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_signature"


@pytest.mark.asyncio
async def test_webhook_valid_processing_and_replay_deduplication(
    client: AsyncClient, test_session_factory
):
    # 1. Setup tenant with pending subscription
    async with test_session_factory() as session:
        tenant_repo = TenantRepository(session)
        plan_repo = PlanRepository(session)
        sub_repo = SubscriptionRepository(session)

        tenant = await tenant_repo.create("Webhook Integration Tenant")
        free_plan = await plan_repo.get_by_name("free")
        sub = await sub_repo.create(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            status="pending",
        )
        sub_id = "sub_integration_test_456"
        await sub_repo.set_provider_subscription_id(sub, sub_id, status="pending")
        await session.commit()
        tenant_id = str(tenant.id)

    event_id = "evt_integ_valid_001"
    body_dict = {
        "entity": "event",
        "event": "subscription.activated",
        "payload": {
            "subscription": {
                "entity": {
                    "id": sub_id,
                    "plan_id": "plan_pro_monthly",
                    "status": "active",
                    "current_start": 1727827200,
                    "current_end": 1730419200,
                }
            }
        },
    }
    raw_body = json.dumps(body_dict).encode("utf-8")
    valid_sig = compute_signature(raw_body, settings.RAZORPAY_WEBHOOK_SECRET)

    # 2. First call: Should succeed and process
    resp1 = await client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": valid_sig,
            "x-razorpay-event-id": event_id,
        },
    )
    assert resp1.status_code == 200
    assert resp1.json() == {"status": "processed"}

    # 3. Check subscription is updated to Pro
    async with test_session_factory() as session:
        sub_repo = SubscriptionRepository(session)
        sub_after, plan_after = await sub_repo.get_subscription_with_plan(
            tenant.id
        )
        assert sub_after.status == "active"
        assert plan_after.name == "pro"

    # 4. Replay call: Should be ignored with 200 OK
    resp2 = await client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": valid_sig,
            "x-razorpay-event-id": event_id,
        },
    )
    assert resp2.status_code == 200
    assert resp2.json() == {
        "status": "ignored",
        "reason": "duplicate_webhook",
    }
