# Metering & Quota Core Implementation Plan (Phases 5–8)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete Usage Metering & Quota Engine for the FlyRank Capstone, implementing the dummy billable AI endpoint (`POST /api/v1/generate`), pure integer micro-INR token pricing, dual-quota pre-execution enforcement, per-call budget guards, double-checked idempotency locking, and usage rollup endpoints (`GET /api/v1/usage`, `GET /api/v1/usage/events`).

**Architecture:** 
- Strict 4-tier layered architecture: FastAPI presentation layer (`app/api/v1/`), business logic services (`app/services/`), data access repositories (`app/repositories/`), and SQLAlchemy 2.0 async models.
- Pessimistic row-level locking (`SELECT ... FROM subscriptions WHERE tenant_id = :id FOR UPDATE`) serializes quota evaluations and prevents race conditions at plan boundaries.
- Double-checked locking prevents concurrent duplicate requests with the same `Idempotency-Key` from executing multiple times.
- Zero floating-point arithmetic: pure integer multiplication with canonical micro-INR ($\mu\text{INR}$).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Pytest, Pytest-Asyncio.

## Global Constraints
- Primary source of truth: FlyRank Capstone PDF and approved `DESIGN.md` v2.0.
- Currency unit: Canonical micro-INR ($\mu\text{INR}$, 1 INR = 1,000,000 $\mu\text{INR}$), stored as integers. Zero float arithmetic.
- Pricing constants: Fresh input = 40 $\mu\text{INR}$, Cached input = 10 $\mu\text{INR}$, Output = 160 $\mu\text{INR}$, Reasoning = 160 $\mu\text{INR}$.
- Free plan quotas: 1,000 API calls, 100,000 tokens, ₹10 budget guard (10,000,000 $\mu\text{INR}$).
- Pro plan quotas: 50,000 API calls, 10,000,000 tokens, ₹100 budget guard (100,000,000 $\mu\text{INR}$).
- Idempotency-Key header: Required for `POST /api/v1/generate`, max length 128 characters.
- Quota rejection: HTTP 429 Too Many Requests with `Retry-After` header.
- Idempotency collision with different body: HTTP 409 Conflict.
- Strict tenant isolation: IDOR prohibited, all queries filtered by `tenant_id`.

---

### Task 1: AI Token Pricing & Cost Engine (`PricingService`)

**Files:**
- Create: `app/services/pricing_service.py`
- Test: `tests/unit/test_pricing.py`

**Interfaces:**
- Produces:
  - `PricingService.calculate_cost(fresh_input: int, cached_input: int, output: int, reasoning: int) -> int`
  - `PricingService.format_micro_inr(amount_micro_inr: int) -> str`

- [ ] **Step 1: Write the failing unit tests for PricingService**
Create `tests/unit/test_pricing.py`:
- Test formula: $(1000 \times 40) + (2000 \times 10) + (500 \times 160) + (200 \times 160) = 172,000\ \mu\text{INR}$.
- Test 0 tokens = 0 $\mu\text{INR}$.
- Test reasoning rate equals output rate (160 $\mu\text{INR}$).
- Test cached rate is 75% cheaper than fresh rate (10 vs 40 $\mu\text{INR}$).
- Test currency formatting (`172000` -> `"₹0.17"` or `"₹0.1720"`).
- Test negative tokens raises `ValueError`.

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/unit/test_pricing.py`
Expected: FAIL (ModuleNotFoundError: No module named 'app.services.pricing_service')

- [ ] **Step 3: Implement PricingService**
Create `app/services/pricing_service.py`:
- Pure integer arithmetic without floating-point math.
- Read prices from `app.core.config.settings`.
- Format function returning standard formatted rupee representation.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/unit/test_pricing.py`
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit**
`git add app/services/pricing_service.py tests/unit/test_pricing.py`
`git commit -m "feat(pricing): implement deterministic integer micro-INR AI token pricing engine"`

---

