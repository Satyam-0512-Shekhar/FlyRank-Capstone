"""
FlyRank Capstone — Unit tests for usage schemas.
"""

import uuid
from pydantic import ValidationError
import pytest

from app.schemas.usage import (
    SimulatedTokens,
    GenerateRequest,
    MeteringResult,
    GenerateResponse,
    UsageSummaryResponse,
    UsageEventItem,
)


def test_simulated_tokens_valid():
    tokens = SimulatedTokens(
        fresh_input_tokens=1000,
        cached_input_tokens=500,
        output_tokens=200,
        reasoning_tokens=50,
    )
    assert tokens.fresh_input_tokens == 1000
    assert tokens.cached_input_tokens == 500
    assert tokens.total_tokens == 1750


def test_simulated_tokens_negative_fails():
    with pytest.raises(ValidationError):
        SimulatedTokens(fresh_input_tokens=-1)


def test_generate_request_valid():
    req = GenerateRequest(
        prompt="Explain quantum physics",
        model="gpt-simulated",
        simulated_tokens=SimulatedTokens(
            fresh_input_tokens=100,
            cached_input_tokens=0,
            output_tokens=50,
            reasoning_tokens=0,
        ),
    )
    assert req.prompt == "Explain quantum physics"
    assert req.model == "gpt-simulated"
    assert req.simulated_tokens.total_tokens == 150


def test_generate_request_empty_prompt_fails():
    with pytest.raises(ValidationError):
        GenerateRequest(
            prompt="",
            simulated_tokens=SimulatedTokens(),
        )


def test_metering_result_schema():
    event_id = uuid.uuid4()
    result = MeteringResult(
        usage_event_id=event_id,
        api_calls_metered=1,
        total_tokens_metered=3700,
        cost_micro_inr=172000,
        currency="INR",
        formatted_cost="₹0.17",
    )
    assert result.usage_event_id == event_id
    assert result.cost_micro_inr == 172000
