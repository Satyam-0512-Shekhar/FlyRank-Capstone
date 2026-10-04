"""
Subscription service handling plan upgrades, provider interaction, and status queries.
"""

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.integrations.payments.base import PaymentProvider
from app.integrations.payments.razorpay import RazorpayProvider
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.billing import CreateSubscriptionResponse, SubscriptionStatusResponse


class SubscriptionService:
    def __init__(
        self,
        session: AsyncSession,
        payment_provider: PaymentProvider | None = None,
    ):
        self.session = session
        self.provider = payment_provider or RazorpayProvider()
        self.plan_repo = PlanRepository(session)
        self.sub_repo = SubscriptionRepository(session)

    async def create_or_upgrade_subscription(
        self,
        tenant_id: uuid.UUID,
        plan_name: str = "pro",
    ) -> CreateSubscriptionResponse:
        """Initiate subscription creation/upgrade with payment gateway."""
        target_plan = await self.plan_repo.get_by_name(plan_name)
        if not target_plan:
            raise NotFoundError(f"Plan '{plan_name}' not found.")

        # Convert micro-INR to paise (10,000 micro-INR = 1 paise, 1,000,000 micro-INR = ₹1 = 100 paise)
        amount_paise = target_plan.price_micro_inr // 10_000

        provider_res = await self.provider.create_subscription(
            plan_id=f"plan_{plan_name}_monthly",
            notes={"tenant_id": str(tenant_id)},
        )

        sub = await self.sub_repo.get_by_tenant_id(tenant_id)
        if not sub:
            sub = await self.sub_repo.create(
                tenant_id=tenant_id,
                plan_id=target_plan.id,
                provider="razorpay",
                status="pending",
            )
            await self.sub_repo.set_provider_subscription_id(
                sub, provider_res["id"], status="pending"
            )
        else:
            await self.sub_repo.set_provider_subscription_id(
                sub, provider_res["id"], status="pending"
            )

        return CreateSubscriptionResponse(
            subscription_id=provider_res["id"],
            provider="razorpay",
            razorpay_key_id=settings.RAZORPAY_KEY_ID,
            plan=plan_name,
            amount_paise=amount_paise,
            currency="INR",
            status="pending",
        )

    async def get_subscription_status(
        self, tenant_id: uuid.UUID
    ) -> SubscriptionStatusResponse:
        """Fetch current tenant subscription status and plan."""
        sub, plan = await self.sub_repo.get_subscription_with_plan(tenant_id)
        if not sub or not plan:
            raise NotFoundError("Subscription not found for tenant.")

        return SubscriptionStatusResponse(
            subscription_id=sub.provider_subscription_id,
            tenant_id=sub.tenant_id,
            plan_name=plan.name,
            status=sub.status,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
        )
