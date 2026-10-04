"""
FlyRank Capstone — Deterministic AI Token Pricing & Cost Engine.
Calculates token costs in canonical micro-INR (µINR) using pure integer arithmetic.
Zero floating-point rounding errors.
"""

from app.core.config import settings


class PricingService:
    """
    Deterministic AI token pricing service.
    Implements pure-multiplication integer arithmetic per DESIGN.md §7.
    """

    @classmethod
    def calculate_token_cost(
        cls,
        fresh_input_tokens: int,
        cached_input_tokens: int,
        output_tokens: int,
        reasoning_tokens: int,
    ) -> int:
        """
        Calculate total cost in canonical micro-INR (µINR).

        Formula:
            Cost_µINR = (N_fresh * 40) + (N_cached * 10) + ((N_output + N_reasoning) * 160)

        Raises:
            ValueError: If any token count is negative.
        """
        if (
            fresh_input_tokens < 0
            or cached_input_tokens < 0
            or output_tokens < 0
            or reasoning_tokens < 0
        ):
            raise ValueError("Token counts cannot be negative.")

        fresh_cost = fresh_input_tokens * settings.PRICE_FRESH_INPUT_TOKEN_MICRO_INR
        cached_cost = cached_input_tokens * settings.PRICE_CACHED_INPUT_TOKEN_MICRO_INR
        output_cost = output_tokens * settings.PRICE_OUTPUT_TOKEN_MICRO_INR
        reasoning_cost = reasoning_tokens * settings.PRICE_REASONING_TOKEN_MICRO_INR

        total_micro_inr = fresh_cost + cached_cost + output_cost + reasoning_cost
        return total_micro_inr

    @classmethod
    def format_micro_inr(cls, amount_micro_inr: int) -> str:
        """
        Format canonical micro-INR to standard currency string (e.g. ₹0.17 or ₹1999.00).
        """
        inr_float = amount_micro_inr / 1_000_000
        return f"₹{inr_float:.2f}"
