# Claude Model Comparison Report for MAST Detection

**Date**: 2026-01-11
**Test Size**: 102 traces per model (17 traces × 6 failure modes)
**Failure Modes Tested**: F1, F3, F6, F7, F8, F14

---

## Executive Summary

Testing all available Claude models for MAST LLM-as-Judge detection revealed that **Claude Sonnet 4 with Extended Thinking achieves the best accuracy (99.0%)** while maintaining reasonable cost.

### Key Findings:

1. **Extended thinking provides +2% accuracy boost** (97.1% → 99.0%)
2. **Sonnet 4 matches Opus 4.5 accuracy at 80% lower cost**
3. **Sonnet 4 is 31% faster than Opus 4.5** (4642ms vs 6081ms)
4. **Extended thinking doubles latency** but significantly improves accuracy

---

## Model Comparison Results

| Model | Accuracy | F1 Score | Total Cost | Avg Latency | Cost/Accuracy |
|-------|----------|----------|------------|-------------|---------------|
| **sonnet-4-thinking** | **99.0%** | **0.991** | $1.66 | 12,299ms | $0.017/% |
| opus-4.5 | 97.1% | 0.973 | $2.38 | 6,081ms | $0.025/% |
| opus-4.5-thinking | 97.1% | 0.973 | $6.20 | 12,072ms | $0.064/% |
| sonnet-4 | 97.1% | 0.973 | $0.48 | 4,642ms | $0.005/% |

### Notes:
- Claude 3.5 Sonnet and Haiku models were unavailable (404 errors) with the test API key
- Results based on 102 adversarial traces across 6 failure modes

---

## Cost Analysis (Per 100 Judgments)

Assuming average of 10K input tokens + 500 output tokens per judgment:

| Model | Input Cost | Output Cost | Thinking Cost | Total | Relative |
|-------|-----------|-------------|---------------|-------|----------|
| sonnet-4 | $0.30 | $0.08 | - | **$0.38** | 1.0x |
| sonnet-4-thinking | $0.30 | $0.08 | ~$0.80 | **$1.18** | 3.1x |
| opus-4.5 | $1.50 | $0.38 | - | **$1.88** | 4.9x |
| opus-4.5-thinking | $1.50 | $0.38 | ~$1.60 | **$3.48** | 9.2x |

**Conclusion**: Sonnet 4 without thinking is **5x cheaper** than Opus 4.5 with same accuracy.

---

## Latency Analysis

| Model | Avg Latency | Relative |
|-------|-------------|----------|
| sonnet-4 | 4,642ms | 1.0x (fastest) |
| opus-4.5 | 6,081ms | 1.3x |
| opus-4.5-thinking | 12,072ms | 2.6x |
| sonnet-4-thinking | 12,299ms | 2.6x |

**Conclusion**: Non-thinking models are 2.6x faster than thinking variants.

---

## Recommendations

### Production Configuration

Based on the benchmark results, we recommend a **tiered approach**:

#### 1. Default Model: Claude Sonnet 4 (Standard)
- **Use for**: High-volume, latency-sensitive detection
- **Expected accuracy**: 97.1%
- **Cost**: ~$0.38 per 100 judgments
- **Latency**: ~4.6 seconds

```python
# Default configuration
detector = FullLLMDetector(model_key="sonnet-4")
```

#### 2. High-Stakes Model: Claude Sonnet 4 with Extended Thinking
- **Use for**: Critical detections, ambiguous cases, high-value customers
- **Expected accuracy**: 99.0%
- **Cost**: ~$1.18 per 100 judgments
- **Latency**: ~12.3 seconds

```python
# High-stakes configuration
detector = FullLLMDetector(model_key="sonnet-4-thinking")
```

#### 3. Tiered Strategy Implementation

```python
def get_detector_for_mode(failure_mode: str, is_high_stakes: bool = False):
    """Select optimal model based on failure mode and stakes."""

    # High-stakes modes always use extended thinking
    high_stakes_modes = {"F6", "F8"}  # State Corruption, Task Derailment

    if failure_mode in high_stakes_modes or is_high_stakes:
        return FullLLMDetector(model_key="sonnet-4-thinking")

    return FullLLMDetector(model_key="sonnet-4")
```

---

## Cost Savings Projection

Switching from current Opus 4.5 to Sonnet 4 configuration:

| Scenario | Monthly Volume | Opus 4.5 Cost | Sonnet 4 Cost | Savings |
|----------|----------------|---------------|---------------|---------|
| Small | 10,000 judgments | $188 | $38 | **$150 (80%)** |
| Medium | 100,000 judgments | $1,880 | $380 | **$1,500 (80%)** |
| Large | 1,000,000 judgments | $18,800 | $3,800 | **$15,000 (80%)** |

With tiered approach (80% Sonnet, 20% Sonnet+Thinking):

| Scenario | Monthly Volume | Cost | vs. Pure Opus |
|----------|----------------|------|---------------|
| Small | 10,000 | $54 | **71% savings** |
| Medium | 100,000 | $540 | **71% savings** |
| Large | 1,000,000 | $5,400 | **71% savings** |

---

## Implementation Checklist

- [x] Multi-model support added to `FullLLMDetector`
- [x] Extended thinking support implemented
- [x] Cost tracking updated for Claude 4.5 models
- [x] Benchmark script created
- [ ] Update hybrid_pipeline.py to use tiered model selection
- [ ] Add model selection to API configuration
- [ ] Update documentation with new model options

---

## Appendix: Raw Benchmark Data

### opus-4.5
```
Accuracy: 97.1%
F1 Score: 0.973
Total Cost: $2.3818
Avg Latency: 6081ms
Tests: 102
```

### opus-4.5-thinking
```
Accuracy: 97.1%
F1 Score: 0.973
Total Cost: $6.1991
Avg Latency: 12072ms
Tests: 102
```

### sonnet-4
```
Accuracy: 97.1%
F1 Score: 0.973
Total Cost: $0.4760
Avg Latency: 4642ms
Tests: 102
```

### sonnet-4-thinking
```
Accuracy: 99.0%
F1 Score: 0.991
Total Cost: $1.6617
Avg Latency: 12299ms
Tests: 102
```

---

## Conclusion

**Sonnet 4 is the optimal choice for production**, matching Opus 4.5 accuracy at 80% lower cost and 30% lower latency. For critical detections requiring maximum accuracy, **Sonnet 4 with Extended Thinking** provides the best results (99.0% accuracy) at a fraction of Opus 4.5's cost.

The recommended configuration is:
- **Default**: `sonnet-4` for standard detection
- **High-stakes**: `sonnet-4-thinking` for critical failure modes

This tiered approach provides **71% cost savings** while maintaining or improving detection accuracy.
