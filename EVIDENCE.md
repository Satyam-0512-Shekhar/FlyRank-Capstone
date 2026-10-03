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
| Test | `tests/probes/test_acceptance_probes.py::test_probe_1_idempotency` |
| Command | `pytest tests/probes/test_acceptance_probes.py::test_probe_1_idempotency -v` |
| Expected | 2 requests → 1 `usage_events` row; Call 2 returns `X-Cache-Lookup: HIT` |
| Actual | *To be recorded in Phase 13* |
| Output | *To be recorded in Phase 13* |

---

## 2. Quota Boundary (Probe 2)

**Requirement**: Request at exactly the limit succeeds; request over the limit returns 429.

| Field | Value |
|---|---|
| Test | `tests/probes/test_acceptance_probes.py::test_probe_2_quota_boundary` |
| Expected | Call #1000: 200 OK; Call #1001: 429 with `quota_dimension: api_calls` |
| Actual | *To be recorded in Phase 13* |
| Output | *To be recorded in Phase 13* |

---

## 3. Pro Upgrade via Webhook (Probe 3)

**Requirement**: Valid `subscription.activated` webhook transitions tenant Free → Pro; GET /usage reflects new limits.

| Field | Value |
|---|---|
| Test | `tests/probes/test_acceptance_probes.py::test_probe_3_pro_upgrade` |
| Expected | Webhook 200 OK processed; GET /usage shows plan=pro, api_calls.limit=50000 |
| Actual | *To be recorded in Phase 13* |
| Output | *To be recorded in Phase 13* |

---

## 4. Invalid & Duplicate Webhook (Probe 4)

**Requirement**: Forged webhook returns 400; valid webhook processed once; replay returns 200 ignored.

| Field | Value |
|---|---|
| Test | `tests/probes/test_acceptance_probes.py::test_probe_4_webhook_security` |
| Expected | Forged: 400 {"error":"invalid_signature"}; Valid: 200 processed; Replay: 200 ignored |
| Actual | *To be recorded in Phase 13* |
| Output | *To be recorded in Phase 13* |

---

## 5. Token Pricing Verification (Probe 5)

**Requirement**: Cached input and reasoning token pricing rules produce exact integer totals.

| Field | Value |
|---|---|
| Test | `tests/probes/test_acceptance_probes.py::test_probe_5_pricing` |
| Expected | 1000×40 + 2000×10 + 500×160 + 200×160 = 172,000 μINR |
| Actual | *To be recorded in Phase 13* |
| Output | *To be recorded in Phase 13* |

---

## 6. Tenant Isolation

**Requirement**: Tenant A cannot access Tenant B's usage data.

| Field | Value |
|---|---|
| Test | `tests/integration/test_tenant_isolation.py` |
| Expected | Cross-tenant requests return 403 or 404 |
| Actual | *To be recorded in Phase 13* |
| Output | *To be recorded in Phase 13* |

---

## 7. Usage Rollup Accuracy

**Requirement**: GET /usage accurately aggregates all events within the billing period.

| Field | Value |
|---|---|
| Test | `tests/integration/test_quota.py::test_usage_rollup_accuracy` |
| Expected | Sum of all usage_events.api_calls and usage_events.total_tokens matches reported values |
| Actual | *To be recorded in Phase 13* |
| Output | *To be recorded in Phase 13* |

---

## 8. Budget Guard

**Requirement**: Per-call cost exceeding plan ceiling is rejected with 429.

| Field | Value |
|---|---|
| Test | `tests/integration/test_quota.py::test_budget_guard_enforcement` |
| Expected | Request with projected cost > max_cost_per_call_micro_inr → 429 budget_guard_exceeded |
| Actual | *To be recorded in Phase 13* |
| Output | *To be recorded in Phase 13* |
