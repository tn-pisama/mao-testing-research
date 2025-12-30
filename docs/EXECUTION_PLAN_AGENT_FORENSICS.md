# Agent Forensics Pivot - Execution Plan

**Branch**: `pivot/agent-forensics`
**Date**: December 2025
**Status**: In Progress

---

## Agent Review Summary

### Key Insights from 5 Review Agents

| Agent | Key Finding | Impact on Plan |
|-------|-------------|----------------|
| **Backend Architect** | 80%+ code reusable. Main work: UniversalSpan abstraction + diagnose endpoint | Reduces scope significantly |
| **Detection Engineer** | 15+ detectors exist; most need minor single-agent mode additions | Prioritize HIGH priority detectors only |
| **Frontend Reviewer** | 70% component reuse. Need /diagnose page + 5 new components | Follow existing patterns |
| **Competitive Strategist** | "Self-healing" is the moat, not just detection. Lead with auto-fix | **Adjust positioning** |
| **SDK Reviewer** | Existing span/session models need UniversalSpan conversion | Add importer layer |

---

## Adjusted Strategy Based on Feedback

### Original Plan Adjustments

| Original | Adjusted | Reason |
|----------|----------|--------|
| "Paste your trace" as entry point | Keep but add **self-healing demo** as key feature | Competitive differentiation |
| Open source single-agent debugger | **Delay OSS decision**; validate commercial first | Risk of giving away 90% value |
| Generic "Agent Forensics" positioning | Lead with **"Self-Healing AI Agents"** | Stronger moat |
| Build all importers upfront | Start with **JSON paste + LangSmith only** | Faster validation |

---

## Phase 1: Core Infrastructure (This Sprint)

### 1.1 UniversalSpan Abstraction
**File**: `backend/app/ingestion/universal_trace.py`

```python
@dataclass
class UniversalSpan:
    id: str
    trace_id: str
    span_type: SpanType  # AGENT, TOOL_CALL, LLM_CALL, HANDOFF
    name: str
    start_time: datetime
    end_time: datetime
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    agent_id: Optional[str] = None
    tool_name: Optional[str] = None
    error: Optional[str] = None
    tokens_used: int = 0
    metadata: Dict[str, Any]
```

### 1.2 Importers
**Directory**: `backend/app/ingestion/importers/`

Priority order:
1. `raw_json.py` - Generic JSON paste (Day 1)
2. `langsmith.py` - LangSmith traces (Day 2)
3. `otel.py` - OpenTelemetry (adapt existing)

### 1.3 Diagnose Endpoint
**File**: `backend/app/api/v1/diagnose.py`

```
POST /api/v1/diagnose/why-failed
  - Accept raw trace JSON
  - Auto-detect format
  - Run detection suite
  - Return root cause + suggested fixes
  - Include self-healing preview
```

### 1.4 Detection Orchestrator
**File**: `backend/app/detection/orchestrator.py`

Aggregate all detectors:
- Priority HIGH: loop, overflow, corruption, coordination, withholding, tool_provision
- Run in parallel, aggregate results
- Generate LLM explanation

---

## Phase 2: Frontend (Next Sprint)

### 2.1 New Pages
- `/diagnose` - Main paste interface

### 2.2 New Components
```
frontend/src/components/diagnose/
├── TracePasteInput.tsx      # Paste/drop interface
├── DiagnosisResults.tsx     # Results container
├── RootCauseCard.tsx        # Root cause with confidence
├── EvidenceChain.tsx        # Step-by-step evidence
├── SuggestedFixPanel.tsx    # Fix with "Apply" button
└── SelfHealingPreview.tsx   # Self-healing demo (differentiator)
```

### 2.3 Reusable Existing Components
- ConfidenceBadge, FailureCard, TraceTimeline, TraceViewer
- Button, Badge, Layout, Tabs, EmptyState, LoadingSkeleton

---

## Phase 3: Self-Healing Integration

### Key Differentiator
Per competitive analysis, "self-healing" is the moat. Integrate existing healing engine:

```
backend/app/healing/
├── analyzer.py   # FailureAnalyzer → already works
├── engine.py     # SelfHealingEngine → wire to diagnose
└── applicator.py # Fix application → demo capability
```

