"""
FlyRank Capstone — Health check endpoint.
GET /health — returns application and database status.
"""

import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """
    System health endpoint.
    Verifies FastAPI is running and PostgreSQL is reachable.
    Returns 200 OK if healthy, 503 if database is unavailable.
    """
    db_status = "disconnected"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        logger.exception("Health check: database unreachable")

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }
