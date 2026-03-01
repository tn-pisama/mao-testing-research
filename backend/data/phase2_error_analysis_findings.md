# Phase 2: Error Analysis Findings

Date: 2026-02-28
Calibration run: error_analysis_20260301_011044.json

## Executive Summary

Reading every FP and FN for the 6 weak detectors reveals that **most failures are caused by a small number of code bugs, not by fundamental detection difficulty**. Of 56 total errors across 6 detectors:

| Category | Count | % | Action |
|----------|-------|---|--------|
| Deterministic fix (code bug) | 42 | 75% | Fix the code |
| Threshold sensitivity | 4 | 7% | Adjust thresholds/confidence formulas |
| Golden data issue | 3 | 5% | Re-label or accept as borderline |
| Genuine ambiguity | 4 | 7% | Leave for LLM judge or accept |
| Missing feature | 3 | 5% | New detection capability needed |

The three highest-impact fixes:
1. **Decomposition parser regex** - fixes all 15 FPs (single bug)
2. **Completion adapter subtask status** - fixes all 10 FPs (single bug)
3. **Specification stemming/synonyms** - fixes 11 of 13 FPs (systematic gap)

---

## Per-Detector Findings

### 1. DECOMPOSITION (15 FP, 0 FN) - P=0.500, R=1.000

**Root Cause: Single parser bug causes ALL 15 FPs**

`_parse_subtasks()` regex uses `(?:^|\n)` prefix + `[^\n]+` greedy capture. Golden data negative samples use single-line format (`Step 1: ... Step 2: ... Step 3: ...` with no newlines). The regex matches only `Step 1:` at `^`, then `[^\n]+` eats the ENTIRE rest of the string. Result: every entry parsed as 1 mega-subtask instead of 5-9 subtasks. `WRONG_GRANULARITY` fires on all.

**Fix**: Replace greedy `[^\n]+` with lookahead-based split:
```
Current:  r'(?:step|task|subtask)\s*\d*[:.]\s*([^\n]+)'
Fixed:    r'(?:step|task|subtask)\s*\d*[:.]\s*(.*?)(?=\s*(?:step|task|subtask)\s*\d*[:.]|$)'
```

**Secondary**: Add missing action verbs ("handle", "index", "containerize") to reduce 3 residual VAGUE_SUBTASK flags after parser fix.

**Category**: All 15 = deterministic fix
**Expected impact**: P 0.500 -> ~0.91+, F1 0.667 -> ~0.90+

---

### 2. GROUNDING (6 FP, 6 FN) - P=0.647, R=0.647

**FP Root Cause (5/6): Word overlap tokenization doesn't strip punctuation**

"budget:" != "budget", "$180M," != "$180M.", "users:" != "users". Punctuation attached to tokens breaks matching. One FP (boost_17) is threshold sensitivity (rounding 487->500 is acceptable paraphrasing).

**FN Root Cause (4/6): Claim indicator verb list too narrow**

`_extract_claims()` requires indicator verbs (is, was, were, reached, shows, states...) but misses: "announced", "guarantees", "requires", "improved", "decreased", "showed". With zero claims extracted, grounding_score defaults to 1.0 (= no problem detected). Two FNs are golden data borderline cases.

**Additional bugs**:
- Sentence splitting `re.split(r'[.!?]+', text)` breaks on decimal points ("$42.5M" -> "$42" + "5M")
- Number regex `\b\d[\d,.]*\b` misses unit-attached numbers (10mg, $500K)

**Fixes (priority order)**:
1. Strip punctuation from word tokens before overlap comparison
2. Add 10+ missing claim indicator verbs
3. Fix sentence splitting to respect decimal points in numbers
4. Add abbreviation expansion (K=000, RPS=requests per second)

**Category**: 9 deterministic fix, 1 threshold sensitivity, 2 golden data issue
**Expected impact**: P 0.647 -> ~0.85, R 0.647 -> ~0.80, F1 0.647 -> ~0.82

---

### 3. COMPLETION (10 FP, 5 FN) - P=0.524, R=0.688

