"""
FlyRank Capstone — UsageRepository.
Encapsulates all database operations for immutable usage events with strict tenant scoping.
"""

import datetime
from typing import Sequence
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_event import UsageEvent


class UsageRepository:
    """Repository for querying and recording UsageEvent ledger rows."""

    @classmethod
    async def create(cls, session: AsyncSession, event: UsageEvent) -> UsageEvent:
        """Insert an immutable usage event into the ledger."""
        session.add(event)
        await session.flush()
        return event

    @classmethod
    async def get_period_usage(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
    ) -> tuple[int, int, int]:
        """
        Aggregate total API calls, total tokens, and total cost (in µINR)
        for a tenant within a specific billing window.
        Returns:
            (total_api_calls, total_tokens, total_cost_micro_inr)
        """
        stmt = (
            select(
                func.coalesce(func.sum(UsageEvent.api_calls), 0),
                func.coalesce(func.sum(UsageEvent.total_tokens), 0),
                func.coalesce(func.sum(UsageEvent.cost_micro_inr), 0),
            )
            .where(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.timestamp >= start_time,
                UsageEvent.timestamp <= end_time,
            )
        )
        result = await session.execute(stmt)
        api_calls, total_tokens, total_cost = result.one()
        return int(api_calls), int(total_tokens), int(total_cost)

    @classmethod
    async def get_period_token_breakdown(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
    ) -> dict[str, int]:
        """
        Aggregate token quantities by category for a tenant within a billing window.
        """
        stmt = (
            select(
                func.coalesce(func.sum(UsageEvent.fresh_input_tokens), 0),
                func.coalesce(func.sum(UsageEvent.cached_input_tokens), 0),
                func.coalesce(func.sum(UsageEvent.output_tokens), 0),
                func.coalesce(func.sum(UsageEvent.reasoning_tokens), 0),
            )
            .where(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.timestamp >= start_time,
                UsageEvent.timestamp <= end_time,
            )
        )
        result = await session.execute(stmt)
        fresh, cached, output, reasoning = result.one()
        return {
            "fresh_input_tokens": int(fresh),
            "cached_input_tokens": int(cached),
            "output_tokens": int(output),
            "reasoning_tokens": int(reasoning),
        }

    @classmethod
    async def list_events(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[UsageEvent]:
        """List paginated usage events for a tenant, ordered by timestamp descending."""
        stmt = (
            select(UsageEvent)
            .where(UsageEvent.tenant_id == tenant_id)
            .order_by(UsageEvent.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return result.scalars().all()
