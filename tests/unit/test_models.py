"""
Unit tests for SQLAlchemy database models, constraints, and indexes.
Includes regression tests for BUG-003 and BUG-004.
"""

from app.models.usage_event import UsageEvent
from app.models.idempotency import IdempotencyRecord
from app.models.payment_event import PaymentEvent


def test_usage_event_partial_unique_index():
    """
    Regression test for BUG-003:
    UsageEvent must define a unique partial index on (tenant_id, idempotency_key)
    where idempotency_key IS NOT NULL for defense-in-depth.
    """
    indexes = {idx.name: idx for idx in UsageEvent.__table_args__}
    assert "uq_usage_events_tenant_idempotency_key" in indexes

    uq_idx = indexes["uq_usage_events_tenant_idempotency_key"]
    assert uq_idx.unique is True
    assert [col.name for col in uq_idx.columns] == ["tenant_id", "idempotency_key"]
    assert "idempotency_key IS NOT NULL" in str(uq_idx.dialect_options["postgresql"]["where"])


def test_usage_event_covering_rollup_index():
    """
    Regression test for BUG-004:
    UsageEvent must define a composite covering index for monthly rollups:
    (tenant_id, timestamp) INCLUDE (api_calls, total_tokens, cost_micro_inr).
    """
    indexes = {idx.name: idx for idx in UsageEvent.__table_args__}
    assert "idx_usage_events_rollup" in indexes

    rollup_idx = indexes["idx_usage_events_rollup"]
    assert [col.name for col in rollup_idx.columns] == ["tenant_id", "timestamp"]
    assert rollup_idx.dialect_options["postgresql"]["include"] == [
        "api_calls",
        "total_tokens",
        "cost_micro_inr",
    ]


def test_idempotency_record_unique_constraint():
    """Verify IdempotencyRecord has unique constraint on (tenant_id, idempotency_key)."""
    constraints = {c.name for c in IdempotencyRecord.__table_args__ if hasattr(c, "name")}
    assert "uq_idempotency_tenant_key" in constraints


def test_payment_event_unique_constraint():
    """Verify PaymentEvent has unique constraint on (provider, provider_event_id)."""
    constraints = {c.name for c in PaymentEvent.__table_args__ if hasattr(c, "name")}
    assert "uq_payment_provider_event" in constraints

