"""
Unit tests for configuration loading and validation.
Includes regression test for BUG-009.
"""

import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_settings_ignores_extra_environment_variables():
    """
    Critical finding regression test:
    Settings must not fail when extra environment variables (e.g. POSTGRES_USER) exist.
    """
    settings = Settings(
        POSTGRES_USER="extra_user",
        POSTGRES_HOST="extra_host",
        SOME_UNEXPECTED_VAR="unexpected",
    )
    assert settings.APP_ENV in ["development", "testing", "production"]


def test_settings_production_rejects_placeholder_credentials():
    """
    Regression test for BUG-009:
    In production mode, placeholder Razorpay credentials must be rejected.
    """
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            APP_ENV="production",
            RAZORPAY_KEY_SECRET="placeholder_secret",
            RAZORPAY_WEBHOOK_SECRET="placeholder_webhook_secret",
        )
    assert "Production environment cannot use placeholder Razorpay credentials" in str(
        excinfo.value
    )


def test_pricing_constants():
    """Verify micro-INR pricing constants match DESIGN.md §7.1."""
    settings = Settings()
    assert settings.PRICE_FRESH_INPUT_TOKEN_MICRO_INR == 40
    assert settings.PRICE_CACHED_INPUT_TOKEN_MICRO_INR == 10
    assert settings.PRICE_OUTPUT_TOKEN_MICRO_INR == 160
    assert settings.PRICE_REASONING_TOKEN_MICRO_INR == 160
