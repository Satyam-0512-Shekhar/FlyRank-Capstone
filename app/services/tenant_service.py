"""
Tenant service for tenant onboarding, plan assignment, and profile retrieval.
"""

import calendar
import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.tenant import Tenant
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.tenant_repository import TenantRepository
from scripts.seed_data import seed_plans


class TenantService:
    @staticmethod
    def get_current_calendar_month_period() -> tuple[datetime.datetime, datetime.datetime]:
        """Compute the UTC calendar-month period for Free tier billing."""
        now = datetime.datetime.now(datetime.timezone.utc)
        start = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        _, last_day = calendar.monthrange(now.year, now.month)
        end = datetime.datetime(
            now.year, now.month, last_day, 23, 59, 59, 999999, tzinfo=datetime.timezone.utc
        )
        return start, end

    @classmethod
    async def create_tenant(cls, session: AsyncSession, name: str) -> dict:
        """
        Register a new tenant and automatically provision an active Free tier subscription.
        Guarantees 1 subscription row per tenant.
        """
        clean_name = name.strip()
        if not clean_name:
            raise ValidationError("Tenant name cannot be empty or whitespace.")

        plan_repo = PlanRepository(session)
        tenant_repo = TenantRepository(session)
        sub_repo = SubscriptionRepository(session)

        # Ensure canonical plans exist
        free_plan = await plan_repo.get_by_name("free")
        if not free_plan:
            await seed_plans(session)
            free_plan = await plan_repo.get_by_name("free")
            if not free_plan:
                raise NotFoundError("Failed to locate default Free plan.")

        # Create Tenant
        tenant = await tenant_repo.create(name=clean_name)

        # Compute calendar month window for initial Free subscription
        start, end = cls.get_current_calendar_month_period()

        # Provision Free subscription
        await sub_repo.create(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            provider="razorpay",
            status="active",
            current_period_start=start,
            current_period_end=end,
        )

        return {
            "id": tenant.id,
            "name": tenant.name,
            "plan": free_plan.name,
            "created_at": tenant.created_at,
        }

    @staticmethod
    async def get_tenant_profile(session: AsyncSession, tenant_id: uuid.UUID) -> dict:
        """
        Retrieve tenant profile, active subscription status, and plan details.
        """
        tenant_repo = TenantRepository(session)
        sub_repo = SubscriptionRepository(session)

        tenant = await tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundError(f"Tenant with ID '{tenant_id}' not found.")

        subscription, plan = await sub_repo.get_subscription_with_plan(tenant_id)
        if not subscription or not plan:
            raise NotFoundError(f"Active subscription or plan not found for tenant '{tenant_id}'.")

        # Format price in standard currency display string (e.g., ₹0.00 or ₹1999.00)
        formatted_price = f"₹{plan.price_micro_inr / 1_000_000:.2f}"

        return {
            "id": tenant.id,
            "name": tenant.name,
            "plan": {
                "id": plan.id,
                "name": plan.name,
                "api_call_quota": plan.api_call_quota,
                "token_quota": plan.token_quota,
                "max_cost_per_call_micro_inr": plan.max_cost_per_call_micro_inr,
                "price_micro_inr": plan.price_micro_inr,
                "currency": plan.currency,
                "billing_interval": plan.billing_interval,
                "formatted_price": formatted_price,
            },
            "subscription": {
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
            },
            "created_at": tenant.created_at,
        }
