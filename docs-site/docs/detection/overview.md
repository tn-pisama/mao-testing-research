# Detection Overview

PISAMA detects **21 failure modes** in multi-agent LLM systems, organized by the [MAST taxonomy](https://arxiv.org/abs/2503.13657) (NeurIPS 2025 Spotlight) with extensions for enterprise use cases.

## Failure Mode Summary

| MAST ID | Name | Key | Category | Tier | F1 | Status |
|---|---|---|---|---|---|---|
| F1 | Specification Mismatch | `specification` | Planning | ICP | 0.703 | Beta |
| F2 | Poor Task Decomposition | `decomposition` | Planning | ICP | 0.727 | Beta |
| F3 | Resource Misallocation | `resource_misallocation` | Planning | Enterprise | -- | Dev |
| F4 | Inadequate Tool Provision | `tool_provision` | Planning | Enterprise | -- | Dev |
| F5 | Flawed Workflow Design | `workflow` | Planning | ICP | 0.797 | Beta |
| F6 | Task Derailment | `derailment` | Execution | ICP | 0.820 | Production |
| F7 | Context Neglect | `context` | Execution | ICP | 0.868 | Production |
| F8 | Information Withholding | `withholding` | Execution | ICP | 0.874 | Production |
| F9 | Role Usurpation | `role_usurpation` | Execution | Enterprise | -- | Dev |
| F10 | Communication Breakdown | `communication` | Execution | ICP | 0.818 | Production |
| F11 | Coordination Failure | `coordination` | Execution | ICP | 0.797 | Beta |
| F12 | Output Validation Failure | `output_validation` | Verification | Enterprise | -- | Dev |
| F13 | Quality Gate Bypass | `quality_gate` | Verification | Enterprise | -- | Dev |
| F14 | Completion Misjudgment | `completion` | Verification | ICP | 0.745 | Beta |
| -- | Loop Detection | `loop` | Extended | ICP | 0.846 | Production |
| -- | Context Overflow | `overflow` | Extended | ICP | 0.823 | Production |
| -- | Prompt Injection | `injection` | Extended | ICP | 0.944 | Production |
| -- | Hallucination | `hallucination` | Extended | ICP | 0.772 | Beta |
| -- | Grounding Failure | `grounding` | Extended | ICP | 0.671 | Emerging |
| -- | Retrieval Quality | `retrieval_quality` | Extended | Enterprise | 0.824 | Production |
| -- | Persona Drift | `persona_drift` | Extended | ICP | 0.932 | Production |
| -- | State Corruption | `corruption` | Extended | ICP | 0.906 | Production |
| -- | Cost Tracking | `cost` | Extended | ICP | N/A | Production |

## Status Definitions

| Status | F1 Threshold | Meaning |
|---|---|---|
| **Production** | >= 0.80 | Reliable for production use |
| **Beta** | 0.70 - 0.79 | Usable but may have false positives/negatives |
| **Emerging** | < 0.70 | Under active improvement |
| **Dev** | Not yet calibrated | Enterprise-only, benchmarking in progress |

## Detection by Category

### [Planning Failures (FC1)](failure-modes/planning.md)

Problems in how tasks are specified, decomposed, and organized:

- **F1 Specification Mismatch**: Output doesn't match user's original requirements
- **F2 Poor Decomposition**: Subtasks are circular, vague, or wrongly granular
- **F3 Resource Misallocation**: Agents compete for shared resources (Enterprise)
- **F4 Tool Provision**: Required tools are missing or misconfigured (Enterprise)
- **F5 Workflow Design**: Unreachable nodes, dead ends, missing error handling

### [Execution Failures (FC2)](failure-modes/execution.md)

Problems during agent runtime:

- **F6 Task Derailment**: Agent goes off-topic (20% prevalence in MAST-Data)
- **F7 Context Neglect**: Agent ignores upstream context
- **F8 Information Withholding**: Agent omits critical information
- **F9 Role Usurpation**: Agent exceeds role boundaries (Enterprise)
- **F10 Communication Breakdown**: Inter-agent messages misunderstood
- **F11 Coordination Failure**: Handoff failures, circular delegation

### [Verification Failures (FC3)](failure-modes/verification.md)

Problems in output validation and completion:

- **F12 Output Validation**: Validation steps skipped or bypassed (Enterprise)
- **F13 Quality Gate Bypass**: Quality thresholds ignored (Enterprise)
- **F14 Completion Misjudgment**: Premature completion claims (40% prevalence for F1.5 in MAST-Data)

### [Extended Detectors](failure-modes/extended.md)

Cross-cutting concerns not in the core MAST taxonomy:

- **Loop Detection**: Agents stuck repeating actions
- **Context Overflow**: Context window exhaustion
- **Prompt Injection**: Attack detection (highest accuracy: F1 0.944)
- **Hallucination**: Fabricated information
- **Grounding Failure**: Claims unsupported by source documents
- **Retrieval Quality**: Wrong or irrelevant documents retrieved (Enterprise)
- **Persona Drift**: Role/personality deviation
- **State Corruption**: Memory/state anomalies
- **Cost Tracking**: Token/cost budget monitoring

## Detection Pipeline

Each trace is analyzed by the `DetectionOrchestrator`, which runs applicable detectors using a cheapest-first strategy:

1. Tier 1: Rule-based (hash, pattern, structural) -- $0.00
2. Tier 2: State delta analysis -- $0.00
3. Tier 3: Embedding similarity -- ~$0.001
4. Tier 4: LLM Judge (Claude) -- ~$0.005-0.05
5. Tier 5: Human review -- variable

Target: **$0.05/trace average**. Most traces resolve at Tier 1-2.

See [Detection Tiers](../concepts/detection-tiers.md) for the full escalation architecture.
