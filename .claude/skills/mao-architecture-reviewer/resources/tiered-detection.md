# Tiered Detection Implementation Guide

## Overview

MAO uses a 5-tier detection system optimized for cost and accuracy. Always start at Tier 1 and only escalate when necessary.

## Tier Definitions

### Tier 1: Structural Hash ($0, <1ms)

**Method**: Exact pattern matching using hashes

**Use Cases**:
- Exact message repetition (loop detection)
- Duplicate span detection
- Known bad pattern matching

**Implementation**:
```python
def tier1_loop_detect(spans: list[Span]) -> Detection | None:
    """Detect exact loops via content hashing."""
    seen_hashes = {}
    for span in spans:
        content_hash = hashlib.md5(
            f"{span.name}:{span.attributes.get('mao.agent.input', '')}".encode()
        ).hexdigest()[:16]

        if content_hash in seen_hashes:
            if seen_hashes[content_hash] >= 2:  # 3+ occurrences
                return Detection(
                    type="loop",
                    tier=1,
                    confidence=1.0,
                    details={"hash": content_hash, "count": seen_hashes[content_hash] + 1}
                )
        seen_hashes[content_hash] = seen_hashes.get(content_hash, 0) + 1

    return None
```

**Escalate When**: No exact match but suspicious patterns exist.

---

### Tier 2: State Delta Analysis ($0, <5ms)

**Method**: Compare state changes between spans

**Use Cases**:
- State not progressing (semantic loop)
- State corruption (invalid transitions)
- Missing required fields

**Implementation**:
```python
def tier2_state_analysis(spans: list[Span]) -> Detection | None:
    """Detect issues via state delta analysis."""
    prev_state = None
    no_progress_count = 0

    for span in spans:
        current_state = span.attributes.get('mao.state.after')
        if current_state and prev_state:
            delta = compute_delta(prev_state, current_state)

            if delta == {}:  # No state change
                no_progress_count += 1
                if no_progress_count >= 3:
                    return Detection(
                        type="loop",
                        tier=2,
                        confidence=0.9,
                        details={"no_progress_spans": no_progress_count}
                    )
            else:
                no_progress_count = 0
                # Check for corruption
                if not validate_state_transition(prev_state, current_state):
                    return Detection(
                        type="state_corruption",
                        tier=2,
                        confidence=0.85,
                        details={"invalid_transition": delta}
                    )

        prev_state = current_state

    return None
```

**Escalate When**: State changes exist but semantic meaning unclear.

---

### Tier 3: Local Embeddings ($0, <50ms)

**Method**: Semantic similarity using local embedding model

**Use Cases**:
- Semantically similar but textually different messages
- Persona drift detection
- Near-duplicate content

**Implementation**:
```python
def tier3_embedding_analysis(spans: list[Span], threshold: float = 0.95) -> Detection | None:
    """Detect semantic patterns using embeddings."""
    embeddings = []

    for span in spans:
        # Use pre-computed embeddings from database
        if span.embedding:
            embeddings.append((span, span.embedding))

    # Check for semantic loops
    for i, (span_a, emb_a) in enumerate(embeddings):
        for span_b, emb_b in embeddings[i+1:]:
            similarity = cosine_similarity(emb_a, emb_b)
            if similarity > threshold:
                return Detection(
                    type="loop",
                    tier=3,
                    confidence=similarity,
                    details={
                        "span_a": span_a.span_id,
                        "span_b": span_b.span_id,
                        "similarity": similarity
                    }
                )

    # Check for persona drift
    baseline_persona_embedding = get_baseline_persona(spans[0])
    for span in spans:
        current_embedding = get_persona_embedding(span)
        drift = 1 - cosine_similarity(baseline_persona_embedding, current_embedding)
        if drift > 0.3:  # 30% drift threshold
            return Detection(
                type="persona_drift",
                tier=3,
                confidence=0.8,
                details={"drift_score": drift, "span_id": span.span_id}
            )

    return None
```

