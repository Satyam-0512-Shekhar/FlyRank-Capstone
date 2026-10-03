"""
FlyRank Capstone — Usage Metering & Billing Engine
Core configuration via pydantic-settings.

All values are loaded from environment variables / .env file.
NEVER hard-code secrets here.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ─────────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://flyrank:flyrank_secret_change_me@postgres:5432/flyrank_billing"
    )

    # ── Razorpay ─────────────────────────────────────────────────────────
    RAZORPAY_KEY_ID: str = "rzp_test_placeholder"
    RAZORPAY_KEY_SECRET: str = "placeholder_secret"
    RAZORPAY_WEBHOOK_SECRET: str = "placeholder_webhook_secret"

    # ── Pricing constants (micro-INR per token) ──────────────────────────
    # These are PROJECT-DEFINED constants — see DESIGN.md §7.1
    PRICE_FRESH_INPUT_TOKEN_MICRO_INR: int = 40
    PRICE_CACHED_INPUT_TOKEN_MICRO_INR: int = 10
    PRICE_OUTPUT_TOKEN_MICRO_INR: int = 160
    PRICE_REASONING_TOKEN_MICRO_INR: int = 160

    # ── Budget guard (micro-INR per call) ────────────────────────────────
    FREE_MAX_COST_PER_CALL_MICRO_INR: int = 10_000_000   # ₹10.00
    PRO_MAX_COST_PER_CALL_MICRO_INR: int = 100_000_000   # ₹100.00


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
