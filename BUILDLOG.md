# BUILDLOG.md — AI-Assisted Development Log
**FlyRank Capstone: Usage Metering & Billing Engine**

AI-assisted development is explicitly permitted by FlyRank. This log maintains an honest record of every significant AI-assisted work item.

---

## Format

Each entry follows this structure:

| Field | Value |
|---|---|
| **Date** | YYYY-MM-DD |
| **Phase** | Phase number and name |
| **Task** | What was being built |
| **AI Assistance** | Antigravity / Gemini Flash / Claude Sonnet |
| **What AI Generated** | Brief description of generated content |
| **What Was Correct** | Verified correct items |
| **What Was Incorrect** | Found bugs or design issues |
| **What Was Changed** | Manual or corrective edits |
| **Why Changed** | Rationale |
| **How Tested** | Verification method |

---

## Log Entries

### 2026-10-04 — Phase 1: Design

| Field | Value |
|---|---|
| **Date** | 2026-10-04 |
| **Phase** | Phase 1: Design |
| **Task** | Full architectural design from FlyRank PDF specification |
| **AI Assistance** | Antigravity (Gemini Flash + Claude Sonnet Thinking) |
| **What AI Generated** | DESIGN.md v1.0 → v1.1 → v2.0; Red-team review report |
| **What Was Correct** | 4-tier architecture, database schema, API contract, idempotency strategy, quota enforcement |
| **What Was Incorrect** | v1.0: Incorrect Razorpay `past_due` status (Stripe-specific); Missing budget guard (PDF Req #7); IDOR on tenant endpoint; Concurrent duplicate-key race condition; Floating-point truncation in token rates; Free tier billing rollover undefined |
| **What Was Changed** | All 6 MUST FIX items corrected in v2.0: double-checked locking, budget guard, IDOR eliminated, rates standardised to exact integers, Free tier calendar-month rollover, Razorpay state machine corrected |
| **Why Changed** | Red-team review by hostile senior architect persona identified concrete failure scenarios |
| **How Tested** | Line-by-line document review; cross-reference against Razorpay official documentation |

---

### 2026-10-04 — Phase 2: Project Bootstrap

| Field | Value |
|---|---|
| **Date** | 2026-10-04 |
| **Phase** | Phase 2: Project Bootstrap & Infrastructure |
| **Task** | Repository initialisation, Docker configuration, FastAPI skeleton, Alembic setup |
| **AI Assistance** | Antigravity (Claude Sonnet Thinking) |
| **What AI Generated** | .gitignore, .env.example, requirements.txt, Dockerfile, docker-compose.yml, app/core/* (config.py, database.py, exceptions.py, security.py), app/main.py, app/api/v1/health.py, alembic.ini, migrations/env.py, model stubs, capstone.yaml |
| **What Was Correct** | Project structure; exception hierarchy definitions; webhook security constant-time comparison; asyncpg engine configured correctly |
| **What Was Incorrect** | `script.py.mako` was 1-line stub; duplicate `httpx` in requirements.txt; missing partial unique constraint & covering index on `UsageEvent`; `get_db()` omitted commit; `health.py` returned 200 when DB down; hardcoded password in alembic.ini; deprecated `@app.on_event`; Settings crashed on extra env vars; README.md missing |
| **What Was Changed** | Deferred to Phase 3 Fix & Harden |
| **Why Changed** | Audit identified multiple critical and high severity defects in scaffold |
| **How Tested** | Static code review and red-team audit. Docker Compose verification was pending daemon availability. |

---

### 2026-10-04 — Phase 3: Fix & Harden

| Field | Value |
|---|---|
| **Date** | 2026-10-04 |
| **Phase** | Phase 3: Fix & Harden |
| **Task** | Review findings, classify each finding, fix all confirmed bugs, add regression tests, and validate test suite |
| **AI Assistance** | Antigravity (Gemini Flash + Claude Sonnet Thinking) |
| **What AI Generated** | Standard Alembic Mako template; UsageEvent table args with partial unique index & covering rollup index; `get_db()` commit-on-success; HTTP 503 health check on DB failure; lifespan context manager; `Retry-After` header injection; `extra="ignore"` and production secret validation in `config.py`; `tests/conftest.py`; `pytest.ini`; `README.md`; 19 unit & regression tests |
| **What Was Correct** | All 19 tests passed on first run after resolving fixture scope; 97% test coverage achieved across codebase |
| **What Was Incorrect** | Initial test run had 2 fixture/naming mismatches (async client fixture scope and constraint name `uq_payment_provider_event`), immediately corrected |
| **What Was Changed** | Replaced `script.py.mako`; removed duplicate `httpx`; added `setuptools<72` for razorpay compatibility; added `__table_args__` to `UsageEvent`; added `session.commit()` to `get_db()`; returned 503 on health check error; added `Retry-After` header; updated `alembic.ini` and `env.py`; aligned `capstone.yaml` |
| **Why Changed** | Systematic resolution of all Critical/High bugs and security findings from Phase 3 Red-Team Report |
| **How Tested** | `python -m pytest -v --cov=app tests/` → 19/19 PASSED (0 failures, 97% coverage) |

---

### 2026-10-04 — Phase 4: Multi-Tenant Foundation & Plan Hierarchy

| Field | Value |
|---|---|
| **Date** | 2026-10-04 |
| **Phase** | Phase 4: Multi-Tenant Foundation & Plan Hierarchy |
| **Task** | Tenant onboarding, automatic Free tier subscription provisioning, authentication dependency, and IDOR elimination |
| **AI Assistance** | Antigravity (Gemini Flash) |
| **What AI Generated** | `app/schemas/tenant.py`, `app/schemas/plan.py`, `app/repositories/tenant_repository.py`, `app/repositories/subscription_repository.py`, `app/repositories/plan_repository.py`, `app/services/tenant_service.py`, `app/api/deps.py` (`get_current_tenant`), `app/api/v1/tenants.py` routes, `tests/unit/test_tenant_service.py`, `tests/integration/test_tenants_api.py`, `tests/integration/test_tenant_isolation.py` |
| **What Was Correct** | Clean 4-tier layer decoupling; calendar-month calculation for Free subscription window; UUID format validation; 403 Forbidden on cross-tenant IDOR path tampering |
| **What Was Incorrect** | None — all 35 tests passed on first run |
| **What Was Changed** | Connected remote GitHub repository; registered tenants router under `/api/v1` prefix |
| **Why Changed** | Complete Phase 4 milestone per approved DESIGN.md §13 & §14.2 |
| **How Tested** | `python -m pytest -v --cov=app --cov=scripts tests/` → 35/35 PASSED (93% coverage) |

---

### 2026-10-04 — Phase 5–8: Usage Metering, Pricing, Quota & Idempotency Core

| Field | Value |
|---|---|
| **Date** | 2026-10-04 |
| **Phase** | Phases 5–8: Usage Metering, Pricing, Quota & Idempotency Core |
| **Task** | Billable AI generation endpoint (`POST /api/v1/generate`), pure integer micro-INR token pricing engine, dual-quota pre-execution enforcement, per-call budget guards, double-checked locking idempotency, usage aggregation endpoints (`GET /api/v1/usage`, `GET /api/v1/usage/events`), and automated verification for Acceptance Probes 1, 2, and 5 |
| **AI Assistance** | Antigravity (Gemini Flash + Claude Sonnet Thinking) |
| **What AI Generated** | `app/services/pricing_service.py`, `app/schemas/usage.py`, `app/repositories/usage_repository.py`, `app/repositories/idempotency_repository.py`, `app/services/quota_service.py`, `app/services/meter_service.py`, `app/api/v1/generate.py`, `app/api/v1/usage.py`, unit tests (`test_pricing.py`, `test_usage_schemas.py`, `test_usage_repositories.py`, `test_quota_service.py`, `test_meter_service.py`), integration tests (`test_generate_api.py`, `test_usage_api.py`), acceptance probe tests (`test_acceptance_probes_metering.py`) |
| **What Was Correct** | Pure integer arithmetic formula without float division; double-checked locking flow; dual-quota pre-validation and budget guard ceiling logic; honest 429 response with `Retry-After` header; X-Cache-Lookup headers (`HIT` vs `MISS`) |
| **What Was Incorrect** | 1. `tests/conftest.py` shared a single SQLite in-memory connection across concurrent coroutines causing transaction collision. Fixed by using isolated temporary SQLite files enabling true independent connections.<br>2. `usage_event.id` was evaluated before commit causing `None` UUID string validation error. Fixed by explicitly assigning `uuid.uuid4()`.<br>3. `meter_service.py` caught concurrent duplicate races with database-level `IntegrityError` fallback, returning winner's committed response body cleanly. |
| **What Was Changed** | Added `IntegrityError` catch-and-recover block in `MeterService`; explicitly passed `uuid.uuid4()` to `UsageEvent`; wired `generate` and `usage` routers into `app/main.py`; updated test fixtures for true connection isolation |
| **Why Changed** | Ensure 100% thread-safety, transaction isolation, and flawless passing of Acceptance Probes 1, 2, and 5 |
| **How Tested** | `python -m pytest --cov=app tests/` → 65/65 PASSED (91% total coverage); `pytest tests/integration/test_acceptance_probes_metering.py -v` → 3/3 PROBES PASSED |

---

### 2026-10-04 — Phase 9–10: Razorpay Integration & Webhook Handling

| Field | Value |
|---|---|
| **Date** | 2026-10-04 |
| **Phase** | Phases 9–10: Razorpay Integration & Webhook Handling |
| **Task** | Abstract PaymentProvider and RazorpayProvider adapter, PaymentEventRepository with deduplication, SubscriptionService for initiating upgrades, WebhookService with constant-time HMAC-SHA256 signature verification and replay protection, Billing & Webhook API endpoints (`POST /api/v1/billing/subscription`, `GET /api/v1/billing/subscription`, `POST /api/v1/webhooks/razorpay`), and automated verification for Acceptance Probes 3 and 4 |
| **AI Assistance** | Antigravity (Gemini Flash + Claude Sonnet Thinking) |
| **What AI Generated** | `app/integrations/payments/base.py`, `app/integrations/payments/razorpay.py`, `app/repositories/payment_event_repository.py`, `app/schemas/billing.py`, `app/services/subscription_service.py`, `app/services/webhook_service.py`, `app/api/v1/billing.py`, `app/api/v1/webhooks.py`, unit tests (`test_payment_provider.py`, `test_payment_event_repo.py`, `test_webhook_service.py`), integration tests (`test_billing_api.py`, `test_webhooks_api.py`, `test_acceptance_probes_webhooks.py`) |
| **What Was Correct** | Constant-time HMAC-SHA256 verification using `hmac.compare_digest()`; replay deduplication returning `{"status": "ignored", "reason": "duplicate_webhook"}` without mutating database; monotonic subscription lifecycle updates (`pending` → `active` on `subscription.activated`); immediate elevation of limits in `GET /api/v1/usage` |
| **What Was Incorrect** | 1. Plan model attribute in `SubscriptionService` was referenced as `price_monthly_micro_inr` instead of `price_micro_inr`. Fixed to use exact column name.<br>2. `RazorpayProvider` mock check did not account for pytest `APP_ENV=testing` (with "ing"). Fixed to match any non-production or test environment.<br>3. `test_billing_api.py` defined redundant test client that did not commit transactions on exit. Fixed to use shared `client` fixture from `conftest.py`. |
| **What Was Changed** | Added `response_model_exclude_none=True` on webhook route; wired `billing` and `webhooks` routers into `app/main.py`; updated Pro plan quota assertion to match seeded 10,000,000 tokens |
| **Why Changed** | Complete Phases 9 & 10 milestone per approved DESIGN.md §11, §14.5, §14.6 and satisfy Acceptance Probes 3 and 4 |
| **How Tested** | `python -m pytest --cov=app --cov=scripts tests/` → 84/84 PASSED (89% total coverage); `pytest tests/integration/test_acceptance_probes_metering.py tests/integration/test_acceptance_probes_webhooks.py -v` → 5/5 PROBES PASSED |

---

### 2026-10-04 — Phase 11: Resilient Background Subscription Reconciliation Worker

| Field | Value |
|---|---|
| **Date** | 2026-10-04 |
| **Phase** | Phase 11: Resilient Background Subscription Reconciliation Worker |
| **Task** | Standalone async background worker utility with exponential backoff (1s, 2s, 4s), concurrency-safe row locking (`SELECT ... FOR UPDATE SKIP LOCKED` on PostgreSQL), structured failure alerting, periodic sweep loop, and unit test suite |
| **AI Assistance** | Antigravity (Gemini Flash + Claude Sonnet Thinking) |
| **What AI Generated** | `app/workers/reconciliation.py`, `app/workers/__init__.py`, `tests/unit/test_reconciliation_worker.py` |
| **What Was Correct** | Dialect-safe SQL locking checking `dialect.name == "postgresql"`; exponential retry backoff loop; structured error alerting with `extra={"alert": True, ...}` on persistent gateway failure; atomic batch commit on sweep completion |
| **What Was Incorrect** | Pytest `caplog` did not capture log records when preceding tests had reconfigured root logger handlers. Fixed by using `unittest.mock.patch` directly on `logger.error` for deterministic assertion. |
| **What Was Changed** | Patched logger in failure test; exported `ReconciliationWorker` in `app/workers/__init__.py` |
| **Why Changed** | Satisfy FlyRank Shared Requirement #3 without bloated infrastructure (no Celery, Redis, or Kafka) per approved DESIGN.md §12 |
| **How Tested** | `python -m pytest --cov=app --cov=scripts tests/` → 87/87 PASSED (87% total coverage) |



