"""
Unit tests for domain exception handlers and HTTP responses.
Includes regression tests for BUG-007 and BUG-011.
"""

from fastapi import APIRouter
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.exceptions import (
    DuplicateWebhookError,
    IdempotencyConflictError,
    QuotaExceededError,
    BudgetGuardError,
    PaymentRequiredError,
)

dummy_router = APIRouter(prefix="/test-errors")


@dummy_router.get("/quota-exceeded")
async def trigger_quota():
    raise QuotaExceededError(
        quota_dimension="api_calls",
        limit=1000,
        used=1000,
        requested=1,
        retry_after_seconds=3600,
    )


@dummy_router.get("/duplicate-webhook")
async def trigger_duplicate():
    raise DuplicateWebhookError()


@dummy_router.get("/idempotency-conflict")
async def trigger_conflict():
    raise IdempotencyConflictError()


@dummy_router.get("/budget-guard")
async def trigger_budget():
    raise BudgetGuardError(projected_cost=15000000, max_allowed=10000000)


@dummy_router.get("/payment-required")
async def trigger_payment_required():
    raise PaymentRequiredError()


app.include_router(dummy_router)



@pytest.mark.asyncio
async def test_quota_exceeded_header_and_body():
    """
    Regression test for BUG-011:
    QuotaExceededError must set Retry-After HTTP header and return status 429.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/test-errors/quota-exceeded")

    assert response.status_code == 429
    assert response.headers.get("Retry-After") == "3600"
    data = response.json()
    assert data["error"] == "quota_exceeded"
    assert data["quota_dimension"] == "api_calls"
    assert data["limit"] == 1000
    assert data["used"] == 1000


@pytest.mark.asyncio
async def test_duplicate_webhook_format():
    """
    Regression test for BUG-007:
    DuplicateWebhookError must return 200 OK with {"status": "ignored", "reason": "duplicate_webhook"}.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/test-errors/duplicate-webhook")

    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ignored", "reason": "duplicate_webhook"}


@pytest.mark.asyncio
async def test_idempotency_conflict():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/test-errors/idempotency-conflict")

    assert response.status_code == 409
    data = response.json()
    assert data["error"] == "idempotency_conflict"


@pytest.mark.asyncio
async def test_budget_guard():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/test-errors/budget-guard")

    assert response.status_code == 429
    data = response.json()
    assert data["error"] == "budget_guard_exceeded"
    assert data["projected_cost_micro_inr"] == 15000000
