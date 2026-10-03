"""
Unit tests for database session dependency.
Includes regression test for BUG-005 (get_db commits on success).
"""

from unittest.mock import AsyncMock, patch
import pytest
from app.core.database import get_db


@pytest.mark.asyncio
async def test_get_db_commits_on_success():
    """
    Regression test for BUG-005:
    When the request finishes cleanly, get_db() MUST call session.commit()
    so mutations are persisted to PostgreSQL.
    """
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.close = AsyncMock()

    with patch("app.core.database.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session

        gen = get_db()
        session = await gen.asend(None)
        assert session is mock_session

        # Simulate route completing successfully
        with pytest.raises(StopAsyncIteration):
            await gen.asend(None)

        mock_session.commit.assert_awaited_once()
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_rolls_back_on_error():
    """
    Regression test for BUG-005:
    When an exception occurs during request execution, get_db() MUST call
    session.rollback() before closing.
    """
    mock_session = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()

    with patch("app.core.database.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session

        gen = get_db()
        session = await gen.asend(None)
        assert session is mock_session

        # Simulate route throwing an exception
        with pytest.raises(ValueError):
            await gen.athrow(ValueError("Simulated route crash"))

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_inactive_session_does_not_commit_or_rollback():
    """Verify that if the session is no longer active, commit/rollback is skipped."""
    mock_session = AsyncMock()
    mock_session.is_active = False
    mock_session.commit = AsyncMock()
    mock_session.close = AsyncMock()

    with patch("app.core.database.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session

        gen = get_db()
        session = await gen.asend(None)
        assert session is mock_session

        with pytest.raises(StopAsyncIteration):
            await gen.asend(None)

        mock_session.commit.assert_not_awaited()
        mock_session.close.assert_awaited_once()