**FP Root Cause (10/10): Calibration adapter marks all subtasks as "pending"**

The adapter in `calibrate.py:352-357` converts golden dataset subtask names to `{"name": s, "status": "pending"}`. The detector's `_analyze_subtasks()` checks status against ["complete", "completed", "done", "success", "passed"], so ALL subtasks show as incomplete (0/N). Combined with any completion claim, this triggers IGNORED_SUBTASKS on every sample with subtasks.

**FN Root Cause (4/5): Planned work verb list too narrow, contractions missed**

The planned_work pattern `\bwill\s+(added|implemented|included|covered)` misses: "I'll" (contraction), "optimize", "fix", "handle", "address". The deferred_work pattern misses "next sprint", "backlog", "follow-up".

**Additional bugs**:
- ERROR_PATTERNS context-blind: "error codes" (domain term), "success/failure" (describing conditions), "3 failed" (in context of "Fixed all 3 failures") all trigger false errors
- Criteria keyword matching too strict: "sortable"!="sort", "handled"!="handles" (no stemming)

**Fixes**:
1. Fix adapter: infer subtask completion from agent_output text, or pass subtasks with neutral status
2. Expand planned_work verbs + add contraction handling ("I'll")
3. Add context check to ERROR_PATTERNS (skip when preceded by "fixed", "resolved", or when the word is part of a compound term)
4. Add "sprint", "backlog", "follow-up" to deferred_work patterns

**Category**: 10 deterministic fix (FPs), 4 deterministic fix (FNs), 1 genuine ambiguity
**Expected impact**: P 0.524 -> ~0.80, R 0.688 -> ~0.80, F1 0.595 -> ~0.80

---

### 4. SPECIFICATION (13 FP, 1 FN) - P=0.519, R=0.933

**FP Root Cause (11/13): Keyword matching without stemming, acronyms, or noun synonyms**

The `_semantic_coverage` falls back to keyword matching when embeddings are unavailable (which is the case during calibration). The synonym dictionary covers verbs but misses:
- Pluralization: "profiles" != "profile"
- Stemming: "resize" != "resizes", "runs" != "run"
- Acronyms: "CRUD" not expanded to create/read/update/delete, "CI" not expanded
- Noun synonyms: "purchase" != "order", "pipeline" != "workflow", "catalog" != "category"
- Compound words: "microservices" != "services"

With these gaps, keyword coverage drops to 0.000 on well-aligned specs, mapping to confidence 0.950 (severe). Two entries need re-verification (may only be FPs with LLM judge interaction).

**Fixes**:
1. Add stemming (Porter/Snowball) to keyword comparison
2. Add acronym expansion table (CRUD, CI, API, SSO, etc.)
3. Expand noun synonym dictionary ("purchase"/"order"/"buy", "pipeline"/"workflow"/"process")
4. Strip trailing 's' as minimal pluralization fallback

**Category**: 11 deterministic fix, 2 threshold sensitivity, 1 genuine ambiguity (FN)
**Expected impact**: P 0.519 -> ~0.85, F1 0.667 -> ~0.85

---

### 5. HALLUCINATION (1 FP, 5 FN) - P=0.917, R=0.688

**FP Root Cause (1/1): No approximate number matching**

"99%" vs "99.2%" treated as novel number. With only 2 numeric claims, a single "novel" number drags grounding_ratio below 0.65 threshold.

**FN Root Cause (3/5): Number/proper noun regex blindspots**

- `\b\d[\d,.]*\b` can't match unit-attached numbers: "10mg", "$500K", "25mg" (no word boundary between digits and letters)
- `[A-Z][a-z]+(\s+[A-Z][a-z]+)+` misses ALL-CAPS acronyms: "AWS", "EKS", "GKE"
- Technical identifiers missed: "c5.2xlarge", "n2-highcpu-8"

**Category**: 4 deterministic fix, 1 threshold sensitivity, 1 genuine ambiguity
**Expected impact**: P stays ~0.92, R 0.688 -> ~0.81, F1 0.786 -> ~0.86

