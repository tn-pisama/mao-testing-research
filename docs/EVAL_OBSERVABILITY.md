# Eval Observability with Phoenix

PISAMA's detection calibration pipeline can export per-detector evaluation traces to [Arize Phoenix](https://github.com/Arize-AI/phoenix) via OpenTelemetry.

## Quick Start

```bash
# Install dependencies
pip install arize-phoenix opentelemetry-sdk opentelemetry-exporter-otlp-proto-http

# Start Phoenix UI
phoenix serve  # Starts on http://localhost:6006

# Run calibration with tracing
cd backend
python -m app.detection_enterprise.calibrate --phoenix
```

Open http://localhost:6006 to see calibration traces.

## What Gets Traced

- **Parent span**: `calibration_run` with dataset size and detector count
- **Child spans**: One per detector type (`calibrate_loop`, `calibrate_hallucination`, etc.) with:
  - `detector.type`: Detection type name
  - `detector.sample_count`: Number of golden entries evaluated
  - `detector.f1`: F1 score
  - `detector.precision`: Precision
  - `detector.recall`: Recall
  - `detector.threshold`: Optimal confidence threshold

## CLI Flags

| Flag | Description |
|------|-------------|
| `--phoenix` | Enable Phoenix OTEL export |
| `--phoenix-endpoint URL` | Custom OTLP endpoint (default: `http://localhost:6006/v1/traces`) |

## Custom Endpoint

To export to a remote Phoenix instance or any OTLP-compatible collector:

```bash
python -m app.detection_enterprise.calibrate \
  --phoenix \
  --phoenix-endpoint https://my-phoenix.example.com/v1/traces
```

## Experiment Tracking

Calibration runs are also tracked locally in `data/calibration_history.jsonl`. Compare recent experiments:

```bash
python -m app.detection_enterprise.calibrate --compare 3
```

## Architecture

```
calibrate.py  --phoenix-->  phoenix_exporter.py  --OTLP/HTTP-->  Phoenix UI
     |                                                              |
     v                                                              v
calibration_history.jsonl                                    Trace Explorer
```
