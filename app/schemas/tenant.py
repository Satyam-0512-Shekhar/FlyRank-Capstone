"""
Pydantic schemas for Tenant requests and responses.
"""

import datetime
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.plan import PlanSummary


class TenantCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Organisation or tenant name",
        examples=["Acme Corp"],
    )


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    plan: str
    created_at: datetime.datetime


class SubscriptionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    current_period_start: datetime.datetime | None = None
    current_period_end: datetime.datetime | None = None


class TenantProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    plan: PlanSummary
    subscription: SubscriptionSummary
    created_at: datetime.datetime
