# Plan: Self-Healing Feature State Review & Gap Analysis

## Current State Assessment

### What Exists (Production-Ready)

The self-healing infrastructure is **extensive and largely complete**. There is substantially more shipped code than gaps.

#### Backend — `backend/app/healing/` (8 modules, ~3K+ LOC)

| Module | Purpose | Status |
|--------|---------|--------|
| `engine.py` | 5-stage orchestration: analyze → generate → apply → validate → report | **Shipped** |
| `models.py` | HealingStatus (9 states), FixRiskLevel (SAFE/MEDIUM/DANGEROUS), 41 fix types classified | **Shipped** |
| `analyzer.py` | FailureAnalyzer with 20+ failure type signatures, pattern matching, root cause ID | **Shipped** |
| `applicator.py` | 17 FixApplicator strategies (one per failure category), original-state tracking for rollback | **Shipped** |
| `validator.py` | 18 validation strategies per failure category, async workflow runner support | **Shipped** |
| `verification.py` | 2-level verification: Level 1 (config checks), Level 2 (execution + re-detection) | **Shipped** |
| `auto_apply.py` | AutoApplyService with rate limiting, cooldown, healing loop detection, per-workflow locks | **Shipped** |
| `git_backup.py` | GitBackupService for checkpoint/restore via git commits | **Shipped** |

#### Backend — `backend/app/fixes/` (21 modules)

20 detection-specific fix generators covering all failure categories: loop, corruption, persona, deadlock, hallucination, injection, overflow, derailment, context neglect, communication, specification, decomposition, workflow, withholding, completion, cost + 3 framework-specific (Dify, LangGraph, OpenClaw).

Each generator produces `FixSuggestion` with title, description, rationale, code changes, risk level, and confidence.

#### Backend API — `backend/app/api/v1/healing.py` (~1,700 LOC)

Fully mounted at `/api/v1/tenants/{tenant_id}/healing/`. Endpoints:
- `POST /trigger/{detection_id}` — Start healing on a detection
- `GET /{healing_id}/status` — Get healing record
- `POST /{healing_id}/approve` — Approve with notes
- `POST /{healing_id}/rollback` — Rollback applied fix
- `POST /{healing_id}/complete` — Mark complete
- `POST /apply-to-n8n/{detection_id}` — Apply fix to n8n workflow
- `POST /{healing_id}/promote` / `reject` — Staged deployment
- `POST /{healing_id}/verify` — 2-level verification
- `GET /verification-metrics` — Pass rates by type
- `GET /versions/{workflow_id}` — Version history
- `POST /versions/{version_id}/restore` — Restore prior version
- n8n connection CRUD (list, create, test, delete)

#### Enterprise Quality Healing — `backend/app/api/enterprise/quality_healing.py`

Quality-dimension-aware healing: assess workflow quality → target low-scoring dimensions → generate/apply/verify fixes → track score improvement.

#### Frontend — Complete Production UI

| Component | Status |
|-----------|--------|
| `/app/healing/page.tsx` — Multi-tab dashboard with polling | **Shipped** |
| `/app/quality/healing/page.tsx` — Quality healing records | **Shipped** |
| 8 healing components (HealingCard, StagedFixBanner, PipelineStepper, ApprovalQueue, etc.) | **Shipped** |
| API client — 18 healing methods with full type coverage | **Shipped** |
| Demo data generators for healing records | **Shipped** |
| Diagnose page auto-fix preview ("Fix This Now" button) | **Shipped** |

#### Tests — 87 passing self-healing tests

- `test_self_healing.py` (87 tests): FailureAnalyzer, FixGenerator, FixApplicator, FixValidator, SelfHealingEngine integration, edge cases, adversarial scenarios (loop detection, concurrent race, dangerous fix blocking)
- `test_healing_api.py` (API endpoint tests)
- `test_quality_healing_engine.py`, `test_quality_healing_api.py`, `test_quality_healing_convergence.py`

---

### Gaps Identified

#### Gap 1: Diagnose → Healing Bridge (HARDCODED FALSE)

**File**: `backend/app/api/v1/diagnose.py:396`

The diagnose endpoint always returns:
```python
self_healing_available=False,
auto_fix_preview=None,
```

The healing engine exists. The fix generators exist. But the `/diagnose/why-failed` endpoint never calls them. The frontend has the "Fix This Now" UI but it never activates because `self_healing_available` is always `False`.

**Impact**: The flagship "paste your trace, get a fix" flow is **visually complete but functionally disconnected**. A user who diagnoses a trace sees detections but never gets a fix suggestion.

#### Gap 2: No ICP-Tier Fix Generation in Diagnose

The healing API at `/api/v1/tenants/{tenant_id}/healing/trigger/{detection_id}` requires:
- A tenant context (auth + DB)
- A persisted `Detection` record in the database

But the `/diagnose/why-failed` endpoint is **stateless** (ICP tier, no DB). There's no path from "paste a trace, get a detection" → "generate a fix suggestion" without going through tenant-scoped persistence first.

