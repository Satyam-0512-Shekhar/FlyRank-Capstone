"""
FlyRank Capstone — Unit tests for AI Token Pricing & Cost Engine.
Verifies integer micro-INR arithmetic, zero float drift, and pricing constants.
"""

import pytest
from app.services.pricing_service import PricingService
from app.core.config import settings


def test_pricing_constants_pinned():
    """Verify rates match DESIGN.md §7.1 exactly."""
    assert settings.PRICE_FRESH_INPUT_TOKEN_MICRO_INR == 40
    assert settings.PRICE_CACHED_INPUT_TOKEN_MICRO_INR == 10
    assert settings.PRICE_OUTPUT_TOKEN_MICRO_INR == 160
    assert settings.PRICE_REASONING_TOKEN_MICRO_INR == 160


def test_calculate_token_cost_probe5_exact():
    """Probe 5 formula: 1000 fresh, 2000 cached, 500 output, 200 reasoning = 172,000 micro-INR."""
    cost = PricingService.calculate_token_cost(
        fresh_input_tokens=1000,
        cached_input_tokens=2000,
        output_tokens=500,
        reasoning_tokens=200,
    )
    # (1000 * 40) + (2000 * 10) + (500 * 160) + (200 * 160) = 40000 + 20000 + 80000 + 32000 = 172000
    assert cost == 172_000
    assert isinstance(cost, int)


def test_zero_tokens_costs_zero():
    """Zero tokens across all categories must cost 0 micro-INR."""
    cost = PricingService.calculate_token_cost(0, 0, 0, 0)
    assert cost == 0
    assert isinstance(cost, int)


def test_cached_input_is_75_percent_discount():
    """Cached input rate (10) must be 75% cheaper than fresh input rate (40)."""
    fresh_cost = PricingService.calculate_token_cost(1000, 0, 0, 0)
    cached_cost = PricingService.calculate_token_cost(0, 1000, 0, 0)
    assert fresh_cost == 40_000
    assert cached_cost == 10_000
    assert cached_cost * 4 == fresh_cost


def test_reasoning_rate_equals_output_rate():
    """Reasoning tokens must be priced at identical rate to output tokens (160 micro-INR)."""
    output_cost = PricingService.calculate_token_cost(0, 0, 1000, 0)
    reasoning_cost = PricingService.calculate_token_cost(0, 0, 0, 1000)
    assert output_cost == 160_000
    assert reasoning_cost == 160_000
    assert output_cost == reasoning_cost


def test_negative_tokens_raise_value_error():
    """Negative token counts must be rejected with ValueError."""
    with pytest.raises(ValueError, match="cannot be negative"):
        PricingService.calculate_token_cost(-1, 0, 0, 0)
    with pytest.raises(ValueError, match="cannot be negative"):
        PricingService.calculate_token_cost(0, -5, 0, 0)
    with pytest.raises(ValueError, match="cannot be negative"):
        PricingService.calculate_token_cost(0, 0, -10, 0)
    with pytest.raises(ValueError, match="cannot be negative"):
        PricingService.calculate_token_cost(0, 0, 0, -1)


def test_format_micro_inr():
    """Test standard micro-INR formatting to INR currency strings."""
    assert PricingService.format_micro_inr(0) == "₹0.00"
    assert PricingService.format_micro_inr(172_000) == "₹0.17"
    assert PricingService.format_micro_inr(1_000_000) == "₹1.00"
    assert PricingService.format_micro_inr(1_999_000_000) == "₹1999.00"
