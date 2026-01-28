---
name: detection-algorithm-designer
description: |
  Designs and implements new detection algorithms for PISAMA failure modes.
  Use when adding loop detection, state corruption, persona drift, or coordination failure detection.
  Ensures algorithms follow tiered architecture, are cost-efficient, and have defined accuracy targets.
  Provides scaffolding code, test cases, and integration guidance.
allowed-tools: Read, Grep, Glob, Write
---

# Detection Algorithm Designer Skill

You are designing a new detection algorithm for the PISAMA platform. Your goal is to create algorithms that are accurate, cost-efficient, and follow the tiered detection architecture.

## Design Process

### Step 1: Define the Failure Mode

Before writing any code, clearly define:

```markdown
## Failure Mode Definition

**Name**: [e.g., "Agent Hallucination Loop"]
**Category**: loop | state_corruption | persona_drift | coordination | custom
**Description**: [What does this failure look like?]

**Examples**:
1. [Concrete example of this failure in a trace]
2. [Another example]

**Non-Examples** (things that look similar but aren't this failure):
1. [What should NOT trigger detection]
2. [Edge case that's actually valid behavior]

**Severity**: low | medium | high | critical
**Frequency**: How often does this occur in production traces?
```

### Step 2: Choose Starting Tier

**ALWAYS start at the lowest tier that could possibly work:**

| Consider Tier 1 (Hash) If... |
|------------------------------|
| Failure has exact text patterns |
| Failure involves repeated messages |
| Failure can be identified by message structure |

| Consider Tier 2 (State Delta) If... |
|-------------------------------------|
| Failure involves state not changing |
| Failure involves invalid state transitions |
| Failure shows in sequence of state snapshots |

| Consider Tier 3 (Embeddings) If... |
|------------------------------------|
| Failure is semantic (meaning-based) |
| Exact text differs but meaning repeats |
| Need similarity comparison |

| Consider Tier 4+ Only If... |
|-----------------------------|
| Lower tiers demonstrably insufficient |
| Failure requires contextual reasoning |
| Ambiguous cases need judgment |

### Step 3: Algorithm Template

Use this template for your detection algorithm:

```python
"""
Detection Algorithm: {name}
Tier: {1-5}
Target Accuracy: Precision >{x}%, Recall >{y}%
False Positive Budget: <{z}%
"""

from dataclasses import dataclass
from typing import Protocol

from mao_testing.core.types import Detection, Span, Trace


@dataclass
class {Name}Config:
    """Configuration for {name} detector."""

    # Thresholds
    threshold: float = 0.9  # Main detection threshold
    min_occurrences: int = 3  # Minimum pattern occurrences

    # Cost controls
    max_spans_to_analyze: int = 100  # Limit computation
    timeout_ms: int = 50  # Max execution time

    # Accuracy tuning
    false_positive_budget: float = 0.05  # 5% max FP rate


class {Name}Detector:
    """
    Detects {failure_description}.

    Tier: {tier}
    Cost: ${cost} per detection
    Latency: <{latency}ms

    Algorithm:
    1. {step1}
    2. {step2}
    3. {step3}

    Escalation Criteria:
    - Escalate to Tier {n+1} when: {criteria}
    """

    def __init__(self, config: {Name}Config | None = None):
        self.config = config or {Name}Config()
        self.tier = {tier}

    def detect(self, trace: Trace) -> list[Detection]:
        """
        Run detection algorithm.

        Args:
            trace: The trace to analyze

        Returns:
            List of detections found (empty if none)
        """
        detections = []

        # Pre-filter spans to reduce computation
        relevant_spans = self._filter_spans(trace.spans)

        if len(relevant_spans) > self.config.max_spans_to_analyze:
            relevant_spans = relevant_spans[:self.config.max_spans_to_analyze]

        # Main detection logic
        for detection_candidate in self._analyze(relevant_spans):
            if detection_candidate.confidence >= self.config.threshold:
                detections.append(detection_candidate)

        return detections

    def _filter_spans(self, spans: list[Span]) -> list[Span]:
        """Filter to relevant spans for this detector."""
        return [
            span for span in spans
            if self._is_relevant(span)
        ]

    def _is_relevant(self, span: Span) -> bool:
        """Check if span is relevant for this detection."""
        # Customize based on detection type
        return span.attributes.get('mao.agent.name') is not None

    def _analyze(self, spans: list[Span]) -> list[Detection]:
        """Core analysis logic."""
        # TODO: Implement detection logic
        raise NotImplementedError

    def should_escalate(self, detection: Detection) -> bool:
        """Determine if detection should escalate to next tier."""
        # Escalate if confidence is in ambiguous range
        if 0.5 <= detection.confidence < self.config.threshold:
            return True

        # Escalate if critical severity but low confidence
        if detection.severity == "critical" and detection.confidence < 0.9:
            return True

        return False
```

