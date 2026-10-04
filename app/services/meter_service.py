"""
FlyRank Capstone — MeterService.
Coordinates double-checked locking idempotency, quota enforcement, and atomic usage recording.
"""

import datetime
import hashlib
import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    IdempotencyConflictError,
    NotFoundError,
    PaymentRequiredError,
)
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.usage_event import UsageEvent
from app.models.idempotency import IdempotencyRecord
from app.repositories.idempotency_repository import IdempotencyRepository
from app.repositories.usage_repository import UsageRepository
from app.schemas.usage import GenerateRequest
from app.services.pricing_service import PricingService
from app.services.quota_service import QuotaService


class MeterService:
    """Core metering engine for executing and metering billable AI operations."""

    @classmethod
    def compute_request_hash(cls, request_data: GenerateRequest) -> str:
        """Compute SHA-256 hash of canonical request body."""
        canonical_json = request_data.model_dump_json()
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    async def process_generate(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        idempotency_key: str,
        request_data: GenerateRequest,
    ) -> tuple[dict, bool]:
        """
        Process a generation request with double-checked locking:
        1. Check 1 (unlocked read): Return cached response on hit; verify payload hash.
        2. Pessimistic row-level lock on tenant's Subscription.
        3. Check 2 (double-checked read inside transaction).
        4. Validate subscription status and plan limits.
        5. Verify dual quotas and budget guard.
        6. Atomically persist UsageEvent and IdempotencyRecord.
        
        Returns:
            (response_body_dict, is_cache_hit: bool)
        """
        request_hash = cls.compute_request_hash(request_data)

        # ── Check 1: Optimistic Read from Idempotency Cache ───────────────────
        cached = await IdempotencyRepository.get(session, tenant_id, idempotency_key)
        if cached:
            if cached.request_hash != request_hash:
                raise IdempotencyConflictError(
                    "Idempotency-Key was already used with a different request payload."
                )
            return cached.response_body, True

        # ── Begin Critical Section: Acquire Row Lock on Subscription ─────────
        sub_stmt = (
            select(Subscription)
            .where(Subscription.tenant_id == tenant_id)
            .with_for_update()
        )
        sub_result = await session.execute(sub_stmt)
        subscription = sub_result.scalar_one_or_none()

        if not subscription:
            raise NotFoundError(f"No subscription found for tenant {tenant_id}.")

        # ── Check 2: Double-Checked Locking Inside Transaction ────────────────
        double_check = await IdempotencyRepository.get(session, tenant_id, idempotency_key)
        if double_check:
            if double_check.request_hash != request_hash:
                raise IdempotencyConflictError(
                    "Idempotency-Key was already used with a different request payload."
                )
            return double_check.response_body, True

        # ── Status & Plan Validation ──────────────────────────────────────────
        if subscription.status in ("cancelled", "halted", "expired"):
            raise PaymentRequiredError(
                f"Subscription is {subscription.status}. An active subscription is required to generate."
            )

        plan_stmt = select(Plan).where(Plan.id == subscription.plan_id)
        plan_result = await session.execute(plan_stmt)
        plan = plan_result.scalar_one_or_none()
        if not plan:
            raise NotFoundError(f"Plan not found for subscription {subscription.id}.")

        # ── Token & Pricing Calculation ───────────────────────────────────────
        tokens = request_data.simulated_tokens
        total_tokens = tokens.total_tokens
        projected_cost = PricingService.calculate_token_cost(
            fresh_input_tokens=tokens.fresh_input_tokens,
            cached_input_tokens=tokens.cached_input_tokens,
            output_tokens=tokens.output_tokens,
            reasoning_tokens=tokens.reasoning_tokens,
        )

        # ── Pre-Execution Dual Quota & Budget Guard Evaluation ────────────────
        await QuotaService.check_quota_and_budget(
            session=session,
            tenant_id=tenant_id,
            subscription=subscription,
            plan=plan,
            requested_tokens=total_tokens,
            projected_cost_micro_inr=projected_cost,
        )

        # ── Simulate AI Completion ───────────────────────────────────────────
        gen_id = f"gen_{uuid.uuid4().hex[:8]}"
        prompt_snippet = request_data.prompt[:60].replace("\n", " ")
        result_text = f"Simulated AI completion result for prompt: '{prompt_snippet}'"

        # ── Atomic Ledger Mutation: UsageEvent + IdempotencyRecord ───────────
        now = datetime.datetime.now(datetime.timezone.utc)
        event_id = uuid.uuid4()
        usage_event = UsageEvent(
            id=event_id,
            tenant_id=tenant_id,
            usage_type="generate",
            api_calls=1,
            total_tokens=total_tokens,
            fresh_input_tokens=tokens.fresh_input_tokens,
            cached_input_tokens=tokens.cached_input_tokens,
            output_tokens=tokens.output_tokens,
            reasoning_tokens=tokens.reasoning_tokens,
            cost_micro_inr=projected_cost,
            idempotency_key=idempotency_key,
            timestamp=now,
        )

        formatted_cost = PricingService.format_micro_inr(projected_cost)
        response_body = {
            "id": gen_id,
            "result": result_text,
            "metering": {
                "usage_event_id": str(event_id),
                "api_calls_metered": 1,
                "total_tokens_metered": total_tokens,
                "cost_micro_inr": projected_cost,
                "currency": "INR",
                "formatted_cost": formatted_cost,
            },
        }

        idempotency_record = IdempotencyRecord(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            response_status_code=200,
            response_body=response_body,
        )

        try:
            await UsageRepository.create(session, usage_event)
            await IdempotencyRepository.create(session, idempotency_record)
            await session.commit()
            return response_body, False
        except IntegrityError:
            await session.rollback()
            # A concurrent transaction with identical key won the race and committed.
            # Re-fetch the committed winner record:
            winner = await IdempotencyRepository.get(session, tenant_id, idempotency_key)
            if winner:
                if winner.request_hash != request_hash:
                    raise IdempotencyConflictError(
                        "Idempotency-Key was already used with a different request payload."
                    )
                return winner.response_body, True
            raise
