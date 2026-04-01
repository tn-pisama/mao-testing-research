# Failure Modes

Pisama detects **25 failure modes** in multi-agent LLM systems, organized into 4 categories based on the [MAST: Multi-Agent System Failure Taxonomy](https://arxiv.org/abs/2503.13657).

## Overview

| Category | MAST Code | Modes | Description |
|---|---|---|---|
| Planning Failures | FC1 | F1-F5 | Problems in task specification, decomposition, and workflow design |
| Execution Failures | FC2 | F6-F11 | Problems during agent execution including derailment, withholding, and coordination |
| Verification Failures | FC3 | F12-F14 | Problems in output validation, quality gates, and completion judgment |
| Extended Detectors | -- | 11 modes | Cross-cutting concerns: loops, injection, hallucination, corruption, convergence, etc. |

## Tier Classification

- **ICP (Always Available)**: 18 detectors included in all plans
- **Enterprise (Feature Flags Required)**: 7 detectors requiring `ml_detection` or `advanced_evals` feature flags

## All 25 Failure Modes

| MAST ID | Name | Detector Key | Category | Tier |
|---|---|---|---|---|
| F1 | Specification Mismatch | `specification` | Planning | ICP |
| F2 | Poor Task Decomposition | `decomposition` | Planning | ICP |
| F3 | Resource Misallocation | `resource_misallocation` | Planning | Enterprise |
| F4 | Inadequate Tool Provision | `tool_provision` | Planning | Enterprise |
| F5 | Flawed Workflow Design | `workflow` | Planning | ICP |
| F6 | Task Derailment | `derailment` | Execution | ICP |
| F7 | Context Neglect | `context` | Execution | ICP |
| F8 | Information Withholding | `withholding` | Execution | ICP |
| F9 | Role Usurpation | `role_usurpation` | Execution | Enterprise |
| F10 | Communication Breakdown | `communication` | Execution | ICP |
| F11 | Coordination Failure | `coordination` | Execution | ICP |
| F12 | Output Validation Failure | `output_validation` | Verification | Enterprise |
| F13 | Quality Gate Bypass | `quality_gate` | Verification | Enterprise |
| F14 | Completion Misjudgment | `completion` | Verification | ICP |
| -- | Loop Detection | `loop` | Extended | ICP |
| -- | Context Overflow | `overflow` | Extended | ICP |
| -- | Prompt Injection | `injection` | Extended | ICP |
| -- | Hallucination | `hallucination` | Extended | ICP |
| -- | Grounding Failure | `grounding` | Extended | ICP |
| -- | Retrieval Quality | `retrieval_quality` | Extended | Enterprise |
| -- | Persona Drift | `persona_drift` | Extended | ICP |
| -- | State Corruption | `corruption` | Extended | ICP |
| -- | Convergence | `convergence` | Extended | ICP |
| -- | Delegation | `delegation` | Extended | ICP |
| -- | Cost Tracking | `cost` | Extended | ICP |

## Accuracy Summary

F1 scores from the [Detection Overview](../detection/overview.md) (canonical source).

### Production Detectors (F1 >= 0.80)

| Detector | F1 | Precision | Recall | Tier |
|---|---|---|---|---|
| Coordination Failure | 0.912 | 0.842 | 1.000 | ICP |
| Context Overflow | 0.878 | 1.000 | 0.699 | ICP |
| Convergence | 0.855 | -- | -- | ICP |
| Delegation | 0.841 | -- | -- | ICP |
| State Corruption | 0.832 | 0.870 | 0.952 | ICP |
| Communication Breakdown | 0.821 | 0.724 | 0.940 | ICP |
| Task Derailment | 0.800 | 0.702 | 0.985 | ICP |
| Cost Tracking | N/A | N/A | N/A | ICP |

### Beta Detectors (F1 0.70-0.79)

| Detector | F1 | Precision | Recall | Tier |
|---|---|---|---|---|
| Info Withholding | 0.796 | 0.805 | 0.957 | ICP |
| Loop Detection | 0.780 | 0.829 | 0.863 | ICP |
| Persona Drift | 0.774 | -- | -- | ICP |
| Hallucination | 0.755 | 0.718 | 0.836 | ICP |
| Specification Mismatch | 0.747 | 0.592 | 0.866 | ICP |
| Decomposition | 0.746 | 0.727 | 0.727 | ICP |
| Prompt Injection | 0.745 | -- | -- | ICP |
| Context Neglect | 0.731 | 0.805 | 0.943 | ICP |
| Completion Misjudgment | 0.718 | 0.687 | 0.814 | ICP |

### Emerging (F1 < 0.70)

| Detector | F1 | Precision | Recall | Tier |
|---|---|---|---|---|
| Flawed Workflow | 0.692 | -- | -- | ICP |
| Grounding Failure | 0.599 | 0.636 | 0.710 | ICP |
| Retrieval Quality | 0.551 | -- | -- | Enterprise |

### Dev (Not Yet Calibrated)

Resource Misallocation, Tool Provision, Role Usurpation, Output Validation, Quality Gate -- Enterprise-only, benchmarking in progress.

For detailed descriptions of each failure mode including real-world examples, detection methods, and sub-types, see the [Detection Reference](../detection/overview.md).

## References

- [MAST: Multi-Agent System Failure Taxonomy](https://arxiv.org/abs/2503.13657)
- [Who&When: Automated Failure Attribution](https://arxiv.org/abs/2505.00212) -- ICML 2025 Spotlight
- [AgentErrorTaxonomy & AgentErrorBench](https://arxiv.org/abs/2509.25370) -- October 2025
