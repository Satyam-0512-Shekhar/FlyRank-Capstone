"""
Pydantic schemas for Plan domain models.
"""

import uuid
from pydantic import BaseModel, ConfigDict


class PlanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    api_call_quota: int
    token_quota: int
    max_cost_per_call_micro_inr: int
    price_micro_inr: int
    currency: str
    billing_interval: str
    formatted_price: str
