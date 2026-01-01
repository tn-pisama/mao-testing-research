# Common Detection Patterns

## Overview

This document contains reusable detection patterns for MAO algorithms. Each pattern is tier-appropriate and includes complexity analysis.

---

## Tier 1 Patterns (Hash-Based)

### Pattern 1.1: Exact Message Loop

Detects when an agent sends the exact same message multiple times.

```python
def detect_exact_loop(spans: list[Span], min_repeats: int = 3) -> Detection | None:
    """
    Time: O(n)
    Space: O(n)
    Latency: <1ms for 1000 spans
    """
    message_counts = {}

    for span in spans:
        msg = span.attributes.get('mao.agent.output', '')
        msg_hash = hashlib.md5(msg.encode()).hexdigest()[:16]

        message_counts[msg_hash] = message_counts.get(msg_hash, 0) + 1

        if message_counts[msg_hash] >= min_repeats:
            return Detection(
                type="exact_loop",
                tier=1,
                confidence=1.0,
                details={"hash": msg_hash, "count": message_counts[msg_hash]}
            )

    return None
```

### Pattern 1.2: Structural Fingerprint

Detects repeating structure even when content varies.

```python
def create_structural_fingerprint(message: str) -> str:
    """
    Creates structure fingerprint by replacing variable content.

    "Found 3 items: A, B, C" -> "Found N items: X, X, X"
    "Error at line 42" -> "Error at line N"
    """
    import re

    # Replace numbers
    result = re.sub(r'\d+', 'N', message)
    # Replace quoted strings
    result = re.sub(r'"[^"]*"', '"X"', result)
    result = re.sub(r"'[^']*'", "'X'", result)
    # Replace UUIDs
    result = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'UUID', result)

    return hashlib.md5(result.encode()).hexdigest()[:16]


def detect_structural_loop(spans: list[Span], min_repeats: int = 3) -> Detection | None:
    """Detect loops based on message structure."""
    fingerprint_counts = {}

    for span in spans:
        msg = span.attributes.get('mao.agent.output', '')
        fingerprint = create_structural_fingerprint(msg)

        fingerprint_counts[fingerprint] = fingerprint_counts.get(fingerprint, 0) + 1

        if fingerprint_counts[fingerprint] >= min_repeats:
            return Detection(
                type="structural_loop",
                tier=1,
                confidence=0.95,
                details={"fingerprint": fingerprint, "count": fingerprint_counts[fingerprint]}
            )

    return None
```

### Pattern 1.3: Tool Call Cycle

Detects when the same sequence of tool calls repeats.

```python
def detect_tool_cycle(spans: list[Span], cycle_length: int = 3) -> Detection | None:
    """
    Detect repeating tool call patterns.
    e.g., [search, read, search, read, search, read] = cycle of 2, repeated 3x
    """
    tool_sequence = []

    for span in spans:
        if 'tool' in span.name:
            tool_name = span.attributes.get('tool.name', span.name)
            tool_sequence.append(tool_name)

    # Check for cycles
    for length in range(1, len(tool_sequence) // 2 + 1):
        pattern = tuple(tool_sequence[:length])
        repetitions = 0

        for i in range(0, len(tool_sequence), length):
            if tuple(tool_sequence[i:i+length]) == pattern:
                repetitions += 1
            else:
                break

        if repetitions >= cycle_length:
            return Detection(
                type="tool_cycle",
                tier=1,
                confidence=0.98,
                details={"pattern": pattern, "repetitions": repetitions}
            )

    return None
```

---

## Tier 2 Patterns (State Delta)

### Pattern 2.1: No Progress Detection

Detects when state isn't changing despite agent activity.

```python
def detect_no_progress(spans: list[Span], threshold: int = 3) -> Detection | None:
    """
    Time: O(n)
    Space: O(1)
    Latency: <5ms for 1000 spans
    """
    no_progress_count = 0
    prev_state_hash = None

    for span in spans:
        state_after = span.attributes.get('mao.state.after')
        if state_after:
            current_hash = hashlib.md5(str(state_after).encode()).hexdigest()

            if current_hash == prev_state_hash:
                no_progress_count += 1
                if no_progress_count >= threshold:
                    return Detection(
                        type="no_progress",
                        tier=2,
                        confidence=0.9,
                        details={"stalled_spans": no_progress_count}
                    )
            else:
                no_progress_count = 0

            prev_state_hash = current_hash

    return None
```

### Pattern 2.2: State Regression

Detects when state goes backward (returns to previous value).

```python
def detect_state_regression(spans: list[Span]) -> Detection | None:
    """Detect when state returns to a previous value."""
    state_history = {}

    for i, span in enumerate(spans):
        state_after = span.attributes.get('mao.state.after')
        if state_after:
            state_hash = hashlib.md5(str(state_after).encode()).hexdigest()

            if state_hash in state_history:
                # State returned to previous value
                prev_index = state_history[state_hash]
                gap = i - prev_index

                if gap > 1:  # Not just consecutive (that's no_progress)
                    return Detection(
                        type="state_regression",
                        tier=2,
                        confidence=0.85,
                        details={
                            "regressed_to_span": prev_index,
                            "current_span": i,
                            "gap": gap
                        }
                    )

            state_history[state_hash] = i

    return None
```

### Pattern 2.3: Invalid State Transition

