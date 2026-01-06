# PISAMA Feature Matrix

**Date:** 2026-01-05
**Version:** 1.0

This document maps features to pricing tiers and code locations.

---

## Feature Flag Configuration

Set these environment variables to enable enterprise features:

```bash
# Master switch (required for any enterprise feature)
FEATURE_ENTERPRISE_ENABLED=true

# Individual feature flags
FEATURE_ML_DETECTION=true
FEATURE_OTEL_INGESTION=true
FEATURE_CHAOS_ENGINEERING=true
FEATURE_TRACE_REPLAY=true
FEATURE_REGRESSION_TESTING=true
FEATURE_ADVANCED_EVALS=true
FEATURE_AUDIT_LOGGING=true
```

---

## Feature Availability by Tier

| Feature | Free | Startup | Growth | Enterprise | Code Location |
|---------|------|---------|--------|------------|---------------|
| **Detection** |
| Loop detection | ✓ | ✓ | ✓ | ✓ | `detection/loop.py` |
| State corruption | ✓ | ✓ | ✓ | ✓ | `detection/corruption.py` |
| Persona drift | ✓ | ✓ | ✓ | ✓ | `detection/persona.py` |
| Coordination analysis | ✓ | ✓ | ✓ | ✓ | `detection/coordination.py` |
| Hallucination | ✓ | ✓ | ✓ | ✓ | `detection/hallucination.py` |
| Injection detection | ✓ | ✓ | ✓ | ✓ | `detection/injection.py` |
| Context overflow | ✓ | ✓ | ✓ | ✓ | `detection/overflow.py` |
| Task derailment | ✓ | ✓ | ✓ | ✓ | `detection/derailment.py` |
| ML-based detection | - | - | - | ✓ | `detection_enterprise/ml_detector.py` |
| Tiered LLM-judge | - | - | - | ✓ | `detection_enterprise/tiered.py` |
| Turn-aware detection | - | - | - | ✓ | `detection_enterprise/turn_aware.py` |
| Quality gate | - | - | - | ✓ | `detection_enterprise/quality_gate.py` |
| **Ingestion** |
| Raw JSON import | ✓ | ✓ | ✓ | ✓ | `ingestion/importers/raw_json.py` |
| Conversation import | ✓ | ✓ | ✓ | ✓ | `ingestion/importers/conversation.py` |
| MAST format | ✓ | ✓ | ✓ | ✓ | `ingestion/importers/mast.py` |
| OTEL native ingestion | - | - | - | ✓ | `ingestion_enterprise/otel.py` |
| LangSmith import | - | - | - | ✓ | `ingestion_enterprise/importers/langsmith.py` |
| **Cost & Analytics** |
| Cost calculation | ✓ | ✓ | ✓ | ✓ | `detection/cost.py` |
| Basic analytics | ✓ | ✓ | ✓ | ✓ | `api/v1/analytics.py` |
| Cost alerts | - | ✓ | ✓ | ✓ | _Planned Phase 2_ |
| ROI metrics | - | - | ✓ | ✓ | _Planned Phase 2_ |
| **Fixes** |
| Fix suggestions | ✓ | ✓ | ✓ | ✓ | `fixes/` |
| Self-healing playbooks | - | - | - | ✓ | `healing/` |
| **Alerting** |
| Email alerts | ✓ | ✓ | ✓ | ✓ | _Planned Phase 1_ |
| Slack integration | - | ✓ | ✓ | ✓ | _Planned Phase 1_ |
| Webhook alerts | - | ✓ | ✓ | ✓ | `api/v1/webhooks.py` |
| PagerDuty | - | - | ✓ | ✓ | _Planned Phase 3_ |
| **Testing & Simulation** |
| Chaos injection | - | - | - | ✓ | `enterprise/chaos/` |
| Trace replay | - | - | - | ✓ | `enterprise/replay/` |
| Regression testing | - | - | - | ✓ | `enterprise/regression/` |
| **Security & Compliance** |
| Basic auth | ✓ | ✓ | ✓ | ✓ | `core/auth.py` |
| API keys | ✓ | ✓ | ✓ | ✓ | `core/security.py` |
| Audit logging | - | - | - | ✓ | `enterprise/audit/` |
| SSO/SAML | - | - | - | ✓ | _Planned Phase 5_ |
| SOC 2 compliance | - | - | - | ✓ | _Planned Phase 5_ |

