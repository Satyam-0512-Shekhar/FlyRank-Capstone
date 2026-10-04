"""
Abstract base class for payment providers (Razorpay, Stripe, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any


class PaymentProvider(ABC):
    """Abstract payment gateway interface."""

    @abstractmethod
    async def create_subscription(
        self,
        plan_id: str,
        customer_id: str | None = None,
        total_count: int = 12,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a recurring subscription for a tenant."""
        pass

    @abstractmethod
    async def fetch_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Fetch subscription details from gateway."""
        pass

    @abstractmethod
    async def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Cancel a subscription with the gateway."""
        pass
