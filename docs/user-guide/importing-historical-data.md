# Importing Historical Data

Test MAO detection capabilities on your existing trace data without instrumenting your production systems.

## Supported Formats

| Source | Format | Export Guide |
|--------|--------|--------------|
| LangSmith | JSONL | [Export from LangSmith](#exporting-from-langsmith) |
| Langfuse | JSON | [Export from Langfuse](#exporting-from-langfuse) |
| OTLP | JSON | [Export from OTEL](#exporting-from-opentelemetry) |
| Custom | JSONL | [Generic format](#generic-format) |

## Quick Start

1. **Export your data** from LangSmith, Langfuse, or your observability platform
2. **Click "Import Historical Data"** on the Dashboard
3. **Drag & drop your file** (or click to browse)
4. **Start Import** - detection runs automatically
5. **View Results** - see detected issues and fix suggestions

## Step-by-Step Guide

### 1. Access Import

From the Dashboard, click the **"Import Historical Data"** button in the top right.

### 2. Upload File

- Drag and drop your `.json` or `.jsonl` file
- Or click the upload area to browse
- Maximum file size: 100MB

### 3. Select Format

- **Auto-detect** (recommended) - MAO will detect the format
- Or manually select: LangSmith, Langfuse, OTLP, Generic

### 4. Start Import

Click **Start Import** to begin processing. You'll see:
- Progress bar with completion percentage
- Records processed count
- Detections found in real-time

### 5. View Results

After import completes, you'll see:
- **Traces imported** - Number of agent workflows
- **Records processed** - Total agent steps
- **Issues detected** - Infinite loops, state corruption, etc.

Click **View Detections** to see details and fix suggestions.

---

## Exporting from LangSmith

1. Go to your LangSmith project
2. Navigate to **Runs** tab
3. Apply date filters as needed
4. Click **Export** → **Download as JSONL**
5. Import the downloaded file to MAO

### LangSmith Format Example

```jsonl
{"id": "run_abc123", "session_id": "session_xyz", "name": "researcher", "run_type": "chain", "inputs": {"query": "..."}, "outputs": {"response": "..."}, "start_time": "2024-12-25T10:00:00Z", "end_time": "2024-12-25T10:00:05Z"}
{"id": "run_def456", "session_id": "session_xyz", "name": "analyzer", "run_type": "chain", "inputs": {...}, "outputs": {...}, ...}
```

---

## Exporting from Langfuse

1. Go to your Langfuse project
2. Navigate to **Traces**
3. Click **Export** → **JSON**
4. Import the downloaded file to MAO

### Langfuse Format Example

```json
{
  "traces": [
    {
      "id": "trace_123",
      "name": "research_workflow",
      "observations": [
        {
          "id": "obs_1",
          "type": "GENERATION",
          "name": "researcher",
          "input": {"query": "..."},
          "output": {"response": "..."},
          "startTime": "2024-12-25T10:00:00Z",
          "endTime": "2024-12-25T10:00:05Z"
        }
      ]
    }
  ]
}
```

---

## Exporting from OpenTelemetry

If you're using OTEL Collector, configure a file exporter:

```yaml
exporters:
  file:
    path: /tmp/traces.json

service:
  pipelines:
    traces:
      exporters: [file]
```

Import the generated JSON file to MAO.

---

## Generic Format

If your data doesn't match supported formats, use JSONL with these fields:

```jsonl
{"trace_id": "t1", "agent_id": "researcher", "name": "search", "inputs": {...}, "outputs": {...}, "timestamp": "2024-12-25T10:00:00Z"}
```

### Required Fields

| Field | Description |
|-------|-------------|
| `trace_id` or `session_id` | Groups related steps |
| `agent_id` or `agent` or `name` | Agent/node identifier |
| `timestamp` or `start_time` | When step occurred |

### Optional Fields

| Field | Description |
|-------|-------------|
| `inputs` or `input` | Step input data |
| `outputs` or `output` | Step output data |
| `tokens` or `token_count` | Token usage |
| `end_time` | Step completion time |

---

## API Reference

### Create Import Job

```bash
curl -X POST https://api.mao-testing.com/api/v1/import-jobs \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@traces.jsonl" \
  -F "format=auto"
```

### Check Import Status

```bash
curl https://api.mao-testing.com/api/v1/import-jobs/{job_id} \
  -H "Authorization: Bearer $API_KEY"
```

### Get Import Results

```bash
curl https://api.mao-testing.com/api/v1/import-jobs/{job_id}/results \
  -H "Authorization: Bearer $API_KEY"
```

---

## Troubleshooting

### "Could not detect file format"

- Ensure your file is valid JSON or JSONL
- Try selecting the format manually
- Check that records have required fields

### "This file has already been imported"

- Each file can only be imported once (duplicate prevention)
- Modify the file or export fresh data to re-import

### "File too large"

- Maximum file size is 100MB
- Split large exports into multiple files
- Use date filters when exporting

### Import fails with errors

- Check the error details in import results
- Verify your export format matches examples above
- Ensure timestamps are in ISO 8601 format

---

## FAQ

**Q: Does import affect my production data?**
A: No. Imported data is stored separately and marked as "imported". It doesn't affect live monitoring.

**Q: Can I delete imported data?**
A: Yes. Use the DELETE endpoint or contact support.

**Q: How long does import take?**
A: Typically 1-5 minutes for 10,000 records. Larger files may take longer.

**Q: Are detections run automatically?**
A: Yes. All detection algorithms (loops, corruption, drift, deadlock) run on imported data.
