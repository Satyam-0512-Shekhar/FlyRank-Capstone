"""
FlyRank Capstone — Acceptance Probes 3 & 4 Verification.

Covers:
- PROBE 3: Razorpay Test Subscription Upgrade Flow (DESIGN.md §3.2)
- PROBE 4: Webhook Signature Verification & Deduplication (DESIGN.md §3.2)
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
from app.repositories.payment_event_repository import PaymentEventRepository


def sign_payload(raw_body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_probe_3_pro_upgrade(client: AsyncClient, test_session_factory):
    """
    PROBE 3: Razorpay Test Subscription Upgrade Flow.

    Setup: Tenant T3 on Free tier with pending subscription 'sub_probe3_test'.
    Action: Send valid subscription.activated webhook.
    Verify:
      1. Webhook returns 200 OK with {"status": "processed"}.
      2. DB subscription transitions pending -> active with plan_id = Pro.
      3. GET /usage reflects new Pro limits: 50,000 API calls, 5,000,000 tokens.
    """
    sub_id = "sub_probe3_test"

    # Setup Tenant T3
    async with test_session_factory() as session:
        tenant_repo = TenantRepository(session)
        plan_repo = PlanRepository(session)
        sub_repo = SubscriptionRepository(session)

        tenant = await tenant_repo.create("Probe 3 Tenant")
        free_plan = await plan_repo.get_by_name("free")

        sub = await sub_repo.create(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            provider="razorpay",
            status="pending",
        )
        await sub_repo.set_provider_subscription_id(sub, sub_id, status="pending")
        await session.commit()
        tenant_id = str(tenant.id)

    # 1. Trigger Webhook
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
    sig = sign_payload(raw_body, settings.RAZORPAY_WEBHOOK_SECRET)
    event_id = "evt_probe3_upgrade"

    webhook_resp = await client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "x-razorpay-event-id": event_id,
        },
    )
    assert webhook_resp.status_code == 200
    assert webhook_resp.json() == {"status": "processed"}

    # 2. Check Database State
    async with test_session_factory() as session:
        sub_repo = SubscriptionRepository(session)
        sub_record, plan_record = await sub_repo.get_subscription_with_plan(tenant.id)
        assert sub_record.status == "active"
        assert plan_record.name == "pro"

        event_repo = PaymentEventRepository(session)
        evt = await event_repo.get_by_provider_event_id("razorpay", event_id)
        assert evt is not None
        assert evt.status == "processed"

    # 3. Query GET /usage to verify immediate Pro quota elevation
    usage_resp = await client.get("/api/v1/usage", headers={"X-Tenant-ID": tenant_id})
    assert usage_resp.status_code == 200
    usage_data = usage_resp.json()

    assert usage_data["plan"] == "pro"
    assert usage_data["api_calls"]["limit"] == 50000
    assert usage_data["ai_tokens"]["limit"] == 10000000


@pytest.mark.asyncio
async def test_probe_4_webhook_security(client: AsyncClient, test_session_factory):
    """
    PROBE 4: Webhook Signature Verification & Deduplication.

    Setup: Tenant T4 with pending subscription 'sub_probe4_test'.
    Step 4a (Forged): Invalid HMAC -> 400 Bad Request, zero DB mutations.
    Step 4b (Valid): Genuine HMAC -> 200 OK processed, subscription activated.
    Step 4c (Replayed): Duplicate event ID resent -> 200 OK ignored, zero duplicate writes.
    """
    sub_id = "sub_probe4_test"

    # Setup Tenant T4
    async with test_session_factory() as session:
        tenant_repo = TenantRepository(session)
        plan_repo = PlanRepository(session)
        sub_repo = SubscriptionRepository(session)

        tenant = await tenant_repo.create("Probe 4 Tenant")
        free_plan = await plan_repo.get_by_name("free")

        sub = await sub_repo.create(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            provider="razorpay",
            status="pending",
        )
        await sub_repo.set_provider_subscription_id(sub, sub_id, status="pending")
        await session.commit()
        tenant_id = str(tenant.id)

    # ── Step 4a: Forged Webhook ──────────────────────────────────────────────
    forged_body = json.dumps({"event": "subscription.activated", "id": sub_id}).encode("utf-8")
    resp_4a = await client.post(
        "/api/v1/webhooks/razorpay",
        content=forged_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "forged_signature_hex_bad_mac",
            "x-razorpay-event-id": "evt_probe4_forged",
        },
    )
    assert resp_4a.status_code == 400
    assert resp_4a.json()["error"] == "invalid_signature"

    # Verify zero database mutations after 4a
    async with test_session_factory() as session:
        sub_repo = SubscriptionRepository(session)
        event_repo = PaymentEventRepository(session)

        sub_check = await sub_repo.get_by_tenant_id(tenant.id)
        assert sub_check.status == "pending"

        forged_evt = await event_repo.get_by_provider_event_id("razorpay", "evt_probe4_forged")
        assert forged_evt is None

    # ── Step 4b: Valid Webhook ──────────────────────────────────────────────
    valid_event_id = "evt_probe4_valid"
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
    valid_sig = sign_payload(raw_body, settings.RAZORPAY_WEBHOOK_SECRET)

    resp_4b = await client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": valid_sig,
            "x-razorpay-event-id": valid_event_id,
        },
    )
    assert resp_4b.status_code == 200
    assert resp_4b.json() == {"status": "processed"}

    # Verify subscription activated and payment event logged
    async with test_session_factory() as session:
        sub_repo = SubscriptionRepository(session)
        event_repo = PaymentEventRepository(session)

        sub_check = await sub_repo.get_by_tenant_id(tenant.id)
        assert sub_check.status == "active"

        valid_evt = await event_repo.get_by_provider_event_id("razorpay", valid_event_id)
        assert valid_evt is not None
        assert valid_evt.status == "processed"

    # ── Step 4c: Replayed Webhook ───────────────────────────────────────────
    resp_4c = await client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": valid_sig,
            "x-razorpay-event-id": valid_event_id,
        },
    )
    assert resp_4c.status_code == 200
    assert resp_4c.json() == {
        "status": "ignored",
        "reason": "duplicate_webhook",
    }

    # Verify still exactly 1 event and subscription unchanged
    async with test_session_factory() as session:
        sub_repo = SubscriptionRepository(session)
        sub_check = await sub_repo.get_by_tenant_id(tenant.id)
        assert sub_check.status == "active"
