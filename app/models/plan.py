"""Plan model — full schema defined in Phase 3."""
import uuid
from sqlalchemy import String, BigInteger, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import datetime


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    api_call_quota: Mapped[int] = mapped_column(BigInteger, nullable=False)
    token_quota: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_cost_per_call_micro_inr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_micro_inr: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    billing_interval: Mapped[str] = mapped_column(String(20), nullable=False, default="month")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now(), nullable=False)
