"""
FlyRank Capstone — Domain exception hierarchy.

Every exception maps to a deterministic HTTP status code.
Routes never catch generic Exception — only specific domain errors.
"""

from typing import Any


class FlyRankError(Exception):
    """Base error for all application-level exceptions."""

    status_code: int = 500
    error_code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, details: dict[str, Any] | None = None):
        self.message = message or self.__class__.message
        self.details = details or {}
        super().__init__(self.message)


# ── 400 Bad Request ──────────────────────────────────────────────────────────
class ValidationError(FlyRankError):
    status_code = 400
    error_code = "validation_error"
    message = "Request validation failed."


# ── 402 Payment Required ─────────────────────────────────────────────────────
class PaymentRequiredError(FlyRankError):
    status_code = 402
    error_code = "payment_required"
    message = "An active paid subscription is required."


# ── 404 Not Found ────────────────────────────────────────────────────────────
class NotFoundError(FlyRankError):
    status_code = 404
    error_code = "not_found"
    message = "The requested resource was not found."


# ── 403 Forbidden ────────────────────────────────────────────────────────────
class ForbiddenError(FlyRankError):
    status_code = 403
    error_code = "forbidden"
    message = "Cross-tenant access denied."


# ── 409 Conflict ─────────────────────────────────────────────────────────────
class IdempotencyConflictError(FlyRankError):
    """Same Idempotency-Key reused with a different request payload."""

    status_code = 409
    error_code = "idempotency_conflict"
    message = "Idempotency-Key was already used with a different request payload."


# ── 429 Too Many Requests ────────────────────────────────────────────────────
class QuotaExceededError(FlyRankError):
    status_code = 429
    error_code = "quota_exceeded"
    message = "Monthly usage quota exceeded."

    def __init__(
        self,
        quota_dimension: str,
        limit: int,
        used: int,
        requested: int,
        retry_after_seconds: int = 86400,
    ):
        self.quota_dimension = quota_dimension
        self.limit = limit
        self.used = used
        self.requested = requested
        self.retry_after_seconds = retry_after_seconds
        details = {
            "quota_dimension": quota_dimension,
            "limit": limit,
            "used": used,
            "requested": requested,
            "retry_after_seconds": retry_after_seconds,
        }
        super().__init__(
            message=f"Monthly {quota_dimension} quota exceeded ({used}/{limit}).",
            details=details,
        )


class BudgetGuardError(FlyRankError):
    """Per-call cost ceiling exceeded — PDF Requirement #7."""

    status_code = 429
    error_code = "budget_guard_exceeded"
    message = "Per-call cost limit exceeded."

    def __init__(self, projected_cost: int, max_allowed: int):
        details = {
            "quota_dimension": "budget_guard",
            "projected_cost_micro_inr": projected_cost,
            "max_allowed_micro_inr": max_allowed,
        }
        super().__init__(
            message=f"Projected call cost {projected_cost} μINR exceeds plan limit {max_allowed} μINR.",
            details=details,
        )


# ── Webhook Errors ────────────────────────────────────────────────────────────
class WebhookSignatureError(FlyRankError):
    status_code = 400
    error_code = "invalid_signature"
    message = "Webhook signature verification failed."


class DuplicateWebhookError(FlyRankError):
    """Already-processed webhook received again — expected, not an error."""

    status_code = 200
    error_code = "duplicate_webhook"
    message = "Webhook event already processed."
