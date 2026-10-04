"""
FlyRank Capstone — Usage Metering & Billing Engine
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import DuplicateWebhookError, FlyRankError

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan Context Manager ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan for startup validation and graceful shutdown."""
    logger.info(
        "FlyRank Billing Engine starting — env=%s version=%s",
        settings.APP_ENV,
        settings.APP_VERSION,
    )
    if settings.APP_ENV != "production" and (
        "placeholder" in settings.RAZORPAY_KEY_SECRET
        or "placeholder" in settings.RAZORPAY_WEBHOOK_SECRET
    ):
        logger.warning(
            "Running with placeholder Razorpay credentials. Webhook verification will use placeholder secret."
        )
    yield
    logger.info("FlyRank Billing Engine shutting down")


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="FlyRank Usage Metering & Billing Engine",
    description=(
        "Multi-tenant API usage metering and billing engine. "
        "Tracks API calls and AI token consumption, enforces quotas, "
        "and integrates Razorpay Test Mode for subscription billing. "
        "Stripe → Razorpay adaptation — see README.md."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── Exception Handlers ───────────────────────────────────────────────────────
@app.exception_handler(DuplicateWebhookError)
async def duplicate_webhook_handler(request: Request, exc: DuplicateWebhookError) -> JSONResponse:
    """
    Handle duplicate webhooks per DESIGN.md §10.2:
    Return 200 OK with {"status": "ignored", "reason": "duplicate_webhook"}
    """
    return JSONResponse(
        status_code=200,
        content={"status": "ignored", "reason": "duplicate_webhook"},
    )


@app.exception_handler(FlyRankError)
async def flyrank_exception_handler(request: Request, exc: FlyRankError) -> JSONResponse:
    """
    Convert all FlyRankError subclasses into consistent structured JSON responses.
    Includes Retry-After header for QuotaExceededError per Probe 2.
    Never leaks stack traces or internal implementation details.
    """
    body: dict[str, Any] = {
        "error": exc.error_code,
        "message": exc.message,
    }
    if exc.details:
        body.update(exc.details)

    headers: dict[str, str] = {}
    retry_after = getattr(exc, "retry_after_seconds", None)
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)

    logger.warning(
        "Domain error %s on %s %s: %s",
        exc.error_code,
        request.method,
        request.url.path,
        exc.message,
    )
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for unexpected errors — returns a generic 500 without leaking details.
    Logs the full traceback for debugging.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "An unexpected error occurred."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
from app.api.v1 import health, tenants  # noqa: E402

app.include_router(health.router, tags=["System"])
app.include_router(tenants.router, prefix="/api/v1")


