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


