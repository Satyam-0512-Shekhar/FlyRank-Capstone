"""
Tenant management and profile endpoints.
"""

import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant
from app.core.database import get_db
from app.core.exceptions import ForbiddenError
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantProfileResponse, TenantResponse
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TenantResponse,
    summary="Register a new tenant",
)
async def create_tenant(
    payload: TenantCreate,
    session: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """
    Register a new tenant organisation and automatically provision an active Free subscription.
    """
    result = await TenantService.create_tenant(session, payload.name)
    return TenantResponse(**result)


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=TenantProfileResponse,
    summary="Get current tenant profile and active plan",
)
async def get_my_profile(
    current_tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> TenantProfileResponse:
    """
    Retrieve authenticated tenant profile, active plan quotas, and subscription details.
    """
    profile = await TenantService.get_tenant_profile(session, current_tenant.id)
    return TenantProfileResponse(**profile)


@router.get(
    "/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=TenantProfileResponse,
    summary="Get tenant by ID with cross-tenant IDOR protection",
)
async def get_tenant_by_id(
    tenant_id: uuid.UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> TenantProfileResponse:
    """
    Retrieve tenant by ID. Enforces strict tenant isolation:
    Returns 403 Forbidden if requesting a tenant ID other than authenticated X-Tenant-ID.
    """
    if tenant_id != current_tenant.id:
        raise ForbiddenError("Cross-tenant access denied.")

    profile = await TenantService.get_tenant_profile(session, current_tenant.id)
    return TenantProfileResponse(**profile)
