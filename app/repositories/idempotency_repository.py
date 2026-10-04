"""
FlyRank Capstone — IdempotencyRepository.
Handles lookup and persistence of idempotency cache records with tenant scoping.
"""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.idempotency import IdempotencyRecord


class IdempotencyRepository:
    """Repository for querying and creating IdempotencyRecord rows."""

    @classmethod
    async def get(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        idempotency_key: str,
    ) -> IdempotencyRecord | None:
        """
        Fetch idempotency record for a specific tenant and idempotency key.
        Strict tenant scoping enforced.
        """
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        record: IdempotencyRecord,
    ) -> IdempotencyRecord:
        """Persist a new idempotency record."""
        session.add(record)
        await session.flush()
        return record
