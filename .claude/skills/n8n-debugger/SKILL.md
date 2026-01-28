---
name: n8n-debugger
description: |
  Debug n8n workflow failures and integration issues.
  Use when troubleshooting n8n workflows, webhook integration, or execution log parsing.
  Provides common failure patterns and remediation steps.
allowed-tools: Read, Grep, Glob, Bash
---

# n8n Debugger Skill

You are debugging n8n workflow failures in the PISAMA platform. Your goal is to diagnose issues, identify root causes, and provide remediation guidance.

## n8n Integration Overview

PISAMA integrates with n8n in two ways:
1. **Webhook ingestion**: n8n sends execution logs to PISAMA webhook
2. **API client**: PISAMA queries n8n API for workflow details

```
n8n Workflow → Webhook → PISAMA /api/v1/n8n/webhook → Parser → Detection
         ↓
PISAMA API Client → n8n API → Workflow Details
```

---

## Common Failure Patterns

### Pattern 1: Webhook Not Receiving Data

**Symptoms:**
- n8n workflow completes but no trace in PISAMA
- Webhook endpoint returns 404 or 500

**Diagnosis:**
```bash
# Check webhook endpoint status
curl -X POST http://localhost:8000/api/v1/n8n/webhook \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'

# Check logs
tail -f backend/logs/application.log | grep "n8n/webhook"
```

**Common Causes:**
1. Incorrect webhook URL in n8n workflow
2. Authentication token missing or invalid
3. Network/firewall blocking webhook

**Fix:**
```json
// n8n HTTP Request node configuration
{
  "method": "POST",
  "url": "https://your-pisama-instance.com/api/v1/n8n/webhook",
  "authentication": "headerAuth",
  "headerParameters": {
    "parameters": [
      {
        "name": "Authorization",
        "value": "Bearer {{$env.PISAMA_API_KEY}}"
      }
    ]
  },
  "body": {
    "executionId": "={{$execution.id}}",
    "workflowId": "={{$workflow.id}}",
    "status": "={{$execution.status}}",
    "data": "={{$json}}"
  }
}
```

---

### Pattern 2: Execution Log Parsing Failure

**Symptoms:**
- Webhook receives data but no trace created
- Error: "Failed to parse n8n execution log"

**Diagnosis:**
```python
# Check parser logs
import json

with open("failed_execution.json") as f:
    data = json.load(f)

from app.ingestion.n8n_parser import N8NParser
parser = N8NParser()

try:
    trace = parser.parse(data)
except Exception as e:
    print(f"Parse error: {e}")
```

**Common Causes:**
1. Unexpected n8n execution format (version mismatch)
2. Missing required fields (executionId, workflowId)
3. Malformed JSON in execution data

**Fix:**
- Update `app/ingestion/n8n_parser.py` for new n8n format
- Add validation for required fields
- Handle edge cases (empty executions, errors)

---

### Pattern 3: Detection Not Running on n8n Traces

**Symptoms:**
- Trace created successfully
- No detections found for obviously failing workflow

**Diagnosis:**
```bash
# Check if detection ran
curl http://localhost:8000/api/v1/traces/{trace_id}/detections

# Manually trigger detection
curl -X POST http://localhost:8000/api/v1/traces/{trace_id}/detect
```

**Common Causes:**
1. n8n traces not tagged for detection
2. Detection disabled for n8n source
3. n8n-specific detector not invoked

**Fix:**
```python
# Ensure n8n detector is registered
from app.detection.n8n.n8n_detector import N8NDetector

detector = N8NDetector()
detections = detector.detect(trace)
```

---

### Pattern 4: Workflow Timeout Not Detected

**Symptoms:**
- n8n workflow times out
- PISAMA doesn't flag it as failure

**Diagnosis:**
Check if timeout detection is enabled:
```python
from app.detection.n8n.timeout_detector import TimeoutDetector

detector = TimeoutDetector()
detections = detector.detect(trace)
```

**Fix:**
```python
# backend/app/detection/n8n/timeout_detector.py

class TimeoutDetectorConfig:
    max_workflow_duration_ms: int = 300000  # 5 minutes
    timeout_threshold: float = 0.95  # 95% of max duration

class TimeoutDetector:
    def detect(self, trace):
        workflow_duration = trace.end_time - trace.start_time
        
        if workflow_duration > self.config.max_workflow_duration_ms:
            return [Detection(
                type="timeout",
                severity="high",
                confidence=1.0,
                evidence={"duration_ms": workflow_duration}
            )]
        
        return []
```

