"""
FlyRank Capstone — Resilient Background Subscription Reconciliation Worker.

Periodically reconciles pending/created database subscriptions with the
payment gateway (Razorpay API) using exponential backoff, concurrency locking
(SELECT ... FOR UPDATE SKIP LOCKED), and structured failure alerting.
Satisfies FlyRank Shared Requirement #3 without bloated message-broker dependencies.
"""

import asyncio
import datetime
import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import AsyncSessionLocal
from app.integrations.payments.base import PaymentProvider
from app.integrations.payments.razorpay import RazorpayProvider
from app.models.subscription import Subscription
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository

logger = logging.getLogger(__name__)


class ReconciliationWorker:
    """
    Lightweight, resilient async reconciliation worker.
    Reconciles orphaned or delayed subscription states between gateway and local ledger.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        payment_provider: PaymentProvider | None = None,
        backoff_delays: list[float] | None = None,
    ):
        self.session_factory = session_factory or AsyncSessionLocal
        self.provider = payment_provider or RazorpayProvider()
        # Default exponential backoff per DESIGN.md §12: 1s, 2s, 4s
        self.backoff_delays = backoff_delays if backoff_delays is not None else [1.0, 2.0, 4.0]

    async def reconcile_pending_subscriptions(
        self,
        max_age_minutes: int = 5,
        limit: int = 50,
    ) -> int:
        """
        Scan and reconcile subscriptions currently in 'pending' or 'created' status.
        Uses SELECT ... FOR UPDATE SKIP LOCKED on PostgreSQL to prevent parallel worker collisions.
        Returns the number of subscriptions successfully reconciled to 'active'.
        """
        reconciled_count = 0

        async with self.session_factory() as session:
            stmt = select(Subscription).where(
                Subscription.status.in_(["pending", "created"]),
                Subscription.provider_subscription_id.isnot(None),
            )

            if max_age_minutes > 0:
                cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
                    minutes=max_age_minutes
                )
                stmt = stmt.where(Subscription.updated_at <= cutoff)

            # Dialect-safe row locking: use SKIP LOCKED on PostgreSQL
            bind = session.bind
            if bind and bind.dialect.name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)

            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            for sub in subscriptions:
                success = await self._reconcile_single(session, sub)
                if success:
                    reconciled_count += 1

            if reconciled_count > 0:
                await session.commit()

        return reconciled_count

    async def _reconcile_single(
        self,
        session: AsyncSession,
        sub: Subscription,
    ) -> bool:
        """
        Reconcile a single subscription with exponential backoff and alerting.
        """
        provider_sub_id = sub.provider_subscription_id
        if not provider_sub_id:
            return False

        # Exponential backoff retry loop
        provider_data: dict[str, Any] | None = None
        for attempt, delay in enumerate(self.backoff_delays, 1):
            try:
                provider_data = await self.provider.fetch_subscription(provider_sub_id)
                break
            except Exception as exc:
                if attempt == len(self.backoff_delays):
                    # Structured failure alert per DESIGN.md §12
                    logger.error(
                        "ALERT: Subscription reconciliation failed for tenant %s (sub_id: %s)",
                        sub.tenant_id,
                        provider_sub_id,
                        extra={
                            "alert": True,
                            "tenant_id": str(sub.tenant_id),
                            "subscription_id": provider_sub_id,
                            "error": str(exc),
                        },
                    )
                    return False
                await asyncio.sleep(delay)

        if not provider_data:
            return False

        remote_status = provider_data.get("status")

        # If provider reports active, upgrade local state to Pro active
        if remote_status == "active":
            plan_repo = PlanRepository(session)
            sub_repo = SubscriptionRepository(session)

            pro_plan = await plan_repo.get_by_name("pro")
            if not pro_plan:
                logger.error("Pro plan not found during reconciliation")
                return False

            period_start = None
            period_end = None
            if "current_start" in provider_data and provider_data["current_start"]:
                period_start = datetime.datetime.fromtimestamp(
                    provider_data["current_start"], datetime.timezone.utc
                )
            if "current_end" in provider_data and provider_data["current_end"]:
                period_end = datetime.datetime.fromtimestamp(
                    provider_data["current_end"], datetime.timezone.utc
                )

            await sub_repo.upgrade_to_plan(
                subscription=sub,
                new_plan_id=pro_plan.id,
                new_status="active",
                period_start=period_start,
                period_end=period_end,
            )
            logger.info(
                "RECONCILED: Subscription %s upgraded to active Pro for tenant %s",
                provider_sub_id,
                sub.tenant_id,
            )
            return True

        elif remote_status in ("paused", "halted", "cancelled"):
            sub_repo = SubscriptionRepository(session)
            await sub_repo.update_status(sub, remote_status)
            logger.info(
                "RECONCILED: Subscription %s status updated to %s",
                provider_sub_id,
                remote_status,
            )
            return False

        return False

    async def run_periodic(
        self,
        interval_seconds: int = 300,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """
        Background loop executing periodic reconciliation sweeps.
        """
        logger.info("Starting background subscription reconciliation loop (interval=%ss)", interval_seconds)
        while True:
            if stop_event and stop_event.is_set():
                logger.info("Reconciliation loop received stop signal. Exiting.")
                break
            try:
                count = await self.reconcile_pending_subscriptions()
                if count > 0:
                    logger.info("Reconciliation sweep completed: %s subscriptions updated.", count)
            except Exception as exc:
                logger.exception("Error during background reconciliation sweep: %s", exc)

            if stop_event:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                    break
                except asyncio.TimeoutError:
                    continue
            else:
                await asyncio.sleep(interval_seconds)
