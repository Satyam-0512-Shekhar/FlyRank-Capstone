"""
Unit / integration tests for GET /health endpoint.
Includes regression test for BUG-006 (returns 503 when DB unreachable).
"""

from unittest.mock import AsyncMock, patch
import pytest


@pytest.mark.asyncio
async def test_health_check_healthy(client):
    """When DB is reachable, health check returns 200 OK and healthy status."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=True)

    with patch("app.api.v1.health.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_health_check_db_failure_returns_503(client):
    """
    Regression test for BUG-006:
    When PostgreSQL is unreachable, /health MUST return 503 Service Unavailable,
    not 200 OK with degraded status.
    """
    with patch("app.api.v1.health.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.side_effect = ConnectionRefusedError(
            "DB connection failed"
        )
        response = await client.get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "disconnected"
