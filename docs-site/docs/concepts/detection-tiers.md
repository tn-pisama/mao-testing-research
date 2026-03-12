# Detection Tiers

PISAMA uses a **tiered escalation system** to balance detection cost and accuracy. Each trace is analyzed starting from the cheapest tier, escalating only when lower tiers are inconclusive.

## Tier Overview

| Tier | Method | Cost per Trace | When Used |
|---|---|---|---|
| Tier 1 | Hash-based detection | < $0.001 | Always -- fastest, cheapest |
| Tier 2 | State delta analysis | $0.005 - $0.01 | When Tier 1 confidence is low |
| Tier 3 | Embedding / ML detection | $0.01 - $0.02 | When Tier 2 is inconclusive |
| Tier 4 | LLM-as-Judge | $0.05 - $0.10 | Gray zone cases requiring reasoning |
| Tier 5 | Human review | Variable | When all automated tiers are uncertain |

**Target cost: $0.05 per trace average.** Most traces resolve at Tier 1-2.

## Tier Details

### Tier 1: Rule-Based Detection

The fastest and cheapest tier. Uses deterministic algorithms with zero LLM cost.

- **Hash collision**: SHA256 hash of normalized state delta -- if two states hash identically, they contain the same data
- **Pattern matching**: Regex patterns for injection detection (60+ patterns across 6 attack categories)
- **Structural matching**: Compares agent IDs and state delta keys between consecutive states
- **Threshold checks**: Token counts, cost budgets, context window utilization

Typical confidence when matched: **0.80 - 0.96**

### Tier 2: State Delta Analysis

Analyzes differences between consecutive states to detect anomalies.

- **Cross-field consistency**: Validates relationships (start_date < end_date, min < max)
- **Domain constraint validation**: Age 0-150, price >= 0, valid email/URL formats
- **Velocity analysis**: Detects abnormal rate of state changes
- **Type drift detection**: Catches when a numeric field suddenly contains a string
- **Null/disappearance detection**: Flags when 3+ fields vanish simultaneously

Typical confidence when matched: **0.70 - 0.90**

### Tier 3: Embedding / ML Detection

Uses embedding models to detect semantic patterns invisible to rules.

- **Semantic similarity**: Embedding distance between task description and output (derailment, context neglect)
- **Semantic clustering**: KMeans clustering on state embeddings to detect loop patterns
- **Role embedding comparison**: Compares agent behavior vectors against role definitions (persona drift)
- **Grounding score**: Measures output alignment against source documents

Models used:

- E5-large-instruct (1024 dimensions)
- nomic-embed-text-v1.5 (768 dimensions)
- Ensemble mode for higher accuracy

Typical confidence when matched: **0.65 - 0.85**

### Tier 4: LLM-as-Judge

When Tier 3 is still uncertain (confidence in the gray zone 0.35-0.65), the LLM Judge provides reasoning-based verification.

**Model routing by failure mode:**

| Judge Tier | Failure Modes | Model | Cost per 1M tokens |
|---|---|---|---|
| Tier 1 (low-stakes) | F3, F7, F11, F12 | Gemini Flash Lite | $0.10 / $0.40 |
| Tier 2 (default) | F1, F2, F4, F5, F10, F13 | Claude Sonnet | $3 / $15 |
| Tier 3 (high-stakes) | F6, F8, F9, F14 | Claude Sonnet (thinking) | Extended thinking |

**Features:**

- **RAG retrieval**: Few-shot examples from pgvector (similarity >= 0.65)
- **Caching**: SHA256-based cache with LRU eviction (max 1000 entries)
- **Cost tracking**: Per-tier and per-provider spend recorded via `JudgeCostTracker`
- **No-downgrade set**: Some detectors (coordination, grounding) have high precision from rules -- the LLM judge can only boost confidence, never reduce it

### Tier 5: Human Review

For critical decisions where all automated tiers are uncertain. Involves routing the detection to a human reviewer through the dashboard or webhook notification.

## Gray Zone Handling

When a detector's confidence falls in the range [0.35, 0.65], the result is classified as "uncertain" and escalates to the next tier. This prevents the system from committing to low-confidence decisions.

```
Confidence < 0.35  →  Classified as negative (no failure)
Confidence 0.35-0.65  →  Gray zone → escalate to next tier
Confidence > 0.65  →  Classified as positive (failure detected)
```

## Tier Configuration

The tiered system is configured per detector type:

```python
@dataclass
class TierConfig:
    rule_confidence_threshold: float = 0.7
    cheap_ai_confidence_threshold: float = 0.8
    expensive_ai_confidence_threshold: float = 0.85
    gray_zone_lower: float = 0.35
    gray_zone_upper: float = 0.65
    enable_cheap_ai: bool = True
    enable_expensive_ai: bool = True
    enable_human_escalation: bool = True
    track_costs: bool = True
```

## Feature Availability by Tier

| Feature | Free | Startup | Growth | Enterprise |
|---|---|---|---|---|
| Loop detection | Yes | Yes | Yes | Yes |
| State corruption | Yes | Yes | Yes | Yes |
| Persona drift | Yes | Yes | Yes | Yes |
| Coordination analysis | Yes | Yes | Yes | Yes |
| Hallucination | Yes | Yes | Yes | Yes |
| Injection detection | Yes | Yes | Yes | Yes |
| Context overflow | Yes | Yes | Yes | Yes |
| Task derailment | Yes | Yes | Yes | Yes |
| ML-based detection | -- | -- | -- | Yes |
| Tiered LLM-judge | -- | -- | -- | Yes |
| Turn-aware detection | -- | -- | -- | Yes |
| Quality gate | -- | -- | -- | Yes |

Enterprise features require the `FEATURE_ML_DETECTION` or `FEATURE_ADVANCED_EVALS` flags. See [Configuration](../getting-started/configuration.md) for details.