### Step 4: Test Specification

Every detector MUST have tests:

```python
"""
Test Specification for {name} Detector
"""

import pytest
from mao_testing.core.types import Span, Trace

from .detector import {Name}Detector


class TestPositiveCases:
    """Cases where detection SHOULD trigger."""

    def test_basic_detection(self):
        """Most common failure pattern."""
        trace = create_trace_with_failure()
        detector = {Name}Detector()

        detections = detector.detect(trace)

        assert len(detections) == 1
        assert detections[0].type == "{failure_type}"
        assert detections[0].confidence >= 0.9

    def test_edge_case_1(self):
        """Subtle variant that should still detect."""
        pass

    def test_edge_case_2(self):
        """Another variant."""
        pass


class TestNegativeCases:
    """Cases where detection should NOT trigger."""

    def test_normal_operation(self):
        """Valid trace with no failures."""
        trace = create_valid_trace()
        detector = {Name}Detector()

        detections = detector.detect(trace)

        assert len(detections) == 0

    def test_similar_but_valid(self):
        """Pattern that looks similar but is valid."""
        pass

    def test_edge_case_no_trigger(self):
        """Edge case that shouldn't trigger."""
        pass


class TestPerformance:
    """Performance requirements."""

    def test_latency_under_budget(self):
        """Must complete within latency budget."""
        trace = create_large_trace(spans=1000)
        detector = {Name}Detector()

        import time
        start = time.monotonic()
        detector.detect(trace)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 50  # Tier-appropriate budget

    def test_handles_large_traces(self):
        """Gracefully handles traces above max_spans."""
        trace = create_large_trace(spans=10000)
        detector = {Name}Detector()

        # Should not raise, should limit internally
        detections = detector.detect(trace)
        assert isinstance(detections, list)


class TestEscalation:
    """Escalation logic tests."""

    def test_escalates_low_confidence(self):
        """Low confidence should escalate."""
        pass

    def test_no_escalate_high_confidence(self):
        """High confidence should not escalate."""
        pass
```

### Step 5: Integration Checklist

Before submitting your detector:

- [ ] Tier placement justified (tried lower tiers first)
- [ ] Config has sensible defaults
- [ ] Cost tracked in Detection output
- [ ] Latency within tier budget
- [ ] Escalation criteria defined
- [ ] No framework-specific imports
- [ ] Tests cover positive, negative, and performance cases
- [ ] Docstrings complete
- [ ] Type hints complete

## Common Patterns

### Pattern: Sliding Window Analysis

For detecting patterns over sequential spans:

```python
def _analyze_with_window(self, spans: list[Span], window_size: int = 5):
    """Analyze using sliding window."""
    for i in range(len(spans) - window_size + 1):
        window = spans[i:i + window_size]
        if self._window_matches_pattern(window):
            yield self._create_detection(window)
```

### Pattern: State Transition Graph

For detecting invalid state transitions:

```python
def _build_transition_graph(self, spans: list[Span]) -> dict:
    """Build graph of state transitions."""
    transitions = {}
    prev_state = None

    for span in spans:
        current_state = span.attributes.get('mao.state.after')
        if prev_state and current_state:
            key = (hash(str(prev_state)), hash(str(current_state)))
            transitions[key] = transitions.get(key, 0) + 1
        prev_state = current_state

    return transitions
```

### Pattern: Similarity Clustering

For Tier 3 semantic detection:

```python
def _cluster_by_similarity(self, spans: list[Span], threshold: float = 0.95):
    """Group spans by semantic similarity."""
    clusters = []

    for span in spans:
        if not span.embedding:
            continue

        added_to_cluster = False
        for cluster in clusters:
            if self._similarity(span.embedding, cluster[0].embedding) > threshold:
                cluster.append(span)
                added_to_cluster = True
                break

        if not added_to_cluster:
            clusters.append([span])

    return clusters
```

## Resources

For detailed specifications, I can load:
- `resources/detection-patterns.md` - Common detection patterns with code
- `resources/accuracy-benchmarks.md` - Expected accuracy by failure type
- `resources/tier-migration-guide.md` - How to move algorithms between tiers

### External References

**Claude Agent SDK - Hooks** - https://github.com/anthropics/claude-agent-sdk-python
- Pre/post-tool use hook patterns for deterministic processing
- Reference for designing detection points at span boundaries
- Error handling patterns and comprehensive error taxonomy
- Session management for multi-turn agent context

**Claude Security Review** - https://github.com/anthropics/claude-code-security-review
- AI-powered security scanning patterns
- Injection detection algorithms and prompt injection patterns
- Automated review workflows applicable to self-healing approval flows
- Reference for improving PISAMA's injection detector (backend/app/detection/injection.py)
