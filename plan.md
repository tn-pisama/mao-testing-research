# Plan: Compound Failure Analysis (Multi-Failure-Mode Traces)

## Current State

The system **does** run all 17 detectors and return all findings. But it treats each detection as independent — there is no understanding of how failures **relate to each other**.

### What exists
- `analyze_conversation_turns()` runs all detectors, returns flat list
- `_pick_primary()` selects by (severity, confidence) — no causal reasoning
- `_generate_root_cause()` mentions "Additional issues" as a comma-joined string
- `DiagnoseResponse.all_detections` is a flat `List[DiagnoseDetectionResult]`
- Frontend renders a flat list under "Problems Found"

### What's missing
1. **No co-occurrence awareness** — F9 (Role Usurpation) always co-occurs with F1/F3/F5/F7/F8/F11/F12/F14 per MAST research, but the system doesn't know this
2. **No root-cause vs symptom distinction** — If F5 (Flawed Workflow) causes F7 (Context Neglect), both are reported at equal standing
3. **No failure clustering** — 5 detections could represent 2 distinct problems, but they're shown as 5 separate items
4. **No confidence adjustment** — Co-occurring failures that are known pairs should boost each other's confidence; unlikely combinations should be flagged
5. **No causal chain** — "Loop caused context overflow which caused hallucination" is a chain, not 3 independent problems

## Plan

### Step 1: Create Compound Failure Analyzer module

**File**: `backend/app/detection/compound_failures.py` (~250 lines)

A post-detection analysis layer that takes the flat list of detections and enriches it with relationship data:

```
Input:  List[detection_results]  (flat, independent)
Output: CompoundAnalysis {
    clusters: List[FailureCluster]     — grouped related failures
    causal_chains: List[CausalChain]   — ordered root→symptom sequences
    co_occurrence_notes: List[str]      — known pattern matches
    adjusted_detections: List[...]      — detections with updated confidence
    primary_root_cause: str             — the deepest root cause (not just highest severity)
}
```

Key components:

- **CO_OCCURRENCE_MAP**: Static dict encoding known MAST co-occurrence patterns
  - `F9 → [F1, F3, F5, F7, F8, F11, F12, F14]` (from MAST research)
  - `F5 (Flawed Workflow) → [F6 (Derailment), F7 (Context Neglect)]` (workflow failures cascade)
  - `F10 (Communication) → [F11 (Coordination)]` (communication breakdown causes coordination failure)
  - Other empirical patterns from the MAST taxonomy

- **CAUSAL_PRECEDENCE**: Dict mapping which failures tend to be causes vs symptoms
  - Root causes: F1 (Specification), F2 (Decomposition), F5 (Workflow)
  - Symptoms: F6 (Derailment), F7 (Context Neglect), F14 (Completion Misjudgment)
  - Contextual: F3 (Resource), F8 (Withholding), F9 (Usurpation)

- **`analyze_compound(detections) -> CompoundAnalysis`**: Main function that:
  1. Maps detections to failure modes (F1-F17)
  2. Identifies known co-occurrence patterns
  3. Builds causal chains using precedence ordering
  4. Clusters related failures (shared spans, temporal proximity, known pairs)
  5. Adjusts confidence: boost for known pairs, flag for unusual combinations
  6. Picks a true root cause (deepest in causal chain, not just highest severity)

### Step 2: Add schema types for compound analysis

**File**: `backend/app/api/v1/schemas.py` (extend existing)

Add:
- `FailureCluster`: group name, member detections, relationship type
- `CausalChain`: ordered list of failure modes from root to symptom
- `CompoundAnalysisResult`: clusters, chains, notes, adjusted primary

Extend `DiagnoseResponse` with:
- `compound_analysis: Optional[CompoundAnalysisResult]` — only populated when 2+ failures detected

### Step 3: Integrate into diagnose endpoint

**File**: `backend/app/api/v1/diagnose.py` (modify existing)

After collecting all detections, call `analyze_compound()` when `len(all_detections) >= 2`.
Use compound analysis to:
- Replace simple `_pick_primary()` with causal-root-cause selection
- Enrich `root_cause_explanation` with causal chain narrative
- Populate new `compound_analysis` field in response

### Step 4: Frontend compound failure display

**File**: `frontend/src/components/diagnose/DiagnosisResults.tsx` (modify existing)

When `compound_analysis` is present:
- Show failure clusters as grouped cards instead of flat list
- Render causal chain as a simple arrow diagram (F5 → F7 → F14)
- Badge known co-occurrence patterns ("Known pattern: Role Usurpation + Coordination Failure")
- Highlight root cause vs symptoms visually (root = red border, symptom = muted)

### Step 5: Tests for compound analysis

**File**: `backend/tests/test_compound_failures.py` (~200 lines)

Test cases:
- Single failure: no compound analysis
- Two known co-occurring failures (F9 + F11): should cluster and identify pattern
- Causal chain (F5 → F6 → F14): should order correctly
- Confidence adjustment: known pair boosts, unusual pair flags
- Root cause selection: picks deepest cause, not just highest severity
- Real-world scenario: 5 simultaneous failures grouped into 2 clusters
