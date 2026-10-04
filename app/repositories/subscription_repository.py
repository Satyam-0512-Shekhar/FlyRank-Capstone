"""
Subscription repository for database access operations.
"""

import datetime
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.subscription import Subscription
from app.models.plan import Plan


class SubscriptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        tenant_id: uuid.UUID,
        plan_id: uuid.UUID,
        provider: str = "razorpay",
        status: str = "active",
        current_period_start: datetime.datetime | None = None,
        current_period_end: datetime.datetime | None = None,
    ) -> Subscription:
        """Create and persist a new Subscription record."""
        subscription = Subscription(
            tenant_id=tenant_id,
            plan_id=plan_id,
            provider=provider,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
        )
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def get_by_tenant_id(self, tenant_id: uuid.UUID) -> Subscription | None:
        """Fetch subscription record for a tenant."""
        stmt = select(Subscription).where(Subscription.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_subscription_with_plan(
        self, tenant_id: uuid.UUID
    ) -> tuple[Subscription | None, Plan | None]:
        """Fetch subscription and joined plan for a tenant."""
        stmt = (
            select(Subscription, Plan)
            .join(Plan, Subscription.plan_id == Plan.id)
            .where(Subscription.tenant_id == tenant_id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if not row:
            return None, None
        return row[0], row[1]

    async def get_by_provider_subscription_id(
        self, provider_subscription_id: str
    ) -> Subscription | None:
        """Fetch subscription by payment provider subscription ID."""
        stmt = select(Subscription).where(
            Subscription.provider_subscription_id == provider_subscription_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_provider_subscription_id(
        self,
        subscription: Subscription,
        provider_subscription_id: str,
        status: str = "pending",
    ) -> Subscription:
        """Attach a provider subscription ID and set status."""
        subscription.provider_subscription_id = provider_subscription_id
        subscription.status = status
        await self.session.flush()
        return subscription

    async def update_status(
        self,
        subscription: Subscription,
        new_status: str,
    ) -> Subscription:
        """Update subscription status."""
        subscription.status = new_status
        await self.session.flush()
        return subscription

    async def upgrade_to_plan(
        self,
        subscription: Subscription,
        new_plan_id: uuid.UUID,
        new_status: str = "active",
        period_start: datetime.datetime | None = None,
        period_end: datetime.datetime | None = None,
    ) -> Subscription:
        """Upgrade subscription plan and activate."""
        subscription.plan_id = new_plan_id
        subscription.status = new_status
        if period_start is not None:
            subscription.current_period_start = period_start
        if period_end is not None:
            subscription.current_period_end = period_end
        await self.session.flush()
        return subscription
