"""
Razorpay Payment Provider Implementation.

Supports real API communication with Razorpay and mock/sandbox emulation
for development, testing, and offline evaluation.
"""

import uuid
import datetime
from typing import Any
import httpx
from app.core.config import settings
from app.integrations.payments.base import PaymentProvider


class RazorpayProvider(PaymentProvider):
    """Concrete Razorpay payment gateway adapter."""

    BASE_URL = "https://api.razorpay.com/v1"

    def __init__(
        self,
        key_id: str | None = None,
        key_secret: str | None = None,
        mock_mode: bool | None = None,
    ):
        self.key_id = key_id or settings.RAZORPAY_KEY_ID
        self.key_secret = key_secret or settings.RAZORPAY_KEY_SECRET

        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            # Auto mock if using placeholder credentials or running in development/test
            is_placeholder = (
                "placeholder" in self.key_id
                or "placeholder" in self.key_secret
                or settings.APP_ENV in ("development", "test")
            )
            self.mock_mode = is_placeholder

    async def create_subscription(
        self,
        plan_id: str,
        customer_id: str | None = None,
        total_count: int = 12,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a recurring subscription."""
        if self.mock_mode:
            now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
            sub_id = f"sub_{uuid.uuid4().hex[:14]}"
            return {
                "id": sub_id,
                "entity": "subscription",
                "plan_id": plan_id,
                "customer_id": customer_id,
                "status": "created",
                "current_start": None,
                "current_end": None,
                "ended_at": None,
                "quantity": 1,
                "notes": notes or {},
                "charge_at": now_ts,
                "start_at": now_ts,
                "total_count": total_count,
                "paid_count": 0,
                "remaining_count": total_count,
                "short_url": f"https://rzp.io/i/{sub_id}",
            }

        async with httpx.AsyncClient(auth=(self.key_id, self.key_secret), timeout=10.0) as client:
            payload: dict[str, Any] = {
                "plan_id": plan_id,
                "total_count": total_count,
                "quantity": 1,
                "customer_notify": 1,
            }
            if customer_id:
                payload["customer_id"] = customer_id
            if notes:
                payload["notes"] = notes

            response = await client.post(f"{self.BASE_URL}/subscriptions", json=payload)
            response.raise_for_status()
            return response.json()

    async def fetch_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Fetch subscription details."""
        if self.mock_mode:
            now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
            return {
                "id": subscription_id,
                "entity": "subscription",
                "plan_id": "plan_pro_monthly",
                "customer_id": None,
                "status": "active",
                "current_start": now_ts,
                "current_end": now_ts + 30 * 86400,
                "ended_at": None,
                "quantity": 1,
                "notes": {},
                "charge_at": now_ts + 30 * 86400,
                "start_at": now_ts,
                "total_count": 12,
                "paid_count": 1,
                "remaining_count": 11,
            }

        async with httpx.AsyncClient(auth=(self.key_id, self.key_secret), timeout=10.0) as client:
            response = await client.get(f"{self.BASE_URL}/subscriptions/{subscription_id}")
            response.raise_for_status()
            return response.json()

    async def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Cancel subscription immediately."""
        if self.mock_mode:
            return {
                "id": subscription_id,
                "entity": "subscription",
                "status": "cancelled",
            }

        async with httpx.AsyncClient(auth=(self.key_id, self.key_secret), timeout=10.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/subscriptions/{subscription_id}/cancel",
                json={"cancel_at_cycle_end": 0},
            )
            response.raise_for_status()
            return response.json()