Add to diagnose response:
```json
{
  "root_cause": {...},
  "suggested_fixes": [...],
  "self_healing_available": true,
  "auto_fix_preview": {
    "description": "We can fix this automatically",
    "confidence": 0.87,
    "action": "Apply prompt guard to prevent loop"
  }
}
```

---

## Implementation Order

| Day | Task | Files | Priority |
|-----|------|-------|----------|
| 1 | Create UniversalSpan abstraction | `backend/app/ingestion/universal_trace.py` | CRITICAL |
| 1 | Create importer base class | `backend/app/ingestion/importers/base.py` | CRITICAL |
| 1 | Implement raw JSON importer | `backend/app/ingestion/importers/raw_json.py` | CRITICAL |
| 2 | Create diagnose API endpoint | `backend/app/api/v1/diagnose.py` | CRITICAL |
| 2 | Create detection orchestrator | `backend/app/detection/orchestrator.py` | CRITICAL |
| 2 | Add diagnosis schemas | `backend/app/api/v1/schemas.py` | CRITICAL |
| 3 | Wire to healing engine | `backend/app/api/v1/diagnose.py` | HIGH |
| 3 | Create LangSmith importer | `backend/app/ingestion/importers/langsmith.py` | HIGH |
| 4 | Frontend: TracePasteInput | `frontend/src/components/diagnose/` | HIGH |
| 4 | Frontend: /diagnose page | `frontend/src/app/diagnose/page.tsx` | HIGH |
| 5 | Frontend: Results components | `frontend/src/components/diagnose/` | MEDIUM |
| 5 | CLI diagnose command | `mao/cli/diagnose.py` | MEDIUM |
| 6 | Integration testing | Tests | MEDIUM |
| 6 | Documentation | docs/ | LOW |

---

## Success Criteria

### Phase 1 Complete When:
- [ ] Can paste raw JSON trace and get diagnosis
- [ ] Diagnosis includes root cause with confidence
- [ ] Suggested fixes are generated
- [ ] Self-healing preview is shown (differentiator)

### Phase 2 Complete When:
- [ ] Frontend /diagnose page works end-to-end
- [ ] Can visualize evidence chain
- [ ] Can "Apply Fix" (preview only for MVP)

---

## Files to Create/Modify

### New Files (Backend)
```
backend/app/ingestion/
├── universal_trace.py          # NEW: UniversalSpan dataclass
└── importers/
    ├── __init__.py             # NEW: Importer registry
    ├── base.py                 # NEW: BaseImporter ABC
    ├── raw_json.py             # NEW: Generic JSON paste
    └── langsmith.py            # NEW: LangSmith format

backend/app/api/v1/
└── diagnose.py                 # NEW: /diagnose endpoint

backend/app/detection/
└── orchestrator.py             # NEW: Detection aggregator
```

### Modified Files (Backend)
```
backend/app/main.py             # Mount diagnose router
backend/app/api/v1/schemas.py   # Add diagnosis schemas
```

### New Files (Frontend)
```
frontend/src/app/diagnose/
└── page.tsx                    # NEW: Main diagnose page

frontend/src/components/diagnose/
├── index.ts                    # NEW: Exports
├── TracePasteInput.tsx         # NEW: Paste interface
├── DiagnosisResults.tsx        # NEW: Results container
├── RootCauseCard.tsx           # NEW: Root cause display
├── EvidenceChain.tsx           # NEW: Evidence timeline
├── SuggestedFixPanel.tsx       # NEW: Fix suggestions
└── SelfHealingPreview.tsx      # NEW: Self-healing demo
```

### Modified Files (Frontend)
```
frontend/src/components/common/Layout.tsx  # Add /diagnose nav
frontend/src/lib/api.ts                    # Add diagnose methods
```

### New Files (CLI)
```
mao/cli/diagnose.py             # NEW: diagnose command
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Detection accuracy insufficient | Use existing TieredDetector with LLM escalation |
| Self-healing too complex for MVP | Demo preview only, full apply in v2 |
| Format auto-detection fails | Start with explicit format selection |
| Frontend complexity | Reuse 70% existing components |

---

## Next Steps (Immediate)

1. Create `backend/app/ingestion/universal_trace.py`
2. Create `backend/app/ingestion/importers/` directory with base + raw_json
3. Create `backend/app/api/v1/diagnose.py` endpoint
4. Create `backend/app/detection/orchestrator.py`
5. Test with sample traces

---

*Plan created based on feedback from 5 specialized review agents*