### Task 2: Pydantic Schemas for Metering & Usage (`app/schemas/usage.py`)

**Files:**
- Create: `app/schemas/usage.py`
- Test: `tests/unit/test_usage_schemas.py`

**Interfaces:**
- Produces:
  - `SimulatedTokens`: `fresh_input_tokens: int`, `cached_input_tokens: int`, `output_tokens: int`, `reasoning_tokens: int` (all `>= 0`)
  - `GenerateRequest`: `prompt: str`, `model: str = "gpt-simulated"`, `simulated_tokens: SimulatedTokens`
  - `MeteringResult`: `usage_event_id: UUID`, `api_calls_metered: int`, `total_tokens_metered: int`, `cost_micro_inr: int`, `currency: str`, `formatted_cost: str`
  - `GenerateResponse`: `id: str`, `result: str`, `metering: MeteringResult`
  - `UsageSummaryResponse`: `tenant_id: UUID`, `plan: str`, `billing_period: dict`, `api_calls: dict`, `ai_tokens: dict`, `total_cost: dict`
  - `UsageEventItem`: individual usage event for `/api/v1/usage/events`

- [ ] **Step 1: Write unit tests for schema validation**
Create `tests/unit/test_usage_schemas.py`:
- Test valid payload passes validation.
- Test negative token counts fail validation.
- Test missing prompt fails validation.

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/unit/test_usage_schemas.py`
Expected: FAIL (ModuleNotFoundError: No module named 'app.schemas.usage')

- [ ] **Step 3: Implement usage schemas**
Create `app/schemas/usage.py` using Pydantic v2.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/unit/test_usage_schemas.py`
Expected: PASS

- [ ] **Step 5: Commit**
`git add app/schemas/usage.py tests/unit/test_usage_schemas.py`
`git commit -m "feat(schemas): add Pydantic schemas for generate endpoint and usage rollups"`

---

### Task 3: Data Access Repositories (`UsageRepository` & `IdempotencyRepository`)

**Files:**
- Create: `app/repositories/usage_repository.py`
- Create: `app/repositories/idempotency_repository.py`
- Test: `tests/unit/test_usage_repositories.py`

**Interfaces:**
- `UsageRepository`:
  - `create(session, event: UsageEvent) -> UsageEvent`
  - `get_period_usage(session, tenant_id: UUID, start_time: datetime, end_time: datetime) -> tuple[int, int, int]` (api_calls, total_tokens, cost_micro_inr)
  - `get_period_token_breakdown(session, tenant_id: UUID, start_time: datetime, end_time: datetime) -> dict[str, int]`
  - `list_events(session, tenant_id: UUID, limit: int = 50, offset: int = 0) -> list[UsageEvent]`
- `IdempotencyRepository`:
  - `get(session, tenant_id: UUID, key: str) -> IdempotencyRecord | None`
  - `create(session, record: IdempotencyRecord) -> IdempotencyRecord`

- [ ] **Step 1: Write repository tests**
Create `tests/unit/test_usage_repositories.py`:
- Test saving and retrieving `UsageEvent`.
- Test aggregation `get_period_usage` correctly sums only events within the billing period for the specific tenant.
- Test tenant isolation (Tenant A usage never includes Tenant B events).
- Test saving and retrieving `IdempotencyRecord`.

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/unit/test_usage_repositories.py`
Expected: FAIL

- [ ] **Step 3: Implement UsageRepository and IdempotencyRepository**
Create `app/repositories/usage_repository.py` and `app/repositories/idempotency_repository.py` with SQLAlchemy 2.0 async queries.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/unit/test_usage_repositories.py`
Expected: PASS

- [ ] **Step 5: Commit**
`git add app/repositories/usage_repository.py app/repositories/idempotency_repository.py tests/unit/test_usage_repositories.py`
`git commit -m "feat(repo): implement usage and idempotency repositories with tenant scoping"`

---

### Task 4: Quota & Budget Guard Service (`QuotaService`)

