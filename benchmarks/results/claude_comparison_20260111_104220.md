# Claude Model Comparison Report

Generated: 2026-01-11T10:42:20.983901

Models tested: 6

## Summary

| Model | Accuracy | F1 Score | Precision | Recall | Total Cost | Avg Latency | Cost/F1 |
|-------|----------|----------|-----------|--------|------------|-------------|---------|
| sonnet-3.5 | 100.0% | 1.000 | 1.000 | 1.000 | $0.2742 | 5052ms | $0.2742 |
| sonnet-4-thinking | 99.0% | 0.991 | 1.000 | 0.982 | $1.6617 | 12299ms | $1.6766 |
| opus-4.5 | 97.1% | 0.973 | 1.000 | 0.947 | $2.3818 | 6081ms | $2.4479 |
| opus-4.5-thinking | 97.1% | 0.973 | 1.000 | 0.947 | $6.1991 | 12072ms | $6.3713 |
| sonnet-4 | 97.1% | 0.973 | 1.000 | 0.947 | $0.4760 | 4642ms | $0.4892 |
| haiku-3.5 | 97.1% | 0.973 | 1.000 | 0.947 | $0.1109 | 3932ms | $0.1140 |

## Recommendations

- **Best Accuracy**: sonnet-3.5 (100.0%)
- **Best Cost Efficiency**: haiku-3.5 ($0.1140 per F1 point)
- **Cheapest**: haiku-3.5 ($0.1109 total)

## Per-Model Details

### sonnet-3.5
- Model ID: `claude-3-5-sonnet-20241022`
- Tests: 102 (Correct: 102, Incorrect: 0, Errors: 0)
- Confusion Matrix: TP=57, FP=0, TN=45, FN=0
- Total Tokens: 73,886

**Per Failure Mode:**

- F1: 17/17 (100.0%) - $0.0420
- F14: 17/17 (100.0%) - $0.0408
- F3: 17/17 (100.0%) - $0.0406
- F6: 17/17 (100.0%) - $0.0532
- F7: 17/17 (100.0%) - $0.0418
- F8: 17/17 (100.0%) - $0.0560

### sonnet-4-thinking
- Model ID: `claude-sonnet-4-20250514`
- Tests: 102 (Correct: 101, Incorrect: 1, Errors: 0)
- Confusion Matrix: TP=56, FP=0, TN=45, FN=1
- Total Tokens: 185,117

**Per Failure Mode:**

- F1: 16/17 (94.1%) - $0.2489
- F14: 17/17 (100.0%) - $0.3035
- F3: 17/17 (100.0%) - $0.2284
- F6: 17/17 (100.0%) - $0.3042
- F7: 17/17 (100.0%) - $0.2573
- F8: 17/17 (100.0%) - $0.3195

### opus-4.5
- Model ID: `claude-opus-4-5-20251101`
- Tests: 102 (Correct: 99, Incorrect: 3, Errors: 0)
- Confusion Matrix: TP=54, FP=0, TN=45, FN=3
- Total Tokens: 86,385

**Per Failure Mode:**

- F1: 14/17 (82.4%) - $0.3464
- F14: 17/17 (100.0%) - $0.3805
- F3: 17/17 (100.0%) - $0.3517
- F6: 17/17 (100.0%) - $0.4589
- F7: 17/17 (100.0%) - $0.3637
- F8: 17/17 (100.0%) - $0.4806

### opus-4.5-thinking
- Model ID: `claude-opus-4-5-20251101`
- Tests: 102 (Correct: 99, Incorrect: 3, Errors: 0)
- Confusion Matrix: TP=54, FP=0, TN=45, FN=3
- Total Tokens: 181,184

**Per Failure Mode:**

- F1: 14/17 (82.4%) - $0.9720
- F14: 17/17 (100.0%) - $1.0808
- F3: 17/17 (100.0%) - $0.7775
- F6: 17/17 (100.0%) - $1.1584
- F7: 17/17 (100.0%) - $0.8817
- F8: 17/17 (100.0%) - $1.3287

### sonnet-4
- Model ID: `claude-sonnet-4-20250514`
- Tests: 102 (Correct: 99, Incorrect: 3, Errors: 0)
- Confusion Matrix: TP=54, FP=0, TN=45, FN=3
- Total Tokens: 86,372

**Per Failure Mode:**

- F1: 14/17 (82.4%) - $0.0625
- F14: 17/17 (100.0%) - $0.0645
- F3: 17/17 (100.0%) - $0.0629
- F6: 17/17 (100.0%) - $0.0975
- F7: 17/17 (100.0%) - $0.0648
- F8: 17/17 (100.0%) - $0.1239

### haiku-3.5
- Model ID: `claude-3-5-haiku-20241022`
- Tests: 102 (Correct: 99, Incorrect: 3, Errors: 0)
- Confusion Matrix: TP=54, FP=0, TN=45, FN=3
- Total Tokens: 82,363

**Per Failure Mode:**

- F1: 14/17 (82.4%) - $0.0160
- F14: 17/17 (100.0%) - $0.0170
- F3: 17/17 (100.0%) - $0.0165
- F6: 17/17 (100.0%) - $0.0220
- F7: 17/17 (100.0%) - $0.0170
- F8: 17/17 (100.0%) - $0.0225

## Cost Analysis

**Cost per 100 judgments (estimated):**

| Model | Estimated Cost |
|-------|---------------|
| sonnet-3.5 | $0.27 |
| sonnet-4-thinking | $1.63 |
| opus-4.5 | $2.34 |
| opus-4.5-thinking | $6.08 |
| sonnet-4 | $0.47 |
| haiku-3.5 | $0.11 |

## Tiered Strategy Recommendation

Based on results, consider a tiered approach:

1. **High-stakes modes** (F6, F8 - semantic complexity): Use best-performing model
2. **Clear-cut modes** (F1, F3 - pattern-based): Use cost-efficient model
3. **Default**: Use balanced model with Opus escalation for uncertain cases
