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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.main import app  # noqa: E402
from app.models.tenant import Tenant
from app.models.plan import Plan
from app.models.subscription import Subscription
from scripts.seed_data import seed_plans


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def db_session():
    """Isolated in-memory database with Tenant, Plan, and Subscription tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Tenant.__table__.create)
        await conn.run_sync(Plan.__table__.create)
        await conn.run_sync(Subscription.__table__.create)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        await seed_plans(session)
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    """Async HTTP test client with get_db overridden to use in-memory database."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
