"""
Integration tests for Billing API endpoints (/api/v1/billing/subscription).
"""

import pytest
from httpx import AsyncClient
from app.repositories.tenant_repository import TenantRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository


@pytest.mark.asyncio
async def test_billing_requires_tenant_header(client):
    res = await client.post(
        "/api/v1/billing/subscription",
        json={"plan_name": "pro"},
    )
    assert res.status_code == 400
    assert res.json()["error"] == "validation_error"


@pytest.mark.asyncio
async def test_create_and_get_subscription(client, test_session_factory):
    # Setup tenant on free tier
    async with test_session_factory() as session:
        tenant_repo = TenantRepository(session)
        plan_repo = PlanRepository(session)
        sub_repo = SubscriptionRepository(session)

        tenant = await tenant_repo.create("Billing API Test Tenant")
        free_plan = await plan_repo.get_by_name("free")
        await sub_repo.create(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            status="active",
        )
        await session.commit()
        tenant_id = str(tenant.id)

    # 1. Initiate upgrade to Pro
    post_res = await client.post(
        "/api/v1/billing/subscription",
        headers={"X-Tenant-ID": tenant_id},
        json={"plan_name": "pro"},
    )
    assert post_res.status_code == 201
    data = post_res.json()
    assert data["plan"] == "pro"
    assert data["provider"] == "razorpay"
    assert data["amount_paise"] == 199900
    assert data["currency"] == "INR"
    assert data["subscription_id"].startswith("sub_")

    # 2. Get subscription status
    get_res = await client.get(
        "/api/v1/billing/subscription",
        headers={"X-Tenant-ID": tenant_id},
    )
    assert get_res.status_code == 200
    status_data = get_res.json()
    assert status_data["tenant_id"] == tenant_id
    assert status_data["subscription_id"] == data["subscription_id"]
    assert status_data["status"] == "pending"


@pytest.mark.asyncio
async def test_create_subscription_invalid_plan(client, test_session_factory):
    async with test_session_factory() as session:
        tenant_repo = TenantRepository(session)
        tenant = await tenant_repo.create("Invalid Plan Tenant")
        await session.commit()
        tenant_id = str(tenant.id)

    res = await client.post(
        "/api/v1/billing/subscription",
        headers={"X-Tenant-ID": tenant_id},
        json={"plan_name": "non_existent_tier"},
    )
    assert res.status_code == 404
    assert res.json()["error"] == "not_found"
