"""
FastAPI dependency injection utilities for authentication, tenant resolution, and database sessions.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.models.tenant import Tenant
from app.repositories.tenant_repository import TenantRepository


async def get_current_tenant(
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
    session: AsyncSession = Depends(get_db),
) -> Tenant:
    """
    Authenticate and resolve the current tenant from the X-Tenant-ID header.
    Returns the Tenant domain model or raises ValidationError (400) / NotFoundError (404).
    """
    if not x_tenant_id:
        raise ValidationError("Missing required header: X-Tenant-ID")

    try:
        tenant_uuid = uuid.UUID(x_tenant_id)
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid UUID format for X-Tenant-ID: '{x_tenant_id}'")

    tenant_repo = TenantRepository(session)
    tenant = await tenant_repo.get_by_id(tenant_uuid)
    if not tenant:
        raise NotFoundError(f"Tenant with ID '{x_tenant_id}' not found.")

    return tenant
