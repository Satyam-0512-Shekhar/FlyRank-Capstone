"""
Plan repository for database access operations.
"""

import uuid
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan


class PlanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_name(self, name: str) -> Plan | None:
        """Fetch a plan by unique canonical name ('free', 'pro')."""
        stmt = select(Plan).where(Plan.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, plan_id: uuid.UUID) -> Plan | None:
        """Fetch a plan by its UUID."""
        stmt = select(Plan).where(Plan.id == plan_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> Sequence[Plan]:
        """List all active plans."""
        stmt = select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.price_micro_inr)
        result = await self.session.execute(stmt)
        return result.scalars().all()
