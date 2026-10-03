"""
FlyRank Capstone — Shared Pytest Fixtures & Test Setup.
"""

import os
import pytest
from httpx import AsyncClient, ASGITransport

# Set environment variables for testing before importing settings or app
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://flyrank:test_pass@localhost:5432/flyrank_test"
os.environ["RAZORPAY_KEY_ID"] = "rzp_test_testkey123"
os.environ["RAZORPAY_KEY_SECRET"] = "test_key_secret_abc"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "test_webhook_secret_xyz"

import pytest_asyncio

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client bound to FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