---

## Directory Structure

```
backend/app/
├── api/
│   ├── v1/                      # ICP API endpoints
│   │   ├── traces.py
│   │   ├── detections.py
│   │   ├── analytics.py
│   │   ├── auth.py
│   │   ├── webhooks.py
│   │   └── ...
│   └── enterprise/              # Enterprise API endpoints
│       ├── chaos.py
│       ├── replay.py
│       ├── regression.py
│       ├── testing.py
│       ├── diagnose.py
│       └── evals.py
├── detection/                   # ICP detectors
│   ├── loop.py
│   ├── corruption.py
│   ├── persona.py
│   ├── coordination.py
│   └── ...
├── detection_enterprise/        # Enterprise detectors
│   ├── ml_detector.py
│   ├── tiered.py
│   ├── turn_aware.py
│   ├── quality_gate.py
│   └── ...
├── ingestion/                   # ICP ingestion
│   ├── importers/
│   │   ├── raw_json.py
│   │   ├── conversation.py
│   │   └── mast.py
│   └── ...
├── ingestion_enterprise/        # Enterprise ingestion
│   ├── otel.py
│   └── importers/
│       ├── otel.py
│       └── langsmith.py
├── enterprise/                  # Full enterprise modules
│   ├── chaos/
│   ├── replay/
│   ├── regression/
│   ├── testing/
│   ├── evals/
│   ├── integrations/
│   └── audit/
├── fixes/                       # ICP (fix suggestions)
├── healing/                     # Phase 4 (self-healing MVP)
├── core/                        # ICP (auth, security, etc.)
│   ├── auth.py
│   ├── security.py
│   ├── feature_gate.py          # Feature flag decorator
│   └── ...
└── config.py                    # Feature flag configuration
```

---

## Feature Flag Decorator Usage

```python
from app.core.feature_gate import require_enterprise, Features

@router.post("/chaos/inject")
@require_enterprise(Features.CHAOS_ENGINEERING)
async def inject_chaos(request: ChaosRequest):
    """Endpoint requires chaos_engineering feature flag."""
    pass
```

Returns HTTP 402 (Payment Required) when feature is not enabled.

---

## Import Rules

1. **ICP code MUST NOT import from enterprise modules**
   - `detection/` cannot import from `detection_enterprise/`
   - `ingestion/` cannot import from `ingestion_enterprise/`
   - `api/v1/` cannot import from `api/enterprise/`

2. **Enterprise code CAN import from ICP modules**
   - `detection_enterprise/` can import from `detection/`
   - `enterprise/` can import from `core/`, `fixes/`, etc.

3. **Conditional imports at module boundaries**
   - Use `is_feature_enabled()` to conditionally load enterprise code
   - Wrap imports in try/except for graceful degradation

---

## CI Configuration

```yaml
# .github/workflows/test.yml
jobs:
  test-icp:
    name: Test ICP Features
    env:
      FEATURE_ENTERPRISE_ENABLED: "false"
    steps:
      - run: pytest tests/icp/

  test-enterprise:
    name: Test Enterprise Features
    env:
      FEATURE_ENTERPRISE_ENABLED: "true"
      FEATURE_ML_DETECTION: "true"
      FEATURE_OTEL_INGESTION: "true"
      FEATURE_CHAOS_ENGINEERING: "true"
      FEATURE_TRACE_REPLAY: "true"
      FEATURE_REGRESSION_TESTING: "true"
      FEATURE_ADVANCED_EVALS: "true"
      FEATURE_AUDIT_LOGGING: "true"
    steps:
      - run: pytest tests/
```

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-05 | Initial feature matrix |
