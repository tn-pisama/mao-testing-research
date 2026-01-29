# Moltbot MAST Benchmarks

Test cases for validating PISAMA detection capabilities against Moltbot agent traces.

## Overview

These benchmarks test PISAMA's ability to detect agent failures in Moltbot deployments. Moltbot is an open-source personal AI assistant with complex multi-tool orchestration across channels (WhatsApp, Telegram, Slack, Discord, etc.).

## Benchmark Files

| File | Detector | Cases | Description |
|------|----------|-------|-------------|
| `loop_detection.json` | Loop | 2 | Tool loops (browser navigation, filesystem search) |
| `overflow_detection.json` | Overflow | 1 | Context window exhaustion in long conversations |
| `persona_detection.json` | Persona | 1 | Personality drift across communication channels |
| `coordination_detection.json` | Coordination | 1 | Multi-step task handoff failures |
| `injection_detection.json` | Injection | 2 | Prompt injection attempts via messages/files |
| `completion_detection.json` | Completion | 1 | Premature task completion claims |
| `corruption_detection.json` | Corruption | 2 | Persistent memory inconsistencies |

**Total**: 7 detectors, 10 test cases

## Moltbot-Specific Patterns

These benchmarks capture failure modes unique to Moltbot's architecture:

1. **Multi-channel context**: Same user across WhatsApp, Slack, Discord
2. **Rich tool ecosystem**: Browser (CDP), filesystem, email, calendar, smart home
3. **Persistent sessions**: Long-running conversations with memory
4. **Sandbox execution**: Per-session Docker containers
5. **Real-time messaging**: Low-latency channel responses

## Running Benchmarks

### Via CLI

```bash
# Run all Moltbot benchmarks
python benchmarks/main.py --platform moltbot

# Run specific detector
python benchmarks/main.py --platform moltbot --detector loop

# Generate report
python benchmarks/main.py --platform moltbot --report
```

### Programmatically

```python
from benchmarks.evaluation import run_moltbot_benchmarks

results = run_moltbot_benchmarks()
print(f"Accuracy: {results['accuracy']}")
print(f"F1 Score: {results['f1_score']}")
```

## Expected Results

Target metrics for Moltbot benchmarks:

- **Precision**: ≥ 0.85
- **Recall**: ≥ 0.90
- **F1 Score**: ≥ 0.87
- **False Positive Rate**: ≤ 0.05

## Integration with PISAMA

These benchmarks validate that:

1. The `pisama-moltbot-adapter` correctly converts Moltbot events to OTEL traces
2. PISAMA detectors work on Moltbot-specific patterns
3. Detection latency is acceptable for real-time monitoring (< 500ms)

## Adding New Cases

To add a new test case:

1. Choose appropriate detector JSON file
2. Add case with unique `case_id` (format: `MOLTBOT_<DETECTOR>_<NUM>`)
3. Set `expected_detection` (true/false)
4. Set `difficulty` (easy/medium/hard)
5. Provide realistic Moltbot trace with proper span structure

Example:

```json
{
  "case_id": "MOLTBOT_LOOP_003",
  "description": "Email send loop with identical content",
  "expected_detection": true,
  "difficulty": "medium",
  "reason": "Agent repeatedly sends same email without variation",
  "trace": {
    "trace_id": "moltbot-loop-003",
    "platform": "moltbot",
    "session_id": "sess-003",
    "spans": [...]
  }
}
```

## References

- [Moltbot GitHub](https://github.com/moltbot/moltbot)
- [PISAMA Moltbot Adapter](../../packages/pisama-moltbot-adapter/)
- [MAST Benchmark Spec](../README.md)
