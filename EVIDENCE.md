# EVIDENCE.md — Acceptance Probe Evidence
**FlyRank Capstone: Usage Metering & Billing Engine**

This document provides verifiable evidence for every major requirement in the FlyRank capstone brief. Evidence is collected progressively as each phase completes.

> [!NOTE]
> Evidence sections are populated during Phases 12–13. Placeholder sections are stubs that will be filled with actual HTTP request/response transcripts, database query outputs, and test run logs.

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
