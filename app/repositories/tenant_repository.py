"""
Tenant repository for database access operations.
"""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant


class TenantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, name: str) -> Tenant:
        """Create and persist a new Tenant record."""
        tenant = Tenant(name=name)
        self.session.add(tenant)
        await self.session.flush()
        return tenant

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        """Fetch a tenant by its UUID."""
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Tenant | None:
        """Fetch a tenant by name."""
        stmt = select(Tenant).where(Tenant.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
