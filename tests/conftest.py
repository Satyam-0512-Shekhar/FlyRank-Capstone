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

from app.core.database import get_db, Base
import app.models  # noqa: F401
from app.main import app  # noqa: E402
from scripts.seed_data import seed_plans


import tempfile


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def test_session_factory():
    """Isolated database file per test enabling true multi-connection concurrency."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    db_url = f"sqlite+aiosqlite:///{db_path}"

    engine = create_async_engine(
        db_url,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        await seed_plans(session)

    yield session_factory
    await engine.dispose()
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


@pytest_asyncio.fixture
async def db_session(test_session_factory):
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_session_factory):
    """Async HTTP test client with get_db overridden to yield independent sessions."""
    async def _override_get_db():
        async with test_session_factory() as session:
            try:
                yield session
                if session.is_active:
                    await session.commit()
            except Exception:
                if session.is_active:
                    await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
