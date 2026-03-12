# Failure Modes

PISAMA detects **21 failure modes** in multi-agent LLM systems, organized into 4 categories based on the [MAST: Multi-Agent System Failure Taxonomy](https://arxiv.org/abs/2503.13657) (NeurIPS 2025 Spotlight).

## Overview

| Category | MAST Code | Modes | Description |
|---|---|---|---|
| Planning Failures | FC1 | F1-F5 | Problems in task specification, decomposition, and workflow design |
| Execution Failures | FC2 | F6-F11 | Problems during agent execution including derailment, withholding, and coordination |
| Verification Failures | FC3 | F12-F14 | Problems in output validation, quality gates, and completion judgment |
| Extended Detectors | -- | 9 modes | Cross-cutting concerns: loops, injection, hallucination, corruption, etc. |

## Tier Classification

- **ICP (Always Available)**: 16 detectors included in all plans
- **Enterprise (Feature Flags Required)**: 5 detectors requiring `ml_detection` or `advanced_evals` feature flags

## All 21 Failure Modes

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
| -- | Cost Tracking | `cost` | Extended | ICP |

## Accuracy Summary

### Production Detectors (F1 >= 0.80)

| Detector | F1 | Precision | Recall | Tier |
|---|---|---|---|---|
| Prompt Injection | 0.944 | 0.983 | 0.908 | ICP |
| Persona Drift | 0.932 | 0.899 | 0.969 | ICP |
| State Corruption | 0.906 | 0.955 | 0.863 | ICP |
| Info Withholding | 0.874 | 0.805 | 0.957 | ICP |
| Context Neglect | 0.868 | 0.805 | 0.943 | ICP |
| Loop Detection | 0.846 | 0.829 | 0.863 | ICP |
| Retrieval Quality | 0.824 | 0.718 | 0.968 | Enterprise |
| Context Overflow | 0.823 | 1.000 | 0.699 | ICP |
| Task Derailment | 0.820 | 0.702 | 0.985 | ICP |
| Communication Breakdown | 0.818 | 0.724 | 0.940 | ICP |

### Beta Detectors (F1 0.70-0.79)

| Detector | F1 | Precision | Recall | Tier |
|---|---|---|---|---|
| Coordination Failure | 0.797 | 0.836 | 0.761 | ICP |
| Flawed Workflow | 0.797 | 0.851 | 0.750 | ICP |
| Hallucination | 0.772 | 0.718 | 0.836 | ICP |
| Completion Misjudgment | 0.745 | 0.687 | 0.814 | ICP |
| Poor Decomposition | 0.727 | 0.727 | 0.727 | ICP |
| Specification Mismatch | 0.703 | 0.592 | 0.866 | ICP |

### Emerging (F1 < 0.70)

| Detector | F1 | Precision | Recall | Tier |
|---|---|---|---|---|
| Grounding Failure | 0.671 | 0.636 | 0.710 | ICP |

For detailed descriptions of each failure mode including real-world examples, detection methods, and sub-types, see the [Detection Reference](../detection/overview.md).

## References

- [MAST: Multi-Agent System Failure Taxonomy](https://arxiv.org/abs/2503.13657) -- NeurIPS 2025 Spotlight
- [Who&When: Automated Failure Attribution](https://arxiv.org/abs/2505.00212) -- ICML 2025 Spotlight
- [AgentErrorTaxonomy & AgentErrorBench](https://arxiv.org/abs/2509.25370) -- October 2025