---

### Pattern 5: Node Failure Not Propagated

**Symptoms:**
- Individual n8n node fails
- Workflow marked as "success" overall
- PISAMA doesn't detect node failure

**Diagnosis:**
```python
# Check if node failures are in execution log
execution = get_execution_from_n8n(execution_id)

for node_name, node_data in execution["data"]["resultData"]["runData"].items():
    for run in node_data:
        if run.get("error"):
            print(f"Node {node_name} failed: {run['error']}")
```

**Fix:**
Update n8n parser to extract node-level failures:
```python
def parse_node_failures(execution_data):
    """Extract node failures from n8n execution."""
    failures = []
    
    run_data = execution_data.get("data", {}).get("resultData", {}).get("runData", {})
    
    for node_name, node_runs in run_data.items():
        for run in node_runs:
            if "error" in run:
                failures.append({
                    "node": node_name,
                    "error": run["error"],
                    "timestamp": run.get("startTime")
                })
    
    return failures
```

---

## Debugging Checklist

### Webhook Integration
- [ ] Webhook URL correct in n8n workflow
- [ ] Authentication token valid
- [ ] Webhook endpoint returns 200 OK for test POST
- [ ] Network allows n8n → PISAMA connection
- [ ] PISAMA logs show webhook requests arriving

### Execution Log Parsing
- [ ] Execution log format matches parser expectations
- [ ] Required fields present (executionId, workflowId, status)
- [ ] JSON is valid and well-formed
- [ ] Parser handles n8n version (check n8n version in logs)

### Detection
- [ ] Trace created in PISAMA database
- [ ] Detection triggered (automatic or manual)
- [ ] n8n-specific detectors registered
- [ ] Detection results visible in API/UI

### n8n API Integration
- [ ] n8n API credentials configured
- [ ] API client can reach n8n instance
- [ ] Workflow details fetched successfully

---

## Testing n8n Integration

### End-to-End Test

```bash
#!/bin/bash
# Test complete n8n integration

# 1. Create test workflow in n8n
n8n_workflow_id=$(curl -X POST http://localhost:5678/api/v1/workflows \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Workflow", "nodes": [...]}' \
  | jq -r '.id')

# 2. Execute workflow
n8n_execution_id=$(curl -X POST http://localhost:5678/api/v1/workflows/$n8n_workflow_id/execute \
  | jq -r '.id')

# 3. Wait for execution to complete
sleep 5

# 4. Check if trace arrived in PISAMA
pisama_trace=$(curl http://localhost:8000/api/v1/traces?source=n8n \
  | jq ".traces[] | select(.metadata.n8n_execution_id == \"$n8n_execution_id\")")

if [ -n "$pisama_trace" ]; then
  echo "✓ Trace received in PISAMA"
else
  echo "✗ Trace NOT received"
  exit 1
fi

# 5. Check if detections ran
trace_id=$(echo $pisama_trace | jq -r '.trace_id')
detections=$(curl http://localhost:8000/api/v1/traces/$trace_id/detections)

echo "Detections found: $(echo $detections | jq '. | length')"
```

---

## n8n-Specific Detection Algorithms

### Loop in n8n Workflow

Common in n8n when:
- Loop node iterates infinitely
- Split-Merge pattern creates cycle
- Conditional node always returns to same node

**Detection:**
```python
def detect_n8n_loop(trace):
    """Detect loops in n8n workflow execution."""
    node_sequence = [span.attributes.get("n8n.node.name") for span in trace.spans]
    
    # Check for repeated node sequences
    for i in range(len(node_sequence) - 3):
        sequence = tuple(node_sequence[i:i+3])
        if node_sequence.count(sequence) >= 2:
            return Detection(
                type="loop",
                subtype="n8n_workflow_loop",
                confidence=0.95,
                evidence={"repeated_sequence": sequence}
            )
```

---

## Resources

For n8n debugging guides:
- `resources/n8n-patterns.md` - Common n8n failure patterns
- `backend/app/integrations/n8n_client.py` - n8n API client
- `backend/app/ingestion/n8n_parser.py` - n8n execution log parser
- `docs/N8N_INTEGRATION.md` - Integration setup guide
