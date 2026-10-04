"""
Unit tests for PaymentProvider and RazorpayProvider.
"""

import pytest
from app.integrations.payments.base import PaymentProvider
from app.integrations.payments.razorpay import RazorpayProvider


@pytest.mark.asyncio
async def test_razorpay_provider_interface():
    provider = RazorpayProvider()
    assert isinstance(provider, PaymentProvider)


@pytest.mark.asyncio
async def test_create_subscription_mock_mode():
    provider = RazorpayProvider(mock_mode=True)
    res = await provider.create_subscription(
        plan_id="plan_pro_monthly",
        customer_id="cust_123",
        total_count=12,
        notes={"tenant_id": "test-tenant"},
    )
    assert res["entity"] == "subscription"
    assert res["id"].startswith("sub_")
    assert res["status"] == "created"
    assert res["plan_id"] == "plan_pro_monthly"
    assert res["notes"]["tenant_id"] == "test-tenant"


@pytest.mark.asyncio
async def test_fetch_subscription_mock_mode():
    provider = RazorpayProvider(mock_mode=True)
    sub = await provider.fetch_subscription("sub_test123")
    assert sub["id"] == "sub_test123"
    assert sub["entity"] == "subscription"
    assert sub["status"] in ("created", "active")


@pytest.mark.asyncio
async def test_cancel_subscription_mock_mode():
    provider = RazorpayProvider(mock_mode=True)
    res = await provider.cancel_subscription("sub_test123")
    assert res["id"] == "sub_test123"
    assert res["status"] == "cancelled"
