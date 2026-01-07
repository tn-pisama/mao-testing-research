# MAST Benchmark Research Synthesis

## Executive Summary

**Current State**: 75.8% overall F1 on 11 MAST traces (conversation format)
**Target**: 90%+ F1 with <10% FPR

This document synthesizes research from academic papers, industry platforms, and empirical testing to recommend improvements for MAST benchmark detection.

---

## Research Sources Analyzed

| Source | Key Insight | Relevance |
|--------|-------------|-----------|
| MAST Paper (UC Berkeley 2024) | LLM annotator with o1 achieves 94% accuracy, 0.77 Cohen's Kappa | Core benchmark methodology |
| SentinelAgent (2024) | Graph-based anomaly detection with node/edge/attack path analysis | Multi-agent coordination failures |
| TRAIL Framework (2024) | LLMs struggle with trace debugging (best: 18.3% joint accuracy) | Sets realistic expectations |
| TRACE Contrastive Learning | 21.3% F1 improvement over traditional methods | Embedding-based detection |
| Industry Platforms | LangSmith, Langfuse, Arize - all moving toward LLM-as-judge | Market validation |

---

## Current Detection Performance

### Per-Mode Breakdown (from latest eval)

| Mode | F1 | Precision | Recall | FPR | Status |
|------|-----|-----------|--------|-----|--------|
| **F5** | 1.0 | 1.0 | 1.0 | 0% | ✅ Perfect |
| **F6** | 1.0 | 1.0 | 1.0 | 0% | ✅ Perfect |
| **F7** | 1.0 | 1.0 | 1.0 | 0% | ✅ Perfect |
| **F11** | 1.0 | 1.0 | 1.0 | 0% | ✅ Perfect |
| **F14** | 1.0 | 1.0 | 1.0 | 0% | ✅ Perfect |
| **F3** | 0.67 | 0.5 | 1.0 | 10% | ⚠️ FP issue |
| **F13** | 0.67 | 0.5 | 1.0 | 10% | ⚠️ FP issue |
| **F8** | 0.5 | 0.33 | 1.0 | 20% | ⚠️ High FPR |
| **F12** | 0.5 | 0.33 | 1.0 | 20% | ⚠️ High FPR |
| **F1** | 0.25 | 0.14 | 1.0 | 60% | ❌ Critical FPR |

### Problem Modes Analysis

**F1 (Specification Mismatch)**: 60% FPR, 14% precision
- Issue: Overly sensitive requirement coverage detection
- Root cause: Text matching struggles with reformulated requirements
- MAST approach: Uses semantic understanding of task completion

**F8 (Step Repetition)**: 20% FPR, 33% precision
- Issue: False positives on legitimate retries
- Root cause: Threshold-based detection can't distinguish intent
- MAST says: 15.7% of all failures are step repetition

**F12 (Resource Limit)**: 20% FPR, 33% precision
- Issue: Token count estimation varies by framework
- Root cause: No ground truth for context window limits

---

## Key Research Findings

### 1. MAST Paper Methodology (94% Accuracy)

The MAST paper achieves 94% inter-annotator agreement using:

```
LLM Annotator Configuration:
- Model: OpenAI o1 (reasoning model)
- Prompting: Few-shot with 2-3 examples per failure mode
- Context: Full trace + failure mode definitions
- Output: Binary classification with confidence + reasoning
```

**Critical Insight**: MAST doesn't use pattern matching. It uses semantic understanding of:
1. What the task required
2. What the agent actually did
3. Whether the outcome meets the specification

**Implication for PISAMA**: Our current detectors are pattern-based (loops, thresholds). MAST requires outcome-based evaluation.

### 2. TRAIL Framework Reality Check

TRAIL (Trace Reasoning for Agentic Issue Localization) tested LLMs on 148 annotated traces:

| Model | Joint Accuracy | Error Identification | Root Cause |
|-------|----------------|---------------------|------------|
| Gemini 2.5-Pro | 18.3% | 35.2% | 41.1% |
| Claude 3.5 | 15.4% | 32.1% | 38.7% |
| GPT-4o | 11.0% | 28.6% | 34.2% |

**Key Takeaway**: Even frontier LLMs struggle with trace debugging. The 94% MAST accuracy is for failure MODE classification, not root cause analysis.

