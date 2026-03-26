# Pisama Detection Capabilities

Multi-agent orchestration testing platform with 45+ failure detectors across 3 tiers.

## Tier 1: ICP Detectors (Always Available)

Pattern-based detection, no LLM calls required. Sub-100ms per detection.

| Detector | What It Detects | F1 |
|----------|----------------|-----|
| loop | Exact, structural, semantic loop detection | 0.652 |
| corruption | State corruption and invalid transitions | 0.857 |
| persona_drift | Persona drift and role confusion | 0.854 |
| coordination | Agent handoff and communication failures (13 methods) | 0.914 |
| hallucination | Factual inaccuracy vs source documents | 0.733 |
| injection | Prompt injection attempts | 0.667 |
| overflow | Context window exhaustion | 0.706 |
| derailment | Task focus deviation | 0.793 |
| context | Context neglect in responses | 0.865 |
| communication | Inter-agent communication breakdown | 0.700 |
| specification | Output vs specification mismatch | 0.721 |
| decomposition | Task breakdown failures | 1.000 |
| workflow | Workflow execution structural issues | 0.667 |
| withholding | Information withholding detection | 0.800 |
| completion | Premature/delayed task completion | 0.703 |
| convergence | Metric plateau, regression, thrashing, divergence | 1.000 |
| delegation | Missing criteria, vague instructions, incomplete handoffs | 0.700 |

### Framework-Specific Detectors

**n8n** (6 detectors): cycle, timeout, schema, resource, error, complexity
**LangGraph** (6): recursion, state_corruption, edge_misroute, tool_failure, parallel_sync, checkpoint_corruption
**Dify** (6): rag_poisoning, iteration_escape, model_fallback, variable_leak, classifier_drift, tool_schema_mismatch
**OpenClaw** (6): session_loop, tool_abuse, elevated_risk, spawn_chain, channel_mismatch, sandbox_escape

## Tier 2: Enterprise Detection

Requires `ml_detection` feature flag.

| Capability | Description | Cost |
|-----------|-------------|------|
| **LLM Judge** | Claude Haiku/Sonnet verification for ambiguous cases | ~$0.01/judgment |
| **SLM Judge** | Fine-tuned Qwen2.5-3B on Modal GPU, 95% accuracy | $0/judgment |
| **Agent-as-Judge** | Multi-step evaluation with episodic memory and 4 tools | ~$0.05/judgment |
| **Tiered Escalation** | Hash → State Delta → Embeddings → LLM → Human (5 tiers) | Cost-proportional |
| **Hybrid Pipeline** | SLM pre-screening → LLM only when needed | 70% cost reduction |

### New: Orchestration Quality Scorer

Dual-mode scoring for multi-agent workflow quality:

**Execution mode** (LangGraph, n8n, Dify traces): 7 dimensions
- Efficiency (makespan ratio), Utilization (Gini), Parallelization (topology-aware), Delegation quality, Communication efficiency, Robustness, Topology alignment

**Conversation mode** (MAST, ChatDev traces): 5 dimensions
- Information flow, Contribution quality, Decision convergence, Role coherence, Task drift

Results: F1=0.853 on 771 MAST traces, F1=0.791 on 574 LangGraph traces.

### New: Multi-Chain Interaction Analyzer

Cross-trace failure detection for linked workflows:
- **Cascade failures**: Weighted causal pairs + temporal causality gate
- **Data corruption propagation**: Semantic comparison (numeric + fuzzy string)
- **Cross-chain loops**: DFS cycle detection on trace graph
- **Redundant work**: >90% input overlap between sibling traces

Results: F1=1.000 on 34 real external data pairs.

## Tier 3: Strategic Capabilities

Competitive moats — no competitor has these.

| Capability | Description | File |
|-----------|-------------|------|
| **Process Reward Model** | Step-level quality scoring using detectors as weak labelers | `process_reward.py` |
| **Causal Intervention** | 8 perturbation types for systematic root cause analysis | `causal_intervention.py` |
| **Predictive Healing** | 5 early warning signals (token exhaustion, quality decline, error spiral, repetition, stall) | `predictive.py` |
| **Semantic Entropy** | Response consistency clustering for hallucination detection | `semantic_entropy.py` |
| **Trajectory Evaluation** | 5-dimensional path scoring (tool selection, efficiency, completeness, ordering, recovery) | `trajectory_evaluator.py` |

## Integrations

Pisama connects to all top 10 production agent platforms:

| Platform | Method | Status |
|----------|--------|--------|
| **LangGraph** | Dedicated webhook + parser + 6 detectors | Production |
| **n8n** | Dedicated webhook + sync + discovery + 6 detectors | Production |
| **Dify** | Dedicated webhook + parser + 6 detectors | Production |
| **OpenClaw** | Dedicated webhook + parser + 6 detectors | Production |
| **Amazon Bedrock** | OTEL ingestion (auto-detected via `gen_ai.system`) | Production |
| **Google Vertex AI** | OTEL ingestion (auto-detected via `gcp.*` attributes) | Production |
| **CrewAI** | OTEL ingestion + SDK adapter | Production |
| **Microsoft Agent Framework** | OTEL ingestion (auto-detected via `microsoft.*`) | Production |
| **Claude Code / MCP** | MCP server + CLI + SDK adapter | Production |
| **Custom frameworks** | OTEL span ingestion + universal trace parser | Production |

### Additional Import Formats

| Format | Description |
|--------|-------------|
| Raw JSON | Generic agent trace format |
| Conversation | Multi-turn conversation format |
| MAST Benchmark | UC Berkeley MAST traces |
| Langfuse Export | Langfuse observation export |
| Phoenix/Arize | Arize Phoenix trace format |

## API Endpoints

### Detection
- `POST /api/v1/traces/ingest` — OTEL span ingestion
- `POST /api/v1/traces/{id}/analyze` — Run detectors on a trace
- `GET /api/v1/traces/{id}/orchestration-quality` — Orchestration quality score
- `GET /api/v1/traces/{id}/chain-analysis` — Multi-chain interaction analysis

### Healing
- `POST /api/v1/healing/trigger/{detection_id}` — Start self-healing
- `GET /api/v1/healing/{id}/progress` — Per-detector healing progress
- `GET /api/v1/healing/progress-summary` — Aggregate healing stats

### Platform Webhooks
- `POST /api/v1/n8n/webhook` — n8n execution ingestion
- `POST /api/v1/dify/webhook` — Dify workflow run ingestion
- `POST /api/v1/langgraph/webhook` — LangGraph graph run ingestion
- `POST /api/v1/openclaw/webhook` — OpenClaw session ingestion

## Self-Healing Pipeline

Detection → Fix Generation → Approval → Apply → Validate → Rollback

- 23 fix generators covering all production detectors
- Risk gating (DANGEROUS fixes blocked without approval)
- Auto-rollback on validation failure
- Fix learning loop (tracks effectiveness, ranks by historical success)
- Level 2 verification: detector re-run + LLM judge confirmation
