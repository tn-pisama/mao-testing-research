# Historical Data Replay Feature Plan

## Overview

Allow users to upload historical trace/log data to test MAO detection capabilities without instrumenting their production systems.

## Architecture Review Feedback (Applied)

### Backend Architect Feedback
- ✅ Use streaming file processing (not memory loading)
- ✅ Background async processing with progress tracking
- ✅ Better REST conventions (import-jobs resource)
- ✅ Add DELETE/LIST endpoints
- ✅ File hash for deduplication
- ✅ Batch inserts for performance (COPY)
- ✅ Partial success handling
- ✅ Import errors table for debugging

### Security Feedback
- ✅ File type validation before processing
- ✅ JSON depth limits to prevent DoS
- ✅ Sanitize all imported data
- ✅ Rate limiting per tenant
- ✅ Temp file cleanup with timeout

### UX Feedback
- ✅ Clear empty states and error messages
- ✅ Sample file download option
- ✅ Progress with ETA
- ✅ Success celebration with key metrics

## Goals

1. **Reduce adoption friction** - Test on real data before committing to SDK integration
2. **Demonstrate value** - Show detections on user's own historical data
3. **Enable retroactive analysis** - Find past incidents for compliance/audit
4. **Fast POC** - Minutes to value instead of days

## Supported Formats

| Format | Source | Priority | Parser |
|--------|--------|----------|--------|
| LangSmith JSONL | LangSmith export | P1 | `langsmith_parser.py` |
| Langfuse JSON | Langfuse export | P1 | `langfuse_parser.py` |
| OTLP JSON | OTEL Collector | P1 | `otel_parser.py` (existing) |
| Generic JSONL | Custom logs | P2 | `generic_parser.py` |

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend      │     │    Backend       │     │   Workers       │
│                 │     │                  │     │                 │
│  Upload UI ─────┼────▶│ POST /import     │────▶│ Process Queue   │
│                 │     │                  │     │                 │
│  Progress ◀─────┼─────│ GET /import/{id} │◀────│ Run Detections  │
│                 │     │                  │     │                 │
│  Results ◀──────┼─────│ GET /import/{id} │     │ Store Results   │
│                 │     │   /results       │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## API Design

### List Import Jobs

```http
GET /api/v1/import-jobs?page=1&per_page=20
```

### Create Import Job

```http
POST /api/v1/import-jobs
Content-Type: multipart/form-data

file: <uploaded file>
format: "langsmith" | "langfuse" | "otlp" | "auto"
```

**Response (202 Accepted):**
```json
{
  "id": "imp_abc123",
  "status": "pending",
  "format_detected": "langsmith",
  "record_count_estimate": 1247,
  "created_at": "2024-12-26T..."
}
```

### Get Import Status

```http
GET /api/v1/import-jobs/{import_id}
```

**Response:**
```json
{
  "id": "imp_abc123",
  "status": "processing",
  "progress": {
    "records_total": 1247,
    "records_processed": 523,
    "records_failed": 2,
    "traces_created": 89,
    "detections_found": 7
  },
  "started_at": "...",
  "estimated_seconds_remaining": 120
}
```

### Get Import Results

```http
GET /api/v1/import-jobs/{import_id}/results
```

### Delete Import Job

```http
DELETE /api/v1/import-jobs/{import_id}
```

**Response:**
```json
{
  "id": "imp_abc123",
  "status": "completed",
  "summary": {
    "traces_imported": 89,
    "states_imported": 1247,
    "detections": {
      "infinite_loop": 3,
      "state_corruption": 2,
      "persona_drift": 1,
      "coordination_deadlock": 1
    },
    "estimated_cost_impact": "$2,847"
  },
  "traces": [...],
  "detections": [...]
}
```

## Database Schema

```sql
CREATE TABLE import_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  format VARCHAR(50),
  file_name VARCHAR(255) NOT NULL,
  file_size_bytes BIGINT NOT NULL,
  file_hash VARCHAR(64) NOT NULL,
  records_total INT DEFAULT 0,
  records_processed INT DEFAULT 0,
  records_failed INT DEFAULT 0,
  traces_created INT DEFAULT 0,
  detections_found INT DEFAULT 0,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  CONSTRAINT valid_progress CHECK (records_processed <= records_total)
);

CREATE INDEX idx_import_jobs_tenant ON import_jobs(tenant_id);
CREATE INDEX idx_import_jobs_status ON import_jobs(status);
CREATE UNIQUE INDEX idx_import_jobs_file_hash ON import_jobs(tenant_id, file_hash);

CREATE TABLE import_errors (
  id SERIAL PRIMARY KEY,
  import_job_id UUID NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE,
  record_index INT NOT NULL,
  error_message TEXT NOT NULL,
  raw_record JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_import_errors_job ON import_errors(import_job_id);
```

