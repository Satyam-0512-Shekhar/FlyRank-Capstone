"""
Unit tests for Alembic database migrations and rollback verification.
Verifies revision metadata, upgrade SQL generation, and downgrade rollback SQL.
"""

import io
from alembic.config import Config
from alembic import command
import importlib.util
from pathlib import Path


def get_alembic_config() -> Config:
    """Create Alembic Config pointing to alembic.ini."""
    ini_path = str(Path(__file__).parent.parent.parent / "alembic.ini")
    return Config(ini_path)


def test_migration_file_metadata():
    """Verify 001_initial_schema.py contains expected Alembic revision identifiers."""
    migration_path = (
        Path(__file__).parent.parent.parent
        / "migrations"
        / "versions"
        / "001_initial_schema.py"
    )
    assert migration_path.exists(), "Migration 001_initial_schema.py not found"

    spec = importlib.util.spec_from_file_location("initial_schema", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.revision == "001_initial_schema"
    assert module.down_revision is None
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_migration_upgrade_sql_generation(capsys):
    """
    Verify upgrade DDL generation produces all 6 required tables,
    partial unique index, and covering rollup index per DESIGN.md §5.
    """
    config = get_alembic_config()

    # Run upgrade in offline mode (--sql)
    command.upgrade(config, "001_initial_schema", sql=True)
    captured = capsys.readouterr()
    sql = captured.out

    # Tables
    assert "CREATE TABLE tenants" in sql
    assert "CREATE TABLE plans" in sql
    assert "CREATE TABLE subscriptions" in sql
    assert "CREATE TABLE usage_events" in sql
    assert "CREATE TABLE idempotency_records" in sql
    assert "CREATE TABLE payment_events" in sql

    # Constraints & Indexes
    assert "uq_idempotency_tenant_key" in sql
    assert "uq_payment_provider_event" in sql
    assert "uq_usage_events_tenant_idempotency_key" in sql
    assert "WHERE idempotency_key IS NOT NULL" in sql
    assert "idx_usage_events_rollup" in sql
    assert "INCLUDE (api_calls, total_tokens, cost_micro_inr)" in sql


def test_migration_downgrade_sql_generation(capsys):
    """
    Verify rollback DDL generation drops all 6 tables and indexes
    in reverse dependency order.
    """
    config = get_alembic_config()

    # Run downgrade in offline mode (--sql) from 001_initial_schema to base
    command.downgrade(config, "001_initial_schema:base", sql=True)
    captured = capsys.readouterr()
    sql = captured.out

    # Tables dropped in reverse dependency order
    assert "DROP TABLE payment_events;" in sql
    assert "DROP TABLE idempotency_records;" in sql
    assert "DROP TABLE usage_events;" in sql
    assert "DROP TABLE subscriptions;" in sql
    assert "DROP TABLE plans;" in sql
    assert "DROP TABLE tenants;" in sql

    # Indexes dropped
    assert "DROP INDEX idx_usage_events_rollup;" in sql
    assert "DROP INDEX uq_usage_events_tenant_idempotency_key;" in sql

