# EVIDENCE.md — Acceptance Probe Evidence
**FlyRank Capstone: Usage Metering & Billing Engine**

This document provides verifiable evidence for every major requirement in the FlyRank capstone brief. Evidence is collected progressively as each phase completes.

---

## Phase 3: Infrastructure Hardening & Security Verification Evidence

| Area | Test / Assertion | Result | Evidence |
|---|---|---|---|
| **Cryptographic Webhook Security** | HMAC-SHA256 constant-time signature verification | ✅ PASS | `tests/unit/test_security.py::test_verify_razorpay_signature_valid` passed; tampered payload rejected |
| **Tamper Resistance** | Modified payload rejected with signature mismatch | ✅ PASS | `tests/unit/test_security.py::test_verify_razorpay_signature_tampered_payload` passed |
| **Health Check (Normal)** | `GET /health` returns 200 OK when DB connected | ✅ PASS | `tests/unit/test_health.py::test_health_check_healthy` passed |
| **Health Check (Degraded)** | `GET /health` returns 503 Service Unavailable when DB disconnected | ✅ PASS | `tests/unit/test_health.py::test_health_check_db_failure_returns_503` passed (BUG-006 regression fix) |
| **Quota Retry-After Header** | `QuotaExceededError` includes `Retry-After: <seconds>` HTTP header | ✅ PASS | `tests/unit/test_exceptions.py::test_quota_exceeded_header_and_body` passed (BUG-011 regression fix) |
| **Duplicate Webhook Format** | `DuplicateWebhookError` returns `{"status": "ignored", "reason": "duplicate_webhook"}` | ✅ PASS | `tests/unit/test_exceptions.py::test_duplicate_webhook_format` passed (BUG-007 regression fix) |
| **Partial Unique Constraint** | `UsageEvent` partial index `uq_usage_events_tenant_idempotency_key` | ✅ PASS | `tests/unit/test_models.py::test_usage_event_partial_unique_index` passed (BUG-003 regression fix) |
| **Covering Rollup Index** | `UsageEvent` index `idx_usage_events_rollup` with `INCLUDE` clause | ✅ PASS | `tests/unit/test_models.py::test_usage_event_covering_rollup_index` passed (BUG-004 regression fix) |
| **Database Transaction Commit** | `get_db()` executes `await session.commit()` on clean exit | ✅ PASS | `tests/unit/test_database.py::test_get_db_commits_on_success` passed (BUG-005 regression fix) |
| **Production Credential Guard** | Rejects placeholder Razorpay credentials when `APP_ENV=production` | ✅ PASS | `tests/unit/test_config.py::test_settings_production_rejects_placeholder_credentials` passed (BUG-009 fix) |
| **Extra Environment Variables** | `SettingsConfigDict(extra="ignore")` prevents startup crash on extra vars | ✅ PASS | `tests/unit/test_config.py::test_settings_ignores_extra_environment_variables` passed |

---


## Evidence Template Format

For each requirement, evidence includes:
- **Requirement**: What the FlyRank brief requires
- **Test**: Test name or probe identifier
- **Command/Request**: Exact HTTP request or pytest command
- **Expected**: Documented expected behaviour
- **Actual**: Recorded actual behaviour (filled during Phase 13)
- **Output**: Actual log/transcript snippet

---

## 1. Idempotency (Probe 1)

**Requirement**: Same idempotency key sent twice must produce exactly one usage event.

| Field | Value |
|---|---|
| Test | `tests/integration/test_acceptance_probes_metering.py::test_probe_1_idempotent_metering_sequential_and_concurrent` |
| Command | `pytest tests/integration/test_acceptance_probes_metering.py::test_probe_1_idempotent_metering_sequential_and_concurrent -v` |
| Expected | 2 requests → 1 `usage_events` row; Call 2 returns `X-Cache-Lookup: HIT`; Concurrent burst of 5 requests with same key yields 1 MISS, 4 HITs, and exactly 1 usage event recorded. |
| Actual | ✅ PASSED: 1 initial MISS + 1 sequential HIT (same event ID returned, zero duplicate DB events). Burst of 5 concurrent requests with identical key yielded exactly 1 MISS and 4 HITs, with exactly 1 additional DB event. |
| Output | `tests/integration/test_acceptance_probes_metering.py::test_probe_1_idempotent_metering_sequential_and_concurrent PASSED` |

---

## 2. Quota Boundary (Probe 2)

**Requirement**: Request at exactly the limit succeeds; request over the limit returns 429.

| Field | Value |
|---|---|
| Test | `tests/integration/test_acceptance_probes_metering.py::test_probe_2_quota_boundary_honesty` |
| Command | `pytest tests/integration/test_acceptance_probes_metering.py::test_probe_2_quota_boundary_honesty -v` |
| Expected | Call at remaining quota boundary succeeds (200 OK); next call over boundary is rejected with 429, body containing `error: "quota_exceeded"`, `quota_dimension: "api_calls"`, and `Retry-After` header present. |
| Actual | ✅ PASSED: Request using remaining quota succeeded with 200 OK. Next request returned 429 Too Many Requests with `error: "quota_exceeded"`, `quota_dimension: "api_calls"`, and valid `Retry-After` header. Post-rejection GET /usage verified no phantom usage was recorded. |
| Output | `tests/integration/test_acceptance_probes_metering.py::test_probe_2_quota_boundary_honesty PASSED` |

---

## 3. Pro Upgrade via Webhook (Probe 3)

**Requirement**: Valid `subscription.activated` webhook transitions tenant Free → Pro; GET /usage reflects new limits.

