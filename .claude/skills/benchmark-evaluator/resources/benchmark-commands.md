# Benchmark Commands Reference

Complete command reference for MAST benchmark evaluation.

---

## Basic Commands

### Run All Benchmarks
```bash
cd backend
pytest tests/benchmark/ -v
```

### Run Specific Benchmark Test
```bash
pytest tests/benchmark/test_mast_evaluation.py::test_overall_f1_target -v
pytest tests/benchmark/test_loop_detection.py -v
pytest tests/benchmark/test_state_corruption.py -v
```

### Generate Detailed Report
```bash
python -m app.benchmark.evaluate_mast \
  --output results/mast_eval_$(date +%Y%m%d).json \
  --verbose \
  --save-errors
```

---

## Advanced Options

### Evaluate Single Detector
```bash
python -m app.benchmark.evaluate_mast \
  --detector loop \
  --output results/loop_only.json
```

### Evaluate by Failure Type
```bash
python -m app.benchmark.evaluate_mast \
  --failure-type LOOP \
  --failure-type STATE \
  --output results/loop_state.json
```

### With Custom Thresholds
```bash
python -m app.benchmark.evaluate_mast \
  --config custom_thresholds.json \
  --output results/custom.json
```

custom_thresholds.json:
```json
{
  "loop": {"semantic_similarity_threshold": 0.80},
  "persona": {"drift_threshold": 0.70},
  "corruption": {"consistency_threshold": 0.92}
}
```

---

## Output Formats

### JSON (Default)
```bash
python -m app.benchmark.evaluate_mast --output results.json
```

### CSV (For Spreadsheet Analysis)
```bash
python -m app.benchmark.evaluate_mast --format csv --output results.csv
```

### Markdown (For Documentation)
```bash
python -m app.benchmark.evaluate_mast --format markdown --output RESULTS.md
```

---

## Analysis Commands

### Compare Two Runs
```bash
python -m app.benchmark.compare \
  --baseline results/baseline.json \
  --current results/after_tuning.json \
  --output comparison.md
```

### Generate Confusion Matrix
```bash
python -m app.benchmark.confusion_matrix \
  --input results/mast_eval.json \
  --output confusion.png
```

### Extract False Positives
```bash
python -m app.benchmark.analyze_errors \
  --input results/mast_eval.json \
  --error-type false_positive \
  --output fp_analysis.json
```

### Extract False Negatives
```bash
python -m app.benchmark.analyze_errors \
  --input results/mast_eval.json \
  --error-type false_negative \
  --output fn_analysis.json
```

---

## Continuous Monitoring

### Run Nightly Benchmarks
```bash
#!/bin/bash
# Save as scripts/nightly_benchmark.sh

DATE=$(date +%Y%m%d)
OUTPUT_DIR="results/nightly"
mkdir -p $OUTPUT_DIR

python -m app.benchmark.evaluate_mast \
  --output "$OUTPUT_DIR/mast_$DATE.json" \
  --verbose

# If F1 drops below threshold, alert
F1=$(jq '.overall.f1' "$OUTPUT_DIR/mast_$DATE.json")
if (( $(echo "$F1 < 0.70" | bc -l) )); then
  echo "ALERT: F1 score dropped to $F1"
  # Send notification (Slack, email, etc.)
fi
```

### Track Metrics Over Time
```bash
python -m app.benchmark.trend_analysis \
  --input-dir results/nightly/ \
  --output trend_report.html
```