### 3. SentinelAgent Graph-Based Detection

SentinelAgent uses graph representation for multi-agent analysis:

```
Graph Structure:
- Nodes: Agents, tools, states
- Edges: Communications, tool calls, state transitions
- Anomaly Detection:
  1. Node-level (individual agent failures)
  2. Edge-level (communication failures)
  3. Path-level (workflow failures)
```

**Applicable MAST Modes**:
- F3 (Agent Coordination): Edge-level anomalies
- F9 (Usurpation): Path deviation from expected workflow
- F13 (Stalling): Node timeout patterns

### 4. Contrastive Learning for Traces

TRACE framework uses contrastive learning to create trace embeddings:

```
Approach:
1. Encode normal traces as positive samples
2. Encode failure traces as negative samples
3. Learn embedding space where failures cluster
4. Detection: Distance from normal cluster centroid

Results: 21.3% F1 improvement over threshold-based methods
```

**Applicable to**: F1, F3, F8 where semantic similarity matters more than exact patterns.

---

## Recommended Improvements

### Priority 1: Hybrid LLM-Judge for High-FPR Modes (F1, F8, F12)

**Problem**: Pattern-based detection has 20-60% FPR on semantic failure modes.

**Solution**: Use LLM verification for detections with confidence 0.5-0.8.

```python
class HybridDetector:
    """Two-stage detection: fast pattern + LLM verification."""

    def detect(self, trace: ConversationTrace) -> list[Detection]:
        # Stage 1: Fast pattern detection
        candidates = self.pattern_detector.detect(trace)

        # Stage 2: LLM verification for ambiguous cases
        verified = []
        for candidate in candidates:
            if candidate.confidence < 0.8:
                # Send to LLM judge
                judgment = self.llm_judge.verify(
                    trace=trace,
                    failure_mode=candidate.type,
                    evidence=candidate.evidence
                )
                if judgment.is_failure:
                    verified.append(candidate)
            else:
                # High confidence: trust pattern detector
                verified.append(candidate)

        return verified
```

**LLM Judge Prompt (from MAST paper):**
```
You are evaluating whether an agent trace exhibits failure mode {mode}.

Failure Mode Definition:
{definition}

Example of this failure:
{few_shot_example}

Trace to evaluate:
{trace_content}

Does this trace exhibit {mode}?
Respond with: YES, NO, or UNCERTAIN
Reasoning: [your analysis]
```

**Cost Estimate**: ~$0.02/trace at current Claude 3.5 Sonnet pricing

### Priority 2: Framework-Aware Task Extraction

**Problem**: Different frameworks store tasks differently:
- LangGraph: First HumanMessage
- ChatDev: System prompt with "develop a program..."
- AG2: Initial user message or config
- Magentic: Function call parameters

**Solution**: Framework-specific task extractors:

```python
class TaskExtractor(Protocol):
    def extract_task(self, trace: ConversationTrace) -> str:
        """Extract the original task/goal from trace."""
        ...

class ChatDevTaskExtractor(TaskExtractor):
    def extract_task(self, trace: ConversationTrace) -> str:
        # ChatDev: Task in system prompt
        for turn in trace.turns:
            if turn.role == "system" and "develop" in turn.content.lower():
                return turn.content
        return ""

class AG2TaskExtractor(TaskExtractor):
    def extract_task(self, trace: ConversationTrace) -> str:
        # AG2: Task in first user message or initial_message config
        for turn in trace.turns:
            if turn.role == "user":
                return turn.content
        # Fallback: check config
        if trace.metadata.get("initial_message"):
            return trace.metadata["initial_message"]
        return ""
```

### Priority 3: Graph-Based Coordination Detection (F3, F9)

**Problem**: F3 (Coordination Failure) needs understanding of multi-agent workflows.

**Solution**: Build agent interaction graph and detect anomalies:

