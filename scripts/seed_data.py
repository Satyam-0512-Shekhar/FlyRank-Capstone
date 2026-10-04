"""
FlyRank Capstone — Database Seeding Script.
Seeds canonical Free and Pro plans with exact quotas and micro-INR rates per DESIGN.md §6 & §8.
Idempotent: safe to run multiple times.
"""

import asyncio
import logging
import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.plan import Plan

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FREE_PLAN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PRO_PLAN_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")

CANONICAL_PLANS = [
    {
        "id": FREE_PLAN_ID,
        "name": "free",
        "api_call_quota": 1_000,
        "token_quota": 100_000,
        "max_cost_per_call_micro_inr": 10_000_000,  # ₹10.00
        "price_micro_inr": 0,
        "currency": "INR",
        "billing_interval": "month",
        "is_active": True,
    },
    {
        "id": PRO_PLAN_ID,
        "name": "pro",
        "api_call_quota": 50_000,
        "token_quota": 5_000_000,
        "max_cost_per_call_micro_inr": 100_000_000,  # ₹100.00
        "price_micro_inr": 1_999_000_000,  # ₹1,999.00
        "currency": "INR",
        "billing_interval": "month",
        "is_active": True,
    },
]


async def seed_plans(session: AsyncSession) -> list[Plan]:
    """
    Seed or update the canonical Free and Pro plans.
    Idempotent operation.
    """
    seeded_plans: list[Plan] = []
    for plan_data in CANONICAL_PLANS:
        stmt = select(Plan).where(Plan.name == plan_data["name"])
        result = await session.execute(stmt)
        existing_plan = result.scalar_one_or_none()

        if existing_plan:
            logger.info("Plan '%s' already exists (id=%s). Updating parameters...", plan_data["name"], existing_plan.id)
            existing_plan.api_call_quota = plan_data["api_call_quota"]
            existing_plan.token_quota = plan_data["token_quota"]
            existing_plan.max_cost_per_call_micro_inr = plan_data["max_cost_per_call_micro_inr"]
            existing_plan.price_micro_inr = plan_data["price_micro_inr"]
            existing_plan.currency = plan_data["currency"]
            existing_plan.billing_interval = plan_data["billing_interval"]
            existing_plan.is_active = plan_data["is_active"]
            seeded_plans.append(existing_plan)
        else:
            logger.info("Creating plan '%s' (id=%s)...", plan_data["name"], plan_data["id"])
            new_plan = Plan(**plan_data)
            session.add(new_plan)
            seeded_plans.append(new_plan)

    await session.commit()
    logger.info("Successfully seeded %d plans.", len(seeded_plans))
    return seeded_plans


async def main() -> None:
    logger.info("Starting database plan seed...")
    async with AsyncSessionLocal() as session:
        await seed_plans(session)
    logger.info("Plan seeding complete.")


if __name__ == "__main__":
    asyncio.run(main())
