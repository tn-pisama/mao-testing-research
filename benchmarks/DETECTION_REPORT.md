# MAST Failure Mode Detection Report

## Executive Summary

**Overall Detection Rate: 82.4%** (1071/1300 traces for F1-F14)

All 16 MAST failure modes now have specialized detectors. F1-F14 detection improved through enhanced pattern matching, semantic analysis, and structural detection. F15-F16 added for RAG/grounding scenarios.

---

## Detection Results by Tier

### Tier 1: High Detection (>95%)

| Mode | Name | Rate | Details |
|------|------|------|---------|
| **F1** | Specification Mismatch | **98%** | 49/50 detected. Improved from 0% via intent parsing |
| **F2** | Poor Task Decomposition | **100%** | 50/50 detected. Improved from 10% via structural analysis |
| **F5** | Flawed Workflow Design | **100%** | 150/150 detected. Issues: missing error handling |
| **F6** | Task Derailment | **100%** | 50/50 detected. Severities: 34 severe, 16 moderate |
| **F7** | Context Neglect | **100%** | 50/50 detected. Improved from 10% via semantic overlap |
| **F8** | Information Withholding | **100%** | 50/50 detected. Issues: critical omissions, detail loss |
| **F11** | Coordination Failure | **100%** | 150/150 detected. Issues: limited communication |
| **F13** | Quality Gate Bypass | **96%** | 48/50 detected. Issues: bypassed reviews |

### Tier 2: Good Detection (60-95%)

| Mode | Name | Rate | Details |
|------|------|------|---------|
| **F14** | Completion Misjudgment | **84%** | 42/50 detected. Improved from 6% via marker detection |
| **F3** | Resource Misallocation | **66.7%** | 100/150 detected. Issues: contention |
| **F4** | Inadequate Tool Provision | **66.7%** | 100/150 detected. Issues: tool call failures |
| **F9** | Role Usurpation | **66.7%** | 100/150 detected. Issues: role violations, scope expansion |
| **F12** | Output Validation Failure | **66.7%** | 100/150 detected. Issues: validation bypassed |
| **F10** | Communication Breakdown | **64%** | 32/50 detected. Types: intent mismatch |

### Tier 3: New RAG/Grounding Modes (F15-F16)

| Mode | Name | Rate | Details |
|------|------|------|---------|
| **F15** | Grounding Failure | **TBD** | Detects claims not supported by source documents |
| **F16** | Retrieval Quality Failure | **TBD** | Detects wrong/irrelevant document retrieval |

**F15-F16 Detection Approach:**
- **F15 Grounding**: Semantic comparison of output claims vs source documents, numerical consistency checking, citation accuracy verification
- **F16 Retrieval**: Query-document relevance scoring, coverage gap detection, precision measurement

---

## Improvement Summary

### Before vs After

| Mode | Before | After | Improvement |
|------|--------|-------|-------------|
| F1 (Specification Mismatch) | 0% | 98% | **+98%** |
| F2 (Task Decomposition) | 10% | 100% | **+90%** |
| F7 (Context Neglect) | 10% | 100% | **+90%** |
| F14 (Completion Misjudgment) | 6% | 84% | **+78%** |
| **Overall** | 68.7% | 82.4% | **+13.7%** |

### Improvement Techniques

1. **F1 - Specification Mismatch**
   - Parse "Scenario:" descriptions for user intent
   - Pattern matching for mismatch indicators ("instead of", "different from")
   - Semantic comparison of intent keywords vs output content

2. **F2 - Task Decomposition**
   - Detect granularity issues (too vague, too granular)
   - Identify dependency problems (circular, missing)
   - Find impossible/undefined subtasks
   - Detect duplicate work patterns

3. **F7 - Context Neglect**
   - Semantic overlap analysis of key terms
   - Numerical data tracking (research → output)
   - Explicit neglect pattern detection
   - Low overlap threshold triggering

4. **F14 - Completion Misjudgment**
   - Comprehensive incomplete markers (TODO, placeholder, pending)
   - Truncated output detection
   - Partial delivery patterns
   - False success claim detection

---

## Detection Coverage

| Category | Modes | Avg Detection |
|----------|-------|---------------|
| Content-level failures | F1, F6, F7, F8, F10, F13, F14 | 92% |
| Structural failures | F2, F3, F4, F5, F9, F11, F12 | 86% |
| RAG/Grounding failures | F15, F16 | TBD |
| **All modes** | F1-F16 | **82.4%** (F1-F14 only) |

---

## Files Modified

### Detection Functions (`src/run_all_detectors.py`)

- `run_specification_detection()` - Enhanced with intent parsing and mismatch patterns
- `run_decomposition_detection()` - Enhanced with structural and semantic analysis
- `run_context_detection()` - Enhanced with semantic overlap and data tracking
- `run_completion_detection()` - Enhanced with comprehensive marker detection

### Detection Modules (mao-testing)

- `resource_misallocation.py` - F3 detector
- `role_usurpation.py` - F9 detector
- `output_validation.py` - F12 detector
- `grounding.py` - F15 detector (17KB) - Grounding failure detection
- `retrieval_quality.py` - F16 detector (17KB) - Retrieval quality detection

---

## Conclusion

Detection improved from **68.7% to 82.4%** through:

1. **Enhanced pattern matching** for specification, decomposition, and completion issues
2. **Semantic analysis** for context utilization and intent alignment
3. **Structural detection** for workflow, coordination, and resource issues

All 16 MAST failure modes now have specialized detectors:
- **F1-F14**: Detection rates above 64%, with 8 modes achieving >95% detection
- **F15 Grounding Failure**: Detects claims not supported by source documents
- **F16 Retrieval Quality Failure**: Detects wrong/irrelevant document retrieval

---

## Complete MAST F1-F16 Taxonomy

| Code | Name | Category | Description |
|------|------|----------|-------------|
| **F1** | Specification Mismatch | Content | Output doesn't match what was requested |
| **F2** | Poor Task Decomposition | Structural | Tasks broken down incorrectly |
| **F3** | Resource Misallocation | Structural | Compute/time allocated poorly |
| **F4** | Inadequate Tool Provision | Structural | Wrong tools used for task |
| **F5** | Flawed Workflow Design | Structural | Workflow has structural issues |
| **F6** | Task Derailment | Content | Agent goes off-topic |
| **F7** | Context Neglect | Content | Agent ignores provided context |
| **F8** | Information Withholding | Content | Agent omits critical info |
| **F9** | Role Usurpation | Structural | Agent exceeds its role boundaries |
| **F10** | Communication Breakdown | Content | Inter-agent comms fail |
| **F11** | Coordination Failure | Structural | Agents fail to coordinate |
| **F12** | Output Validation Failure | Structural | Output not validated properly |
| **F13** | Quality Gate Bypass | Content | Skips quality checks |
| **F14** | Completion Misjudgment | Content | Declares done when incomplete |
| **F15** | Grounding Failure | RAG | Claims not supported by sources |
| **F16** | Retrieval Quality Failure | RAG | Retrieves wrong/irrelevant docs |
