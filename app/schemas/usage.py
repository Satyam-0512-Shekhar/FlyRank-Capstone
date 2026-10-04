"""
FlyRank Capstone — Pydantic Schemas for Usage Metering, AI Generation, and Analytics.
"""

import datetime
import uuid
from pydantic import BaseModel, ConfigDict, Field


class SimulatedTokens(BaseModel):
    """Token breakdown parameters simulating an LLM generation."""
    model_config = ConfigDict(frozen=True)

    fresh_input_tokens: int = Field(default=0, ge=0, description="Fresh input tokens (standard rate)")
    cached_input_tokens: int = Field(default=0, ge=0, description="Cached input tokens (discounted rate)")
    output_tokens: int = Field(default=0, ge=0, description="Output tokens generated")
    reasoning_tokens: int = Field(default=0, ge=0, description="Thinking / reasoning tokens (billed at output rate)")

    @property
    def total_tokens(self) -> int:
        return (
            self.fresh_input_tokens
            + self.cached_input_tokens
            + self.output_tokens
            + self.reasoning_tokens
        )


class GenerateRequest(BaseModel):
    """Request payload for the billable AI generate endpoint."""
    prompt: str = Field(..., min_length=1, max_length=100_000, description="Input prompt for generation")
    model: str = Field(default="gpt-simulated", max_length=100, description="Simulated AI model identifier")
    simulated_tokens: SimulatedTokens = Field(
        default_factory=SimulatedTokens,
        description="Simulated token counts for usage metering",
    )


class MeteringResult(BaseModel):
    """Metering confirmation embedded in the generation response."""
    usage_event_id: uuid.UUID = Field(..., description="Unique immutable usage event ledger ID")
    api_calls_metered: int = Field(default=1, description="Number of API calls metered")
    total_tokens_metered: int = Field(..., description="Sum of all token categories metered")
    cost_micro_inr: int = Field(..., description="Exact operation cost in micro-INR (pure integer)")
    currency: str = Field(default="INR", description="Currency ISO code")
    formatted_cost: str = Field(..., description="Human-readable formatted cost in INR")


class GenerateResponse(BaseModel):
    """Response returned by POST /api/v1/generate."""
    id: str = Field(..., description="Generation execution ID")
    result: str = Field(..., description="Simulated completion text")
    metering: MeteringResult = Field(..., description="Metering attribution details")


class BillingPeriod(BaseModel):
    start: datetime.datetime
    end: datetime.datetime


class ApiCallUsage(BaseModel):
    used: int
    limit: int
    remaining: int


class TokenBreakdown(BaseModel):
    fresh_input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int


class TokenUsage(BaseModel):
    used: int
    limit: int
    remaining: int
    breakdown: TokenBreakdown


class TotalCost(BaseModel):
    micro_inr: int
    formatted: str


class UsageSummaryResponse(BaseModel):
    """Response returned by GET /api/v1/usage."""
    tenant_id: uuid.UUID
    plan: str
    billing_period: BillingPeriod
    api_calls: ApiCallUsage
    ai_tokens: TokenUsage
    total_cost: TotalCost


class UsageEventItem(BaseModel):
    """Single usage event item returned in GET /api/v1/usage/events."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timestamp: datetime.datetime
    usage_type: str
    api_calls: int
    total_tokens: int
    fresh_input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cost_micro_inr: int
    formatted_cost: str
    idempotency_key: str | None = None