---

### 6. COORDINATION (7 FP, 3 FN) - P=0.650, R=0.812

**FP Root Cause 1 (5/7): `limited_communication` assumes mesh topology**

The rule "each agent must communicate with >50% of peers" fires false positives on: pipelines (neg_001), hierarchies (extra_002), fan-out (boost_11), pub/sub (boost_14), terminal nodes (neg_003). These are all valid architectural patterns.

**FP Root Cause 2 (2/7): `excessive_back_forth` threshold too low**

`max_back_forth_count = 3` flags any 2-agent pair with 4+ messages. Normal request-ack protocols (boost_10) and progress reporting (boost_16) easily exceed this.

**FN Root Cause (3/3): Missing features**

All 3 FNs require capabilities the detector doesn't have:
- Timestamp gap analysis (boost_17: 14-second delay)
- Reply-chain routing validation (boost_18: response bypasses delegator)
- Instruction contradiction detection (boost_20: cancel + re-assign)

All 3 are tagged "borderline" with low expected confidence.

**Fixes**:
1. Fix `limited_communication`: only flag agents that have been addressed by others but fail to respond, or require at least 1 outgoing message before checking breadth
2. Raise `excessive_back_forth` threshold from 3 to 5-6
3. (Deferred) Consider adding delay/contradiction sub-detectors as new features

**Category**: 7 deterministic fix (FPs), 2 golden data / genuine ambiguity (FNs), 1 missing feature (FN)
**Expected impact**: P 0.650 -> ~0.87, R stays ~0.81, F1 0.722 -> ~0.84

---

## Revised Phase 3 Plan (based on findings)

Original plan had speculative fixes. Error analysis shows which ones matter:

| Detector | Original Plan Fix | Keep/Drop | Why |
|----------|-------------------|-----------|-----|
| Decomposition: tighten vagueness | DROP | The real bug is the parser regex, not vagueness detection |
| Decomposition: orphan subtask detection | DROP | No FNs to fix |
| Grounding: synonym groups | MODIFY | Word overlap punctuation stripping is the actual FP fix |
| Grounding: context-aware numbers | DROP | Not the root cause |
| Grounding: implicit citations | MODIFY | Real fix is expanding claim indicator verbs |
| Completion: self-contradiction | DROP | Real bug is adapter subtask status |
| Completion: ensemble gate exemptions | DROP | Ensemble gate not the issue |
| Specification: reformulation exemption | DROP | Real bug is missing stemming/synonyms |
| Specification: constraint violations | KEEP | Still valid for FN reduction |
| Hallucination: reduce novelty floor | MODIFY | Real fix is approximate number matching |
| Hallucination: temporal inconsistency | DROP | Not observed in actual FNs |
| Coordination: incomplete handoffs | DROP | FN patterns are missing features, not handoff tracking |
| Coordination: expand delegation patterns | DROP | FNs are too different from delegation issues |

### Priority-ordered fix list (from error analysis)

1. **Decomposition: fix `_parse_subtasks()` regex** - eliminates 15/15 FPs
2. **Completion: fix adapter subtask status** - eliminates 10/10 FPs
3. **Specification: add stemming + acronym expansion + noun synonyms** - eliminates 11/13 FPs
4. **Grounding: strip punctuation from word tokens** - eliminates 5/6 FPs
5. **Grounding: expand claim indicator verbs** - eliminates 4/6 FNs
6. **Coordination: fix `limited_communication` for non-mesh topologies** - eliminates 5/7 FPs
7. **Coordination: raise `excessive_back_forth` threshold** - eliminates 2/7 FPs
8. **Hallucination: fix number regex for unit-attached numbers** - eliminates 3/5 FNs
9. **Hallucination: add approximate number matching** - eliminates 1/1 FP
10. **Hallucination: extend proper noun regex for ALL-CAPS** - eliminates 1/5 FNs
11. **Grounding: fix sentence splitting for decimal points** - reduces 2 FPs + 1 FN
12. **Completion: expand planned_work verbs + contractions** - eliminates 4/5 FNs