**Files:**
- Create: `app/services/quota_service.py`
- Test: `tests/unit/test_quota_service.py`

**Interfaces:**
- Consumes: `UsageRepository`, `Subscription`, `Plan`
- Produces:
  - `QuotaService.resolve_billing_period(subscription: Subscription) -> tuple[datetime, datetime]`
  - `QuotaService.check_quota_and_budget(session, tenant_id: UUID, subscription: Subscription, plan: Plan, requested_tokens: int, projected_cost_micro_inr: int) -> None`
    - Raises `QuotaExceededError` with dimension ("api_calls", "ai_tokens", or "budget_guard"), limit, used, requested, and retry_after_seconds.

- [ ] **Step 1: Write unit tests for QuotaService**
Create `tests/unit/test_quota_service.py`:
- Test allowed when under limits (999/1000 calls, 50k/100k tokens).
- Test boundary allowed at exact limit (1000/1000 calls).
- Test rejected when call quota exceeded (1001/1000 calls) -> raises `QuotaExceededError(dimension="api_calls")`.
- Test rejected when token quota exceeded -> raises `QuotaExceededError(dimension="ai_tokens")`.
- Test rejected when per-call budget exceeded -> raises `QuotaExceededError(dimension="budget_guard")`.
- Test Free plan lazy rollover calculation when current period end is in past.

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/unit/test_quota_service.py`
Expected: FAIL

- [ ] **Step 3: Implement QuotaService**
Create `app/services/quota_service.py`.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/unit/test_quota_service.py`
Expected: PASS

- [ ] **Step 5: Commit**
`git add app/services/quota_service.py tests/unit/test_quota_service.py`
`git commit -m "feat(quota): implement dual-quota pre-execution enforcement and budget guard service"`

---

### Task 5: Meter Service with Double-Checked Locking (`MeterService`)

**Files:**
- Create: `app/services/meter_service.py`
- Test: `tests/unit/test_meter_service.py`

**Interfaces:**
- Consumes: `PricingService`, `QuotaService`, `UsageRepository`, `IdempotencyRepository`, `SubscriptionRepository`, `TenantRepository`
- Produces:
  - `MeterService.process_generate(session, tenant_id: UUID, idempotency_key: str, request_payload: dict) -> tuple[dict, bool]` (returns `(response_dict, is_cache_hit)`)

- [ ] **Step 1: Write unit tests for MeterService**
Create `tests/unit/test_meter_service.py`:
- Test fresh request creates usage event and idempotency record, returns cache_hit=False.
- Test duplicate request with same key & same payload returns cached response and cache_hit=True without creating new usage event.
- Test duplicate request with same key & DIFFERENT payload raises `IdempotencyConflictError` (409).
- Test quota exceeded raises `QuotaExceededError` and rolls back transaction.

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m pytest tests/unit/test_meter_service.py`
Expected: FAIL

- [ ] **Step 3: Implement MeterService**
Create `app/services/meter_service.py` with:
- SHA-256 request payload hashing.
- Initial unlocked read of `IdempotencyRecord`.
- Pessimistic locking of `Subscription` (`SELECT ... FOR UPDATE`).
- Double-checked locking read of `IdempotencyRecord` inside transaction.
- Quota and budget guard checks.
- Simulated AI text generation.
- Atomic commit of `UsageEvent` and `IdempotencyRecord`.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m pytest tests/unit/test_meter_service.py`
Expected: PASS

- [ ] **Step 5: Commit**
`git add app/services/meter_service.py tests/unit/test_meter_service.py`
`git commit -m "feat(meter): implement MeterService with double-checked locking and atomic usage recording"`

---

### Task 6: API Endpoints (`POST /api/v1/generate`, `GET /api/v1/usage`, `GET /api/v1/usage/events`)

**Files:**
- Create: `app/api/v1/generate.py`
- Create: `app/api/v1/usage.py`
- Modify: `app/main.py`
- Test: `tests/integration/test_generate_api.py`
- Test: `tests/integration/test_usage_api.py`

