# Detection Overview

Pisama detects **43 failure modes** across general-purpose and platform-specific detectors, organized by the [MAST taxonomy](https://arxiv.org/abs/2503.13657) with extensions for enterprise use cases. **29 detectors** are production-grade (F1 >= 0.80).

## Failure Mode Summary

| MAST ID | Name | Key | Category | Tier | F1 | Status |
|---|---|---|---|---|---|---|
| F1 | Specification Mismatch | `specification` | Planning | ICP | 0.747 | Beta |
| F2 | Poor Task Decomposition | `decomposition` | Planning | ICP | 0.746 | Beta |
| F3 | Resource Misallocation | `resource_misallocation` | Planning | Enterprise | -- | Dev |
| F4 | Inadequate Tool Provision | `tool_provision` | Planning | Enterprise | -- | Dev |
| F5 | Flawed Workflow Design | `workflow` | Planning | ICP | 0.692 | Emerging |
| F6 | Task Derailment | `derailment` | Execution | ICP | 0.800 | Production |
| F7 | Context Neglect | `context` | Execution | ICP | 0.731 | Beta |
| F8 | Information Withholding | `withholding` | Execution | ICP | 0.796 | Beta |
| F9 | Role Usurpation | `role_usurpation` | Execution | Enterprise | -- | Dev |
| F10 | Communication Breakdown | `communication` | Execution | ICP | 0.821 | Production |
| F11 | Coordination Failure | `coordination` | Execution | ICP | 0.912 | Production |
| F12 | Output Validation Failure | `output_validation` | Verification | Enterprise | -- | Dev |
| F13 | Quality Gate Bypass | `quality_gate` | Verification | Enterprise | -- | Dev |
| F14 | Completion Misjudgment | `completion` | Verification | ICP | 0.718 | Beta |
| -- | Loop Detection | `loop` | Extended | ICP | 0.780 | Beta |
| -- | Context Overflow | `overflow` | Extended | ICP | 0.878 | Production |
| -- | Prompt Injection | `injection` | Extended | ICP | 0.745 | Beta |
| -- | Hallucination | `hallucination` | Extended | ICP | 0.755 | Beta |
| -- | Grounding Failure | `grounding` | Extended | ICP | 0.599 | Emerging |
| -- | Retrieval Quality | `retrieval_quality` | Extended | ICP | 0.551 | Emerging |
| -- | Persona Drift | `persona_drift` | Extended | ICP | 0.774 | Beta |
| -- | State Corruption | `corruption` | Extended | ICP | 0.832 | Production |
| -- | Convergence | `convergence` | Extended | ICP | 0.855 | Production |
| -- | Delegation | `delegation` | Extended | ICP | 0.841 | Production |
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
- **Prompt Injection**: Attack detection
- **Hallucination**: Fabricated information
- **Grounding Failure**: Claims unsupported by source documents
- **Retrieval Quality**: Wrong or irrelevant documents retrieved
- **Persona Drift**: Role/personality deviation
- **State Corruption**: Memory/state anomalies
- **Convergence**: Metric plateau, regression, thrashing, divergence detection
- **Cost Tracking**: Token/cost budget monitoring

## Platform-Specific Detectors

In addition to the general-purpose detectors above, Pisama includes 24 platform-specific detectors (6 per platform) that catch issues unique to each framework's architecture:

- **[n8n](failure-modes/n8n.md)** (6): Schema mismatch, workflow cycles, complexity, error handling, resource exhaustion, timeouts
- **[LangGraph](failure-modes/langgraph.md)** (6): Recursion limits, state corruption, edge misrouting, tool failures, parallel sync, checkpoint corruption
- **[Dify](failure-modes/dify.md)** (6): RAG poisoning, iteration escape, silent model fallback, variable leakage, classifier drift, tool schema mismatch
- **[OpenClaw](failure-modes/openclaw.md)** (6): Session loops, tool abuse, elevated privilege risk, spawn chain depth, channel mismatch, sandbox escape

These run automatically when traces from the corresponding platform are ingested.

## Detection Pipeline

Each trace is analyzed by the `DetectionOrchestrator`, which runs applicable detectors using a cheapest-first strategy:

1. Tier 1: Rule-based (hash, pattern, structural) -- $0.00
2. Tier 2: State delta analysis -- $0.00
3. Tier 3: Embedding similarity -- ~$0.001
4. Tier 4: LLM Judge (Claude) -- ~$0.005-0.05
5. Tier 5: Human review -- variable

Target: **$0.05/trace average**. Most traces resolve at Tier 1-2.

See [Detection Tiers](../concepts/detection-tiers.md) for the full escalation architecture.