```python
class AgentInteractionGraph:
    """Graph representation of agent-to-agent communication."""

    def __init__(self, trace: ConversationTrace):
        self.nodes = set()  # Agent names
        self.edges = []  # (from_agent, to_agent, message)
        self._build_from_trace(trace)

    def detect_coordination_failures(self) -> list[Detection]:
        failures = []

        # 1. Detect message loops between agents
        for cycle in self._find_cycles():
            if len(cycle) > 3:
                failures.append(Detection(
                    type="F3",
                    evidence=f"Communication cycle: {' -> '.join(cycle)}",
                    confidence=0.85
                ))

        # 2. Detect handoff failures (message sent, no response)
        for edge in self.edges:
            if not self._has_response(edge):
                failures.append(Detection(
                    type="F3",
                    evidence=f"{edge.from_agent} sent to {edge.to_agent} with no response",
                    confidence=0.75
                ))

        return failures
```

### Priority 4: Contrastive Trace Embeddings for F1

**Problem**: F1 (Specification Mismatch) has 60% FPR because text matching fails on paraphrased requirements.

**Solution**: Learn embeddings that capture task completion semantics:

```python
class TaskCompletionEmbedder:
    """Embed (task, trace) pairs for completion detection."""

    def __init__(self, model: str = "text-embedding-3-large"):
        self.encoder = OpenAIEmbeddings(model=model)
        self.completion_threshold = 0.82  # Tuned from training data

    def is_task_complete(self, task: str, trace_summary: str) -> tuple[bool, float]:
        """Check if trace demonstrates task completion."""
        task_emb = self.encoder.embed(task)
        trace_emb = self.encoder.embed(trace_summary)

        # Cosine similarity as completion score
        similarity = cosine_similarity(task_emb, trace_emb)

        return similarity >= self.completion_threshold, similarity
```

---

## Implementation Roadmap

### Phase 1: Quick Wins (1-2 days)
1. ✅ Fix F1 threshold bug (done)
2. Add framework detection to trace metadata
3. Implement framework-specific task extractors
4. Tune thresholds for remaining high-FPR modes

### Phase 2: LLM Judge Integration (3-5 days)
1. Create LLM judge prompts for F1, F8, F12
2. Implement hybrid detection pipeline
3. Add confidence-based escalation
4. Benchmark cost vs accuracy tradeoff

### Phase 3: Graph-Based Detection (5-7 days)
1. Build AgentInteractionGraph from traces
2. Implement cycle detection for F3
3. Add handoff failure detection
4. Test on MAST multi-agent traces

### Phase 4: Embedding-Based Detection (7-10 days)
1. Generate task-completion embeddings
2. Build training set from MAST annotations
3. Train contrastive model
4. Replace pattern-based F1 detector

---

## Limitations and Gaps

### Fundamental Limitations

1. **MAST is outcome-based, traces are process-based**
   - MAST annotates whether task SUCCEEDED
   - Traces show HOW agent worked
   - Gap: Good process with bad outcome vs bad process with good outcome

2. **Multi-agent traces have metadata, not dialogue**
   - ChatDev traces: Agent config objects, not actual messages
   - AG2 traces: Function calls, not reasoning
   - Gap: Can't evaluate agent reasoning quality

3. **Ground truth ambiguity**
   - Some MAST annotations are subjective
   - F8 (Step Repetition) vs legitimate retry
   - F1 (Specification Mismatch) vs partial completion

### Detection Gaps

| MAST Mode | Current Detector | Gap |
|-----------|------------------|-----|
| F2 | None | Task decomposition quality - needs planning analysis |
| F4 | None | Tool selection quality - needs capability mapping |
| F9 | Basic | Usurpation - needs role boundary detection |
| F10 | None | Inform failure - needs communication pattern analysis |

### Data Gaps

1. **Small evaluation set**: Only 11 conversation-format traces
2. **Framework bias**: Mostly AG2 and ChatDev in current eval
3. **No failure examples**: Need more ground-truth failure traces for tuning

---

## Conclusions

1. **Current 75.8% F1 is good** for pattern-based detection
2. **LLM judge is necessary** to reach 90%+ on semantic modes (F1, F8)
3. **Graph-based detection** is promising for coordination failures (F3, F9)
4. **Framework-aware extraction** is critical for multi-agent traces
5. **Contrastive embeddings** could replace threshold-based detection

**Recommended Next Step**: Implement hybrid LLM-judge for F1, F8, F12 to reduce FPR from 20-60% to <10%.
