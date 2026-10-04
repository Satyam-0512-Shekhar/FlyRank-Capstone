"""
FlyRank Capstone — Quota & Budget Guard Service.
Enforces pre-execution dual-quota bounds (API calls & AI tokens) and per-call budget ceilings.
"""

import calendar
import datetime
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BudgetGuardError, QuotaExceededError
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.repositories.usage_repository import UsageRepository


class QuotaService:
    """Pre-execution validation engine for API quotas and budget limits."""

    @classmethod
    async def resolve_billing_period(
        cls,
        session: AsyncSession,
        subscription: Subscription,
    ) -> tuple[datetime.datetime, datetime.datetime]:
        """
        Determine the active billing window for a subscription.
        For Free plans or expired subscriptions, lazily rolls over to the current UTC calendar month.
        """
        now = datetime.datetime.now(datetime.timezone.utc)

        # Make subscription periods tz-aware if they are naive
        period_start = subscription.current_period_start
        period_end = subscription.current_period_end
        if period_start and period_start.tzinfo is None:
            period_start = period_start.replace(tzinfo=datetime.timezone.utc)
        if period_end and period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=datetime.timezone.utc)

        # If period end is in the past, or period is unset, rollover to current UTC calendar month
        if not period_end or period_end < now:
            _, last_day = calendar.monthrange(now.year, now.month)
            new_start = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
            new_end = datetime.datetime(now.year, now.month, last_day, 23, 59, 59, 999999, tzinfo=datetime.timezone.utc)

            subscription.current_period_start = new_start
            subscription.current_period_end = new_end
            await session.flush()
            return new_start, new_end

        return period_start, period_end

    @classmethod
    async def check_quota_and_budget(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        subscription: Subscription,
        plan: Plan,
        requested_tokens: int,
        projected_cost_micro_inr: int,
    ) -> None:
        """
        Evaluate tri-partite pre-execution boundaries per DESIGN.md §8:
        1. Budget Guard (per-call cost limit)
        2. API Call Quota (used + 1 <= limit)
        3. AI Token Quota (used + requested <= limit)

        Raises:
            BudgetGuardError: If projected call cost exceeds per-call ceiling.
            QuotaExceededError: If monthly call or token limits are exceeded.
        """
        # 1. Check per-call budget guard (PDF Requirement #7)
        if (
            plan.max_cost_per_call_micro_inr is not None
            and projected_cost_micro_inr > plan.max_cost_per_call_micro_inr
        ):
            raise BudgetGuardError(
                projected_cost=projected_cost_micro_inr,
                max_allowed=plan.max_cost_per_call_micro_inr,
            )

        # 2. Resolve current billing window
        start_time, end_time = await cls.resolve_billing_period(session, subscription)

        # 3. Aggregate period usage
        used_calls, used_tokens, _ = await UsageRepository.get_period_usage(
            session=session,
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time,
        )

        now = datetime.datetime.now(datetime.timezone.utc)
        retry_after_seconds = max(int((end_time - now).total_seconds()), 1)

        # 4. Check API call quota
        if used_calls + 1 > plan.api_call_quota:
            raise QuotaExceededError(
                quota_dimension="api_calls",
                limit=plan.api_call_quota,
                used=used_calls,
                requested=1,
                retry_after_seconds=retry_after_seconds,
            )

        # 5. Check AI token quota
        if used_tokens + requested_tokens > plan.token_quota:
            raise QuotaExceededError(
                quota_dimension="ai_tokens",
                limit=plan.token_quota,
                used=used_tokens,
                requested=requested_tokens,
                retry_after_seconds=retry_after_seconds,
            )