## Frontend Components

### 1. Import Button (Dashboard)

Location: Dashboard header or empty state

```tsx
<Button onClick={openImportModal}>
  <UploadIcon />
  Import Historical Data
</Button>
```

### 2. Import Modal

```
┌─────────────────────────────────────────────────────────┐
│  Import Historical Data                            [X]  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │                                                  │   │
│  │     Drag & drop your file here                  │   │
│  │     or click to browse                          │   │
│  │                                                  │   │
│  │     Supported: LangSmith, Langfuse, OTLP JSON   │   │
│  │                                                  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Format: [Auto-detect ▼]                               │
│                                                         │
│  ☑ Run all detections after import                     │
│  ☐ Sample data (process 10% for quick preview)         │
│                                                         │
│                              [Cancel]  [Start Import]   │
└─────────────────────────────────────────────────────────┘
```

### 3. Import Progress

```
┌─────────────────────────────────────────────────────────┐
│  Importing...                                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ████████████████░░░░░░░░░░░░░░  42%                   │
│                                                         │
│  Processed: 523 / 1,247 records                        │
│  Traces created: 89                                     │
│  Detections found: 7                                    │
│                                                         │
│  Estimated time remaining: 2 minutes                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4. Import Results

```
┌─────────────────────────────────────────────────────────┐
│  Import Complete ✓                                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  📊 Summary                                             │
│  ─────────────────────────────────────────────────────  │
│  Traces imported:     89                                │
│  Agent steps:         1,247                             │
│  Time range:          Dec 1-25, 2024                    │
│                                                         │
│  🔍 Detections Found                                    │
│  ─────────────────────────────────────────────────────  │
│  ⚠️  3 Infinite Loops         [View]                    │
│  ⚠️  2 State Corruptions      [View]                    │
│  ⚠️  1 Persona Drift          [View]                    │
│  ⚠️  1 Deadlock               [View]                    │
│                                                         │
│  💰 Estimated Impact: $2,847 in wasted API costs       │
│                                                         │
│                    [View All Traces]  [View Detections] │
└─────────────────────────────────────────────────────────┘
```

## File Parsers

### LangSmith Format

```python
# Expected format (JSONL - one run per line)
{
  "id": "run_abc123",
  "parent_run_id": "run_parent",
  "name": "agent_node",
  "run_type": "chain",
  "inputs": {"query": "..."},
  "outputs": {"response": "..."},
  "start_time": "2024-12-25T10:00:00Z",
  "end_time": "2024-12-25T10:00:05Z",
  "extra": {"tokens": 150}
}
```

### Langfuse Format

```python
# Expected format (JSON array of traces)
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
          "input": {...},
          "output": {...},
          "startTime": "...",
          "endTime": "..."
        }
      ]
    }
  ]
}
```

## Implementation Tasks

### Backend (2 days)

1. **Import model and API** (0.5 day)
   - Database migration for imports table
   - POST /imports endpoint with file upload
   - GET /imports/{id} status endpoint
   - GET /imports/{id}/results endpoint

2. **File parsers** (1 day)
   - LangSmith JSONL parser
   - Langfuse JSON parser
   - Auto-detection logic
   - Validation and error handling

3. **Processing pipeline** (0.5 day)
   - Async processing with progress updates
   - Batch insert for performance
   - Run detection algorithms
   - Error recovery

### Frontend (1.5 days)

1. **Import modal** (0.5 day)
   - File drag & drop
   - Format selection
   - Options checkboxes

2. **Progress tracking** (0.5 day)
   - Real-time progress bar
   - Detection count updates
   - Error display

3. **Results display** (0.5 day)
   - Summary cards
   - Detection list
   - Navigation to traces/detections

### Documentation (0.5 day)

1. **User guide**
   - How to export from LangSmith
   - How to export from Langfuse
   - Import walkthrough

2. **API reference**
   - Import endpoints
   - Format specifications

## Security Considerations

- File size limit: 100MB (configurable)
- Rate limit: 5 imports per hour per tenant
- File type validation (JSON/JSONL only, check magic bytes)
- JSON parsing depth limit (max 50 levels)
- JSON object size limit (max 10MB per record)
- Sanitize all imported data (strip PII patterns)
- Tenant isolation for imported data
- Temporary file cleanup (5 minute timeout)
- File hash to prevent duplicate processing

## Success Metrics

- Time to first import: < 2 minutes
- Import success rate: > 95%
- User activation via import: track conversion

## Total Effort: 4 days
