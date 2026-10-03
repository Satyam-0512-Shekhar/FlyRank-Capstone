"""UsageEvent model — full schema defined in Phase 3."""
import uuid
import datetime
from sqlalchemy import String, BigInteger, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usage_type: Mapped[str] = mapped_column(String(50), nullable=False, default="generate")
    api_calls: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    total_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    fresh_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_micro_inr: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False, index=True
    )
