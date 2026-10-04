"""
Unit tests for TenantService business logic.
"""

import uuid
import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.services.tenant_service import TenantService


@pytest.mark.asyncio
async def test_create_tenant_provisions_free_subscription(db_session):
    """Verify tenant registration provisions an active Free tier subscription."""
    result = await TenantService.create_tenant(db_session, "Initech Corp")

    assert result["name"] == "Initech Corp"
    assert result["plan"] == "free"
    assert isinstance(result["id"], uuid.UUID)

    # Fetch profile to verify subscription association
    profile = await TenantService.get_tenant_profile(db_session, result["id"])
    assert profile["name"] == "Initech Corp"
    assert profile["plan"]["name"] == "free"
    assert profile["plan"]["api_call_quota"] == 1_000
    assert profile["plan"]["token_quota"] == 100_000
    assert profile["plan"]["max_cost_per_call_micro_inr"] == 10_000_000
    assert profile["plan"]["price_micro_inr"] == 0
    assert profile["subscription"]["status"] == "active"
    assert profile["subscription"]["current_period_start"] is not None
    assert profile["subscription"]["current_period_end"] is not None


@pytest.mark.asyncio
async def test_create_tenant_empty_name_raises_validation_error(db_session):
    """Verify empty or whitespace-only names are rejected."""
    with pytest.raises(ValidationError):
        await TenantService.create_tenant(db_session, "   ")

    with pytest.raises(ValidationError):
        await TenantService.create_tenant(db_session, "")


@pytest.mark.asyncio
async def test_get_tenant_profile_non_existent(db_session):
    """Verify querying non-existent tenant ID raises NotFoundError."""
    random_id = uuid.uuid4()
    with pytest.raises(NotFoundError):
        await TenantService.get_tenant_profile(db_session, random_id)
