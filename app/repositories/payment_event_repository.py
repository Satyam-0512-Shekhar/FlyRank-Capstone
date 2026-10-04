"""
PaymentEvent repository for database operations on incoming payment webhooks.
"""

import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.payment_event import PaymentEvent


class PaymentEventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_provider_event_id(
        self, provider: str, provider_event_id: str
    ) -> PaymentEvent | None:
        """Fetch payment event by provider and provider_event_id."""
        stmt = select(PaymentEvent).where(
            PaymentEvent.provider == provider,
            PaymentEvent.provider_event_id == provider_event_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        provider: str,
        provider_event_id: str,
        event_type: str,
        payload_hash: str,
        raw_payload: dict,
        status: str = "processed",
        error_message: str | None = None,
        processed_at: datetime.datetime | None = None,
    ) -> PaymentEvent:
        """Create and persist a PaymentEvent record."""
        event = PaymentEvent(
            provider=provider,
            provider_event_id=provider_event_id,
            event_type=event_type,
            payload_hash=payload_hash,
            raw_payload=raw_payload,
            status=status,
            error_message=error_message,
            processed_at=processed_at or datetime.datetime.now(datetime.timezone.utc),
        )
        self.session.add(event)
        await self.session.flush()
        return event