Detects transitions that violate expected state machine.

```python
def detect_invalid_transition(
    spans: list[Span],
    valid_transitions: dict[str, set[str]]
) -> Detection | None:
    """
    Detect transitions not in allowed set.

    Args:
        valid_transitions: {"state_a": {"state_b", "state_c"}, ...}
    """
    prev_state = None

    for span in spans:
        state_after = span.attributes.get('mao.state.after')
        if state_after and prev_state:
            # Extract key state field (customize per use case)
            prev_key = extract_state_key(prev_state)
            curr_key = extract_state_key(state_after)

            if prev_key in valid_transitions:
                if curr_key not in valid_transitions[prev_key]:
                    return Detection(
                        type="invalid_transition",
                        tier=2,
                        confidence=0.95,
                        details={
                            "from": prev_key,
                            "to": curr_key,
                            "allowed": list(valid_transitions[prev_key])
                        }
                    )

        prev_state = state_after

    return None
```

---

## Tier 3 Patterns (Embeddings)

### Pattern 3.1: Semantic Loop Detection

Detects messages that mean the same thing but are worded differently.

```python
def detect_semantic_loop(
    spans: list[Span],
    similarity_threshold: float = 0.95,
    min_cluster_size: int = 3
) -> Detection | None:
    """
    Time: O(n²) for similarity comparisons
    Space: O(n) for embeddings
    Latency: <50ms for 100 spans
    """
    spans_with_embeddings = [
        s for s in spans
        if s.embedding is not None
    ]

    # Build similarity graph
    clusters = []

    for span in spans_with_embeddings:
        added = False
        for cluster in clusters:
            # Compare with cluster centroid (first element)
            similarity = cosine_similarity(span.embedding, cluster[0].embedding)
            if similarity >= similarity_threshold:
                cluster.append(span)
                added = True
                break

        if not added:
            clusters.append([span])

    # Check for large clusters (semantic loops)
    for cluster in clusters:
        if len(cluster) >= min_cluster_size:
            return Detection(
                type="semantic_loop",
                tier=3,
                confidence=0.9,
                details={
                    "cluster_size": len(cluster),
                    "span_ids": [s.span_id for s in cluster]
                }
            )

    return None
```

### Pattern 3.2: Persona Drift Detection

Detects when agent behavior diverges from baseline persona.

```python
def detect_persona_drift(
    spans: list[Span],
    baseline_embedding: list[float],
    drift_threshold: float = 0.3
) -> Detection | None:
    """
    Detect when agent responses drift from expected persona.

    Args:
        baseline_embedding: Embedding of expected persona behavior
        drift_threshold: Maximum allowed drift (0 = identical, 1 = opposite)
    """
    for span in spans:
        if span.embedding is None:
            continue

        # Calculate drift from baseline
        similarity = cosine_similarity(span.embedding, baseline_embedding)
        drift = 1 - similarity

        if drift > drift_threshold:
            return Detection(
                type="persona_drift",
                tier=3,
                confidence=0.8 + (drift - drift_threshold) * 0.5,
                details={
                    "span_id": span.span_id,
                    "drift_score": drift,
                    "threshold": drift_threshold
                }
            )

    return None
```

### Pattern 3.3: Topic Coherence Check

Detects when conversation goes off-topic.

```python
def detect_topic_drift(
    spans: list[Span],
    topic_embeddings: list[list[float]],
    coherence_threshold: float = 0.5
) -> Detection | None:
    """
    Detect spans that don't relate to expected topics.

    Args:
        topic_embeddings: Embeddings representing valid topics
    """
    for span in spans:
        if span.embedding is None:
            continue

        # Find max similarity to any valid topic
        max_similarity = max(
            cosine_similarity(span.embedding, topic)
            for topic in topic_embeddings
        )

        if max_similarity < coherence_threshold:
            return Detection(
                type="topic_drift",
                tier=3,
                confidence=0.7,
                details={
                    "span_id": span.span_id,
                    "max_topic_similarity": max_similarity
                }
            )

    return None
```

---

## Utility Functions

```python
import numpy as np


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_np = np.array(a)
    b_np = np.array(b)
    return np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np))


def extract_state_key(state: dict) -> str:
    """Extract the key field from state for comparison."""
    # Customize based on your state structure
    return state.get('status', str(state))


def compute_delta(before: dict, after: dict) -> dict:
    """Compute the difference between two state dicts."""
    delta = {}

    all_keys = set(before.keys()) | set(after.keys())

    for key in all_keys:
        before_val = before.get(key)
        after_val = after.get(key)

        if before_val != after_val:
            delta[key] = {"before": before_val, "after": after_val}

    return delta
```

---

## Combining Patterns

For robust detection, combine multiple patterns:

```python
class CompositeDetector:
    """Run multiple detectors with early exit on high-confidence detection."""

    def __init__(self, detectors: list):
        # Sort by tier (lowest first)
        self.detectors = sorted(detectors, key=lambda d: d.tier)

    def detect(self, trace: Trace) -> list[Detection]:
        detections = []

        for detector in self.detectors:
            result = detector.detect(trace)
            if result:
                detections.extend(result if isinstance(result, list) else [result])

                # Early exit if high-confidence detection at low tier
                if any(d.confidence >= 0.95 and d.tier <= 2 for d in detections):
                    break

        return detections
```