**Interfaces:**
- Endpoints:
  - `POST /api/v1/generate` (Headers: `X-Tenant-ID`, `Idempotency-Key`) -> returns `GenerateResponse`, sets header `X-Cache-Lookup: HIT` or `MISS`.
  - `GET /api/v1/usage` (Header: `X-Tenant-ID`) -> returns `UsageSummaryResponse`.
  - `GET /api/v1/usage/events` (Header: `X-Tenant-ID`, params: `page`, `page_size`) -> returns paginated events.

- [ ] **Step 1: Write integration tests for generate and usage endpoints**
Create `tests/integration/test_generate_api.py` and `tests/integration/test_usage_api.py`:
- Test successful generation returns 200 and `X-Cache-Lookup: MISS`.
- Test repeated generation with same key returns 200, identical body, and `X-Cache-Lookup: HIT`.
- Test hash conflict returns 409 Conflict.
- Test missing `Idempotency-Key` returns 422 or 400.
- Test `GET /api/v1/usage` accurately aggregates calls, tokens, token breakdown, and cost.
- Test `GET /api/v1/usage/events` returns list of events for current tenant.

- [ ] **Step 2: Run tests to verify they fail**
Run: `python -m pytest tests/integration/test_generate_api.py tests/integration/test_usage_api.py`
Expected: FAIL (404 Not Found)

- [ ] **Step 3: Implement API routers and wire into main.py**
Create `app/api/v1/generate.py` and `app/api/v1/usage.py`. Include routers in `app/main.py`.

- [ ] **Step 4: Run tests to verify they pass**
Run: `python -m pytest tests/integration/test_generate_api.py tests/integration/test_usage_api.py`
Expected: PASS

- [ ] **Step 5: Commit**
`git add app/api/v1/generate.py app/api/v1/usage.py app/main.py tests/integration/test_generate_api.py tests/integration/test_usage_api.py`
`git commit -m "feat(api): implement /generate and /usage endpoints with cache headers and analytics"`

---

### Task 7: Concurrency & Boundary Probes Verification (Probes 1, 2, and 5)

**Files:**
- Create: `tests/integration/test_acceptance_probes_metering.py`

- [ ] **Step 1: Write automated acceptance probe tests for Probes 1, 2, and 5**
Create `tests/integration/test_acceptance_probes_metering.py`:
- **Probe 1 (Idempotent Metering):**
  - Run concurrent `POST /generate` requests with identical `Idempotency-Key`.
  - Verify DB has exactly 1 `UsageEvent` and 1 `IdempotencyRecord`.
  - Verify both requests return HTTP 200, first with `MISS`, second with `HIT`.
- **Probe 2 (Quota Boundary Honesty):**
  - Seed tenant usage at 999 API calls.
  - Call #1000 succeeds with 200 OK. Usage increases to 1,000.
  - Call #1001 rejected with 429 Too Many Requests, `Retry-After` header present, DB usage stays at 1,000.
- **Probe 5 (AI Token Pricing Verification):**
  - Call with 1000 fresh, 2000 cached, 500 output, 200 reasoning.
  - Verify exact integer cost is 172,000 $\mu\text{INR}$.
  - Verify `GET /usage` shows exact 172,000 $\mu\text{INR}$ and token breakdown.

- [ ] **Step 2: Run probe tests to verify execution and results**
Run: `python -m pytest tests/integration/test_acceptance_probes_metering.py -v`
Expected: PASS (all 3 acceptance probes pass cleanly)

- [ ] **Step 3: Run full test suite and verify coverage**
Run: `python -m pytest --cov=app tests/`
Expected: 100% pass across all tests with >90% coverage.

- [ ] **Step 4: Commit and push**
`git add tests/integration/test_acceptance_probes_metering.py`
`git commit -m "test(probes): add automated verification for Acceptance Probes 1, 2, and 5"`
`git push origin main`
