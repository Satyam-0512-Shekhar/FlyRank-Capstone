"""
Unit tests for plan seeding logic (scripts/seed_data.py).
Tests exact quotas, budget guards, and idempotent re-execution.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.plan import Plan
from scripts.seed_data import seed_plans, FREE_PLAN_ID, PRO_PLAN_ID


@pytest.fixture
async def plan_db_session():
    """Isolated in-memory database session with only the plans table."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Plan.__table__.create)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_plans_creates_canonical_plans(plan_db_session):
    """Verify seed_plans creates Free and Pro plans with exact quotas per DESIGN.md §6 & §8."""
    plans = await seed_plans(plan_db_session)
    assert len(plans) == 2

    # Query directly from DB to verify persistence
    result = await plan_db_session.execute(select(Plan).order_by(Plan.name))
    stored_plans = {p.name: p for p in result.scalars().all()}

    assert "free" in stored_plans
    assert "pro" in stored_plans

    free = stored_plans["free"]
    assert free.id == FREE_PLAN_ID
    assert free.api_call_quota == 1_000
    assert free.token_quota == 100_000
    assert free.max_cost_per_call_micro_inr == 10_000_000  # ₹10.00 ceiling
    assert free.price_micro_inr == 0
    assert free.currency == "INR"
    assert free.billing_interval == "month"
    assert free.is_active is True

    pro = stored_plans["pro"]
    assert pro.id == PRO_PLAN_ID
    assert pro.api_call_quota == 50_000
    assert pro.token_quota == 5_000_000
    assert pro.max_cost_per_call_micro_inr == 100_000_000  # ₹100.00 ceiling
    assert pro.price_micro_inr == 1_999_000_000  # ₹1,999.00
    assert pro.currency == "INR"
    assert pro.billing_interval == "month"
    assert pro.is_active is True


@pytest.mark.asyncio
async def test_seed_plans_is_idempotent(plan_db_session):
    """Verify running seed_plans multiple times does not duplicate plans or error."""
    # Run 1
    await seed_plans(plan_db_session)

    # Run 2
    plans_second_run = await seed_plans(plan_db_session)
    assert len(plans_second_run) == 2

    # Ensure still exactly 2 plans in the database
    result = await plan_db_session.execute(select(Plan))
    all_plans = result.scalars().all()
    assert len(all_plans) == 2
