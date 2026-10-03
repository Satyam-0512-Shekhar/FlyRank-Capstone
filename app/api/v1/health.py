"""
FlyRank Capstone — Health check endpoint.
GET /health — returns application and database status.
"""

import logging
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=None)
async def health_check() -> JSONResponse:
    """
    System health endpoint.
    Verifies FastAPI is running and PostgreSQL is reachable.
    Returns 200 OK if healthy, 503 Service Unavailable if database is unreachable.
    """
    db_status = "disconnected"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        logger.exception("Health check: database unreachable")

    is_healthy = (db_status == "connected")
    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    content: dict[str, Any] = {
        "status": "healthy" if is_healthy else "degraded",
        "database": db_status,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }
    return JSONResponse(status_code=status_code, content=content)

