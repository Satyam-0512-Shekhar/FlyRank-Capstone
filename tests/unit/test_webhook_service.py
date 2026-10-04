"""
Unit tests for WebhookService and SubscriptionService.
"""

import hmac
import hashlib
import json
import uuid
import pytest
from app.core.config import settings
from app.core.exceptions import WebhookSignatureError, DuplicateWebhookError
from app.repositories.tenant_repository import TenantRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.payment_event_repository import PaymentEventRepository
from app.services.webhook_service import WebhookService
from app.services.subscription_service import SubscriptionService


def generate_signature(raw_body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_webhook_invalid_signature_raises_error(test_session_factory):
    async with test_session_factory() as session:
        service = WebhookService(session)
        payload = b'{"event": "subscription.activated"}'
        forged_sig = "bad_signature_hex"
        event_id = "evt_forged_test"

        with pytest.raises(WebhookSignatureError):
            await service.process_razorpay_webhook(
                raw_body=payload,
                signature=forged_sig,
                event_id=event_id,
            )


@pytest.mark.asyncio
async def test_webhook_valid_activation_upgrades_subscription(test_session_factory):
    async with test_session_factory() as session:
        tenant_repo = TenantRepository(session)
        plan_repo = PlanRepository(session)
        sub_repo = SubscriptionRepository(session)

        tenant = await tenant_repo.create("Tenant Upgrade Test")
        free_plan = await plan_repo.get_by_name("free")
        pro_plan = await plan_repo.get_by_name("pro")

        sub = await sub_repo.create(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            provider="razorpay",
            status="pending",
        )
        sub_id = "sub_test_upgrade_123"
        await sub_repo.set_provider_subscription_id(sub, sub_id, status="pending")
        await session.commit()

        # Webhook payload
        body_dict = {
            "entity": "event",
            "event": "subscription.activated",
            "contains": ["subscription"],
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
        valid_sig = generate_signature(raw_body, settings.RAZORPAY_WEBHOOK_SECRET)
        event_id = "evt_valid_upgrade_001"

        service = WebhookService(session)
        result = await service.process_razorpay_webhook(
            raw_body=raw_body,
            signature=valid_sig,
            event_id=event_id,
        )
        await session.commit()

        assert result["status"] == "processed"

        # Subscription should now be active Pro
        sub_after, plan_after = await sub_repo.get_subscription_with_plan(tenant.id)
        assert sub_after.status == "active"
        assert plan_after.name == "pro"

        # Event logged
        event_repo = PaymentEventRepository(session)
        logged_evt = await event_repo.get_by_provider_event_id("razorpay", event_id)
        assert logged_evt is not None
        assert logged_evt.status == "processed"


@pytest.mark.asyncio
async def test_webhook_duplicate_replay_is_ignored(test_session_factory):
    async with test_session_factory() as session:
        body_dict = {
            "entity": "event",
            "event": "subscription.activated",
            "payload": {"subscription": {"entity": {"id": "sub_any"}}},
        }
        raw_body = json.dumps(body_dict).encode("utf-8")
        valid_sig = generate_signature(raw_body, settings.RAZORPAY_WEBHOOK_SECRET)
        event_id = "evt_replay_test_001"

        # Seed payment event first
        event_repo = PaymentEventRepository(session)
        await event_repo.create(
            provider="razorpay",
            provider_event_id=event_id,
            event_type="subscription.activated",
            payload_hash="somehash",
            raw_payload=body_dict,
            status="processed",
        )
        await session.commit()

        service = WebhookService(session)
        # Calling process should return duplicate_webhook response or raise DuplicateWebhookError
        res = await service.process_razorpay_webhook(
            raw_body=raw_body,
            signature=valid_sig,
            event_id=event_id,
        )
        assert res["status"] == "ignored"
        assert res["reason"] == "duplicate_webhook"


@pytest.mark.asyncio
async def test_subscription_service_initiate_upgrade(test_session_factory):
    async with test_session_factory() as session:
        tenant_repo = TenantRepository(session)
        plan_repo = PlanRepository(session)
        sub_repo = SubscriptionRepository(session)

        tenant = await tenant_repo.create("Tenant Initiate Sub")
        free_plan = await plan_repo.get_by_name("free")
        await sub_repo.create(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            status="active",
        )
        await session.commit()

        sub_service = SubscriptionService(session)
        res = await sub_service.create_or_upgrade_subscription(
            tenant_id=tenant.id,
            plan_name="pro",
        )
        await session.commit()

        assert res.plan == "pro"
        assert res.provider == "razorpay"
        assert res.status in ("created", "pending")
        assert res.subscription_id.startswith("sub_")

        # Verify DB updated to pending
        sub = await sub_repo.get_by_tenant_id(tenant.id)
        assert sub.provider_subscription_id == res.subscription_id
        assert sub.status == "pending"
