"""
Webhook processing service.

Enforces HMAC-SHA256 signature verification, replay deduplication,
and monotonic subscription lifecycle state updates.
"""

import hashlib
import json
import logging
import datetime
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    WebhookSignatureError,
    ValidationError,
)
from app.core.security import verify_razorpay_signature
from app.repositories.payment_event_repository import PaymentEventRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.plan_repository import PlanRepository

logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.payment_event_repo = PaymentEventRepository(session)
        self.sub_repo = SubscriptionRepository(session)
        self.plan_repo = PlanRepository(session)

    async def process_razorpay_webhook(
        self,
        raw_body: bytes,
        signature: str | None,
        event_id: str | None = None,
    ) -> dict[str, str]:
        """
        Cryptographically verify and process incoming Razorpay webhooks.

        Steps:
        1. Verify HMAC-SHA256 signature against settings.RAZORPAY_WEBHOOK_SECRET.
        2. Extract or infer event ID.
        3. Check payment_events for replay / duplicate.
        4. Apply state transitions to subscription.
        5. Persist audit record in payment_events.
        """
        # Step 1: Signature verification
        if not signature:
            logger.warning("Razorpay webhook rejected: missing signature header")
            raise WebhookSignatureError("Missing X-Razorpay-Signature header.")

        is_valid = verify_razorpay_signature(
            raw_body=raw_body,
            signature_header=signature,
            webhook_secret=settings.RAZORPAY_WEBHOOK_SECRET,
        )
        if not is_valid:
            logger.warning("Razorpay webhook rejected: invalid HMAC-SHA256 signature")
            raise WebhookSignatureError("Webhook signature verification failed.")

        # Parse payload
        try:
            payload: dict[str, Any] = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            raise ValidationError(f"Invalid JSON payload: {exc}")

        # Step 2: Determine event ID
        if not event_id:
            event_id = payload.get("id") or payload.get("event_id")

        if not event_id:
            raise ValidationError("Missing webhook event ID.")

        # Step 3: Replay deduplication check
        existing_event = await self.payment_event_repo.get_by_provider_event_id(
            provider="razorpay",
            provider_event_id=event_id,
        )
        if existing_event:
            logger.info("Ignoring duplicate webhook event %s", event_id)
            return {"status": "ignored", "reason": "duplicate_webhook"}

        # Step 4: Process event semantics
        event_type = payload.get("event", "unknown")
        payload_hash = hashlib.sha256(raw_body).hexdigest()

        # Extract subscription ID if present
        sub_payload = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        sub_id = sub_payload.get("id") or payload.get("subscription_id")

        if sub_id:
            sub = await self.sub_repo.get_by_provider_subscription_id(sub_id)
            if sub:
                await self._handle_subscription_event(sub, event_type, sub_payload)
            else:
                logger.warning(
                    "Webhook received for unknown provider_subscription_id %s", sub_id
                )

        # Step 5: Record event in ledger
        await self.payment_event_repo.create(
            provider="razorpay",
            provider_event_id=event_id,
            event_type=event_type,
            payload_hash=payload_hash,
            raw_payload=payload,
            status="processed",
        )

        return {"status": "processed"}

    async def _handle_subscription_event(
        self, sub, event_type: str, sub_payload: dict[str, Any]
    ) -> None:
        """Handle subscription lifecycle updates with monotonic state transition rules."""
        # Terminal state guard: cannot reactivate a cancelled or completed subscription
        if sub.status in ("cancelled", "completed") and event_type in (
            "subscription.activated",
            "subscription.charged",
        ):
            logger.warning(
                "Cannot activate subscription %s from terminal state %s",
                sub.provider_subscription_id,
                sub.status,
            )
            return

        if event_type in ("subscription.activated", "subscription.charged"):
            pro_plan = await self.plan_repo.get_by_name("pro")
            if not pro_plan:
                logger.error("Pro plan not found in database during upgrade")
                return

            period_start = None
            period_end = None
            if "current_start" in sub_payload and sub_payload["current_start"]:
                period_start = datetime.datetime.fromtimestamp(
                    sub_payload["current_start"], datetime.timezone.utc
                )
            else:
                period_start = datetime.datetime.now(datetime.timezone.utc)

            if "current_end" in sub_payload and sub_payload["current_end"]:
                period_end = datetime.datetime.fromtimestamp(
                    sub_payload["current_end"], datetime.timezone.utc
                )
            else:
                period_end = period_start + datetime.timedelta(days=30)

            await self.sub_repo.upgrade_to_plan(
                subscription=sub,
                new_plan_id=pro_plan.id,
                new_status="active",
                period_start=period_start,
                period_end=period_end,
            )
            logger.info(
                "Subscription %s upgraded to Pro (active) for tenant %s",
                sub.provider_subscription_id,
                sub.tenant_id,
            )

        elif event_type == "subscription.paused":
            await self.sub_repo.update_status(sub, "paused")
            logger.info("Subscription %s paused", sub.provider_subscription_id)

        elif event_type == "subscription.halted":
            await self.sub_repo.update_status(sub, "halted")
            logger.info("Subscription %s halted", sub.provider_subscription_id)

        elif event_type == "subscription.cancelled":
            await self.sub_repo.update_status(sub, "cancelled")
            logger.info("Subscription %s cancelled", sub.provider_subscription_id)