**Escalate When**: Similarity scores in ambiguous range (0.7-0.95).

---

### Tier 4: LLM Judge ($0.50, <2s)

**Method**: LLM evaluates ambiguous cases

**Use Cases**:
- Complex semantic analysis
- Context-dependent failures
- Novel failure modes

**Implementation**:
```python
async def tier4_llm_judge(spans: list[Span], context: str) -> Detection | None:
    """Use LLM to judge ambiguous cases."""

    prompt = f"""Analyze this agent trace for failures:

Trace Context: {context}

Spans:
{format_spans_for_llm(spans)}

Check for:
1. Loops (agents repeating without progress)
2. State corruption (invalid state transitions)
3. Persona drift (agent behaving out of character)
4. Coordination failures (miscommunication between agents)

Respond with JSON:
{{
    "has_failure": true/false,
    "failure_type": "loop" | "state_corruption" | "persona_drift" | "coordination" | null,
    "confidence": 0.0-1.0,
    "explanation": "..."
}}
"""

    response = await llm.complete(prompt, max_tokens=500)
    result = json.loads(response)

    if result["has_failure"]:
        return Detection(
            type=result["failure_type"],
            tier=4,
            confidence=result["confidence"],
            details={"explanation": result["explanation"]},
            cost_usd=0.50
        )

    return None
```

**Escalate When**: LLM confidence < 0.7 or detection is critical severity.

---

### Tier 5: Human Review ($50, <24h)

**Method**: Human expert reviews flagged traces

**Use Cases**:
- Critical business impact
- Novel/unknown failure patterns
- LLM uncertainty
- Training data collection

**Implementation**:
```python
async def tier5_human_review(detection: Detection, trace: Trace) -> Detection:
    """Queue for human review."""

    review_ticket = await create_review_ticket(
        trace_id=trace.id,
        detection=detection,
        priority="high" if detection.severity == "critical" else "normal",
        context=prepare_review_context(trace)
    )

    # Update detection status
    detection.status = "pending_review"
    detection.review_ticket_id = review_ticket.id
    detection.tier = 5
    detection.cost_usd = 50.0  # Human review cost

    return detection
```

---

## Escalation Decision Tree

```
Start: New trace received
         │
         ▼
    ┌─────────────┐
    │   Tier 1    │──── Detection found? ──── Yes ──► Return detection
    │ Struct Hash │                                   (confidence: 1.0)
    └─────────────┘
         │ No
         ▼
    ┌─────────────┐
    │   Tier 2    │──── Detection found? ──── Yes ──► Return detection
    │ State Delta │                                   (confidence: 0.85-0.95)
    └─────────────┘
         │ No
         ▼
    ┌─────────────┐
    │   Tier 3    │──── Detection found? ──── Yes ──┬─► confidence > 0.9?
    │ Embeddings  │                                  │   Yes ──► Return detection
    └─────────────┘                                  │   No ──► Tier 4
         │ No
         ▼
    ┌─────────────┐
    │   Tier 4    │──── Detection found? ──── Yes ──┬─► confidence > 0.7?
    │  LLM Judge  │                                  │   Yes ──► Return detection
    └─────────────┘                                  │   No ──► Tier 5
         │ No                                        │
         ▼                                           │
    Return: No detection                             │
                                                     ▼
                                              ┌─────────────┐
                                              │   Tier 5    │
                                              │Human Review │
                                              └─────────────┘
```

## Cost Budget Guidelines

| Org Tier | Monthly Budget | Tier 4 Limit | Tier 5 Limit |
|----------|----------------|--------------|--------------|
| Free | $0 | 0 | 0 |
| Starter | $50 | 100 calls | 1 review |
| Pro | $500 | 1000 calls | 10 reviews |
| Enterprise | Custom | Custom | Custom |

## Metrics to Track

For each detection tier:
- Invocation count
- Average latency
- Cost incurred
- True positive rate
- False positive rate
- Escalation rate

Target: 95% of detections at Tier 1-2, <1% at Tier 4-5.
