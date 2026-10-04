"""
Pydantic v2 schemas for billing and subscriptions.
"""

import uuid
import datetime
from pydantic import BaseModel, Field


class CreateSubscriptionRequest(BaseModel):
    plan_name: str = Field(default="pro", description="Target plan name to subscribe to")


class CreateSubscriptionResponse(BaseModel):
    subscription_id: str
    provider: str = "razorpay"
    razorpay_key_id: str
    plan: str
    amount_paise: int
    currency: str = "INR"
    status: str


class SubscriptionStatusResponse(BaseModel):
    subscription_id: str | None = None
    tenant_id: uuid.UUID
    plan_name: str
    status: str
    current_period_start: datetime.datetime | None = None
    current_period_end: datetime.datetime | None = None


class WebhookResponse(BaseModel):
    status: str
    reason: str | None = None
