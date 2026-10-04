"""
FlyRank Capstone — POST /api/v1/generate API Router.
Billable AI completion endpoint simulating model execution and recording dual-quota usage.
"""

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant
from app.core.database import get_db
from app.models.tenant import Tenant
from app.schemas.usage import GenerateRequest, GenerateResponse
from app.services.meter_service import MeterService

router = APIRouter(tags=["Metering"])


@router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute simulated AI generation and meter usage",
)
async def generate(
    request: GenerateRequest,
    response: Response,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=128,
        description="Unique request key for exactly-once processing (max 128 chars)",
    ),
    current_tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    """
    Simulates AI completion and atomically meters API calls and AI tokens.
    Guarantees idempotency via double-checked locking and returns X-Cache-Lookup header.
    """
    result_dict, is_cache_hit = await MeterService.process_generate(
        session=session,
        tenant_id=current_tenant.id,
        idempotency_key=idempotency_key,
        request_data=request,
    )

    response.headers["X-Cache-Lookup"] = "HIT" if is_cache_hit else "MISS"
    return GenerateResponse(**result_dict)
