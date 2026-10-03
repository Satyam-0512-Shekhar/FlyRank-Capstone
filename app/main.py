"""
FlyRank Capstone — Usage Metering & Billing Engine
FastAPI application entry point.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import FlyRankError

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

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
)


# ── Global Exception Handler ─────────────────────────────────────────────────
@app.exception_handler(FlyRankError)
async def flyrank_exception_handler(request: Request, exc: FlyRankError) -> JSONResponse:
    """
    Convert all FlyRankError subclasses into consistent structured JSON responses.
    Never leaks stack traces or internal implementation details.
    """
    body: dict = {
        "error": exc.error_code,
        "message": exc.message,
    }
    if exc.details:
        body.update(exc.details)

    logger.warning(
        "Domain error %s on %s %s: %s",
        exc.error_code,
        request.method,
        request.url.path,
        exc.message,
    )
    return JSONResponse(status_code=exc.status_code, content=body)


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


# ── Routers (imported lazily to avoid circular imports at startup) ─────────────
from app.api.v1 import health  # noqa: E402

app.include_router(health.router, tags=["System"])


# ── Startup event ─────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup() -> None:
    logger.info(
        "FlyRank Billing Engine starting — env=%s version=%s",
        settings.APP_ENV,
        settings.APP_VERSION,
    )