| Field | Value |
|---|---|
| Test | `tests/integration/test_acceptance_probes_webhooks.py::test_probe_3_pro_upgrade` |
| Command | `pytest tests/integration/test_acceptance_probes_webhooks.py::test_probe_3_pro_upgrade -v` |
| Expected | Webhook 200 OK processed; GET /usage shows plan=pro, api_calls.limit=50000 |
| Actual | ✅ PASSED: Valid HMAC signature webhook with event `subscription.activated` for subscription `sub_probe3_test` returned 200 OK `{"status": "processed"}`. DB subscription updated to `active` with plan `pro`. Subsequent `GET /api/v1/usage` immediately returned elevated Pro limits: `api_calls.limit = 50000` and `ai_tokens.limit = 5000000`. |
| Output | `tests/integration/test_acceptance_probes_webhooks.py::test_probe_3_pro_upgrade PASSED` |

---

## 4. Invalid & Duplicate Webhook (Probe 4)

**Requirement**: Forged webhook returns 400; valid webhook processed once; replay returns 200 ignored.

| Field | Value |
|---|---|
| Test | `tests/integration/test_acceptance_probes_webhooks.py::test_probe_4_webhook_security` |
| Command | `pytest tests/integration/test_acceptance_probes_webhooks.py::test_probe_4_webhook_security -v` |
| Expected | Forged: 400 {"error":"invalid_signature"}; Valid: 200 processed; Replay: 200 ignored |
| Actual | ✅ PASSED: Step 4a (Forged): Invalid HMAC signature rejected with 400 Bad Request `{"error": "invalid_signature"}` and 0 DB mutations. Step 4b (Valid): Genuine HMAC processed with 200 OK `{"status": "processed"}` and subscription activated. Step 4c (Replayed): Replayed request returned 200 OK `{"status": "ignored", "reason": "duplicate_webhook"}` with exactly 1 row in `payment_events` and zero duplicate mutations. |
| Output | `tests/integration/test_acceptance_probes_webhooks.py::test_probe_4_webhook_security PASSED` |

---

## 5. Token Pricing Verification (Probe 5)

**Requirement**: Cached input and reasoning token pricing rules produce exact integer totals.

| Field | Value |
|---|---|
| Test | `tests/integration/test_acceptance_probes_metering.py::test_probe_5_ai_token_pricing_verification` |
| Command | `pytest tests/integration/test_acceptance_probes_metering.py::test_probe_5_ai_token_pricing_verification -v` |
| Expected | 1000×40 + 2000×10 + 500×160 + 200×160 = 172,000 μINR |
| Actual | ✅ PASSED: Simulated request with (1000 fresh, 2000 cached, 500 output, 200 reasoning) yielded cost_micro_inr = 172,000. Verified zero floating-point rounding errors across API response, UsageEvent DB record, and GET /usage rollup. |
| Output | `tests/integration/test_acceptance_probes_metering.py::test_probe_5_ai_token_pricing_verification PASSED` |

---

## 6. Tenant Isolation

**Requirement**: Tenant A cannot access Tenant B's usage data.

| Field | Value |
|---|---|
| Test | `tests/integration/test_tenant_isolation.py::test_cross_tenant_access_denied_idor_protection` |
| Command | `pytest tests/integration/test_tenant_isolation.py -v` |
| Expected | Cross-tenant requests return 403 or 404 |
| Actual | ✅ PASSED: Cross-tenant access attempted by Tenant A against Tenant B returns 403 Forbidden with `TENANT_ACCESS_DENIED`. |
| Output | `tests/integration/test_tenant_isolation.py::test_cross_tenant_access_denied_idor_protection PASSED` |

---

## 7. Usage Rollup Accuracy

**Requirement**: GET /usage accurately aggregates all events within the billing period.

| Field | Value |
|---|---|
| Test | `tests/integration/test_usage_api.py::test_usage_summary_and_events_api` |
| Command | `pytest tests/integration/test_usage_api.py::test_usage_summary_and_events_api -v` |
| Expected | Sum of all usage_events.api_calls and usage_events.total_tokens matches reported values |
| Actual | ✅ PASSED: Single generation event recorded 1 API call, 3,700 tokens (1000 fresh, 2000 cached, 500 output, 200 reasoning), and 172,000 μINR cost. Subsequent `GET /api/v1/usage` accurately verified remaining API calls (999/1000), remaining tokens (96,300/100,000), exact breakdown per category, and exact total cost. |
| Output | `tests/integration/test_usage_api.py::test_usage_summary_and_events_api PASSED` |

---

## 8. Budget Guard

**Requirement**: Per-call cost exceeding plan ceiling is rejected with 429.

| Field | Value |
|---|---|
| Test | `tests/integration/test_generate_api.py::test_generate_endpoint_budget_guard_exceeded_429` |
| Command | `pytest tests/integration/test_generate_api.py::test_generate_endpoint_budget_guard_exceeded_429 -v` |
| Expected | Request with projected cost > max_cost_per_call_micro_inr → 429 budget_guard_exceeded |
| Actual | ✅ PASSED: Free plan ceiling is ₹10.00 (10,000,000 μINR). Requesting 100,000 output tokens yields projected cost of 16,000,000 μINR (₹16.00). Request was rejected before generation with 429 Too Many Requests, error `budget_guard_exceeded`, and Retry-After header. |
| Output | `tests/integration/test_generate_api.py::test_generate_endpoint_budget_guard_exceeded_429 PASSED` |
