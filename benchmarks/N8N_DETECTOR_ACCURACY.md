# n8n Detector Benchmark Results

**Run Date**: 2026-01-28 20:06:55
**Total Workflows**: 84

## Overall Results

| Detector | Precision | Recall | F1 Score | Accuracy | TP | FP | TN | FN |
|----------|-----------|--------|----------|----------|----|----|----|----|
| N8NCycleDetector | 0.8333 | 0.2500 | 0.3846 | 0.2381 | 20 | 4 | 0 | 60 |
| N8NSchemaDetector | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 84 | 0 | 0 |
| N8NResourceDetector | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 0 | 84 |
| N8NTimeoutDetector | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 0 | 84 |
| N8NErrorDetector | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 0 | 84 |
| N8NComplexityDetector | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 84 | 0 | 0 |

## Average Metrics

- **Average Precision**: 0.1389
- **Average Recall**: 0.0417
- **Average F1 Score**: 0.0641

## Detection Rate by Failure Mode

| Failure Mode | Detected | Total | Detection Rate |
|--------------|----------|-------|----------------|
| F11 | 92 | 216 | 42.59% |
| F2 | 37 | 108 | 34.26% |
| F3 | 31 | 90 | 34.44% |
| F4 | 32 | 90 | 35.56% |