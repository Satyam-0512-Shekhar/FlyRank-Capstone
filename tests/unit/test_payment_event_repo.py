"""
Unit tests for PaymentEventRepository and SubscriptionRepository webhook methods.
"""

import uuid
import pytest
from sqlalchemy.exc import IntegrityError
from app.repositories.payment_event_repository import PaymentEventRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.tenant_repository import TenantRepository
from app.repositories.plan_repository import PlanRepository


@pytest.mark.asyncio
async def test_payment_event_create_and_find(test_session_factory):
    async with test_session_factory() as session:
        repo = PaymentEventRepository(session)
        event_id = f"evt_{uuid.uuid4().hex[:12]}"

        # Initially not found
        found = await repo.get_by_provider_event_id("razorpay", event_id)
        assert found is None

        # Create
        created = await repo.create(
            provider="razorpay",
            provider_event_id=event_id,
            event_type="subscription.activated",
            payload_hash="hash123",
            raw_payload={"event": "subscription.activated"},
            status="processed",
        )
        await session.commit()

        assert created.id is not None
        assert created.provider_event_id == event_id
        assert created.status == "processed"

        # Query found
        found_again = await repo.get_by_provider_event_id("razorpay", event_id)
        assert found_again is not None
        assert found_again.id == created.id
        assert found_again.provider_event_id == event_id


@pytest.mark.asyncio
async def test_payment_event_uniqueness_enforced(test_session_factory):
    async with test_session_factory() as session:
        repo = PaymentEventRepository(session)
        event_id = "evt_duplicate_test"

        await repo.create(
            provider="razorpay",
            provider_event_id=event_id,
            event_type="subscription.activated",
            payload_hash="hash1",
            raw_payload={},
        )
        await session.commit()

        # Second create must fail with IntegrityError
        with pytest.raises(IntegrityError):
            await repo.create(
                provider="razorpay",
                provider_event_id=event_id,
                event_type="subscription.activated",
                payload_hash="hash2",
                raw_payload={},
            )
            await session.commit()


@pytest.mark.asyncio
async def test_subscription_lookup_and_upgrade(test_session_factory):
    async with test_session_factory() as session:
        tenant_repo = TenantRepository(session)
        plan_repo = PlanRepository(session)
        sub_repo = SubscriptionRepository(session)

        tenant = await tenant_repo.create("Test Tenant Payments")
        free_plan = await plan_repo.get_by_name("free")
        pro_plan = await plan_repo.get_by_name("pro")

        sub = await sub_repo.create(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            provider="razorpay",
            status="created",
        )
        await sub_repo.set_provider_subscription_id(sub, "sub_prov_123", status="pending")
        await session.commit()

        # Lookup by provider_subscription_id
        found_sub = await sub_repo.get_by_provider_subscription_id("sub_prov_123")
        assert found_sub is not None
        assert found_sub.id == sub.id
        assert found_sub.status == "pending"

        # Upgrade to pro
        upgraded = await sub_repo.upgrade_to_plan(
            subscription=found_sub,
            new_plan_id=pro_plan.id,
            new_status="active",
        )
        await session.commit()

        assert upgraded.status == "active"
        assert upgraded.plan_id == pro_plan.id
