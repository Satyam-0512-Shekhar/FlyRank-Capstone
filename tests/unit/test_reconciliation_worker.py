"""
Unit tests for Background Subscription Reconciliation Worker.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, patch
from app.models.subscription import Subscription
from app.repositories.tenant_repository import TenantRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.workers.reconciliation import ReconciliationWorker


class MockPaymentProvider:
    def __init__(self, fetch_status: str = "active", fail_count: int = 0):
        self.fetch_status = fetch_status
        self.fail_count = fail_count
        self.attempts = 0

    async def create_subscription(self, *args, **kwargs):
        return {"id": "sub_mock"}

    async def fetch_subscription(self, subscription_id: str):
        self.attempts += 1
        if self.attempts <= self.fail_count:
            raise ConnectionError("Gateway timeout")
        return {
            "id": subscription_id,
            "status": self.fetch_status,
            "current_start": 1727827200,
            "current_end": 1730419200,
        }

    async def cancel_subscription(self, subscription_id: str):
        return {"id": subscription_id, "status": "cancelled"}


@pytest.mark.asyncio
async def test_reconciliation_activates_pending_subscription(test_session_factory):
    async with test_session_factory() as session:
        tenant_repo = TenantRepository(session)
        plan_repo = PlanRepository(session)
        sub_repo = SubscriptionRepository(session)

        tenant = await tenant_repo.create("Reconciliation Test Tenant")
        free_plan = await plan_repo.get_by_name("free")

        sub = await sub_repo.create(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            provider="razorpay",
            status="pending",
        )
        sub_id = "sub_reconcile_active_001"
        await sub_repo.set_provider_subscription_id(sub, sub_id, status="pending")
        await session.commit()
        tenant_id = tenant.id

    mock_provider = MockPaymentProvider(fetch_status="active")
    worker = ReconciliationWorker(
        session_factory=test_session_factory,
        payment_provider=mock_provider,
        backoff_delays=[0.01, 0.02, 0.04],
    )

    reconciled_count = await worker.reconcile_pending_subscriptions(max_age_minutes=0)
    assert reconciled_count == 1
    assert mock_provider.attempts == 1

    # Verify database state
    async with test_session_factory() as session:
        sub_repo = SubscriptionRepository(session)
        sub_check, plan_check = await sub_repo.get_subscription_with_plan(tenant_id)
        assert sub_check.status == "active"
        assert plan_check.name == "pro"


@pytest.mark.asyncio
async def test_reconciliation_leaves_still_pending_unchanged(test_session_factory):
    async with test_session_factory() as session:
        tenant_repo = TenantRepository(session)
        plan_repo = PlanRepository(session)
        sub_repo = SubscriptionRepository(session)

        tenant = await tenant_repo.create("Reconciliation Still Pending Tenant")
        free_plan = await plan_repo.get_by_name("free")

        sub = await sub_repo.create(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            provider="razorpay",
            status="pending",
        )
        sub_id = "sub_reconcile_pending_002"
        await sub_repo.set_provider_subscription_id(sub, sub_id, status="pending")
        await session.commit()
        tenant_id = tenant.id

    mock_provider = MockPaymentProvider(fetch_status="created")
    worker = ReconciliationWorker(
        session_factory=test_session_factory,
        payment_provider=mock_provider,
        backoff_delays=[0.01, 0.02, 0.04],
    )

    reconciled_count = await worker.reconcile_pending_subscriptions(max_age_minutes=0)
    assert reconciled_count == 0

    async with test_session_factory() as session:
        sub_repo = SubscriptionRepository(session)
        sub_check, plan_check = await sub_repo.get_subscription_with_plan(tenant_id)
        assert sub_check.status == "pending"
        assert plan_check.name == "free"


@pytest.mark.asyncio
async def test_reconciliation_retries_and_alerts_on_persistent_failure(
    test_session_factory,
):
    async with test_session_factory() as session:
        tenant_repo = TenantRepository(session)
        plan_repo = PlanRepository(session)
        sub_repo = SubscriptionRepository(session)

        tenant = await tenant_repo.create("Reconciliation Failure Tenant")
        free_plan = await plan_repo.get_by_name("free")

        sub = await sub_repo.create(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            provider="razorpay",
            status="pending",
        )
        sub_id = "sub_reconcile_fail_003"
        await sub_repo.set_provider_subscription_id(sub, sub_id, status="pending")
        await session.commit()

    # Fail all 3 attempts
    mock_provider = MockPaymentProvider(fail_count=5)
    worker = ReconciliationWorker(
        session_factory=test_session_factory,
        payment_provider=mock_provider,
        backoff_delays=[0.01, 0.02, 0.04],
    )

    with patch("app.workers.reconciliation.logger.error") as mock_log:
        reconciled_count = await worker.reconcile_pending_subscriptions(max_age_minutes=0)

    assert reconciled_count == 0
    assert mock_provider.attempts == 3
    assert mock_log.called
    assert "ALERT: Subscription reconciliation failed" in mock_log.call_args[0][0]