**Impact**: Anonymous/ICP users can diagnose but cannot heal. The fix generation capability is locked behind tenant auth.

#### Gap 3: No Compound-Failure-Aware Healing

The newly-built compound failure analysis identifies root causes vs symptoms and causal chains. But the healing system generates fixes per-detection independently. If F5 (Flawed Workflow) caused F7 (Context Neglect) caused F14 (Completion Misjudgment), the system would generate 3 independent fix suggestions instead of fixing the root cause (F5) and noting that F7/F14 should resolve as a consequence.

**Impact**: Users could be told to apply 3 fixes when 1 would suffice.

#### Gap 4: No Approval Notification System

The approval workflow (approve/reject with notes) exists in the API and UI. But there's no notification mechanism — no Slack, no email, no webhook. A staged fix requiring approval just sits in the approval queue until someone manually checks the page.

**Impact**: High-risk fixes (DANGEROUS level) that need approval have no way to alert the approver.

#### Gap 5: No Learning Loop (AI → Playbook Graduation)

Documented as strategic vision: "Graduate successful AI fixes to playbook status." No implementation exists. Successful fixes are tracked (`HealingStatus.SUCCESS`) but there's no system to:
- Identify fixes that succeed consistently
- Promote them to deterministic playbooks
- Auto-apply previously-graduated patterns

**Impact**: Every healing is a one-off. The system doesn't get smarter over time.

---

## Implementation Status

All 5 gaps have been implemented. **74 new tests pass** across the 3 new test files.

### 1. Wire Diagnose → Fix Generation (Gap 1+2) — DONE

**Files changed:**
- `backend/app/api/v1/diagnose.py` — Added `_generate_fix_preview()`, `_CATEGORY_TO_DETECTION_TYPE` mapping, wired fix generation into `/why-failed` endpoint
- `backend/app/fixes/__init__.py` — Added `create_fix_generator()` factory

**What it does:**
- After detection, calls the appropriate `FixGenerator` to produce fix suggestions
- Returns `self_healing_available=True` + `auto_fix_preview` with the top suggestion
- No DB, no tenant, no persistence — purely generative, stateless
- Maps all 17 failure modes (F1-F17) + span-based categories to detection types
- Frontend "Fix This Now" button now activates when failures are detected

**Tests:** 7 new tests in `test_diagnose_icp.py::TestFixGenerationBridge`

### 2. Compound-Aware Healing (Gap 3) — DONE

**Files changed:**
- `backend/app/api/v1/diagnose.py` — Added `_annotate_symptom_detections()`, `_count_downstream_symptoms()`, compound-aware fix preview

**What it does:**
- When a causal chain exists (e.g., F5 → F7 → F14), generates fix only for the root cause
- Fix preview description notes how many downstream symptoms should resolve
- Symptom detections are annotated with "Likely symptom of X — expected to resolve when root cause is fixed"
- Integrates with existing `compound_failures.py` analysis

**Tests:** 5 new tests in `test_diagnose_icp.py::TestCompoundAwareHealing`

### 3. Approval Notifications (Gap 4) — DONE

**Files created:**
- `backend/app/notifications/webhook.py` — Generic webhook notifier with Slack Block Kit support

**Files changed:**
- `backend/app/notifications/router.py` — Added `webhook_url`, `notify_on_approval_required`, `notify_approval_required()`, `build_approval_payload()`, deep link generation
- `backend/app/notifications/__init__.py` — Exports `WebhookNotifier`, `ApprovalPayload`, `create_notification_router`
- `backend/app/api/v1/healing.py` — Fire-and-forget notification on approval-required triggers via `asyncio.create_task()`

**What it does:**
- POST to configurable webhook URL with healing context (env: `HEALING_WEBHOOK_URL`)
- Auto-detects Slack incoming webhooks and formats with Block Kit (action buttons, risk emojis)
- Non-Slack webhooks get structured JSON with `event: "approval_required"`
- Includes approve/reject deep links back to the UI (env: `UI_BASE_URL`)
- Routes to all configured channels: webhook, Discord, and email
- Non-blocking — notification failures don't affect healing workflow

**Tests:** 16 new tests in `test_approval_notifications.py`

### 4. Learning Loop (Gap 5) — DONE

**Files created:**
- `backend/app/healing/playbook.py` — `PlaybookRegistry` with `FixOutcome`, `PlaybookEntry`

**What it does:**
- Tracks (detection_type, fix_type) → outcome for every fix application
- After N consecutive successes (configurable, default 3), marks as "graduated playbook"
- Graduated playbooks auto-apply without approval via `should_auto_apply()`
- Failures revoke graduation (safety measure) — re-graduation requires N new consecutive successes
- `get_recommended_fix()` returns best fix for a detection type (prefers graduated)
- Full serialization/deserialization for persistence (`to_dict()` / `from_dict()`)
- Statistics API: total patterns, graduated count, overall success rate

**Tests:** 26 new tests in `test_playbook_graduation.py`
