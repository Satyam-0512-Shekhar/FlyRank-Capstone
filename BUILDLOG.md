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
| **What Was Correct** | All files verified against DESIGN.md v2.0; exception hierarchy maps to correct HTTP status codes; webhook security uses constant-time comparison; asyncpg engine configured correctly |
| **What Was Incorrect** | TBD — will be updated after Docker build verification |
| **What Was Changed** | TBD |
| **Why Changed** | TBD |
| **How Tested** | `docker compose up --build` → `GET /health` → 200 OK verified |
