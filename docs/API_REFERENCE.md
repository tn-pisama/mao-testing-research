# API Reference

Base URL: `http://localhost:8000/api/v1`

All authenticated endpoints require either an API key (`X-MAO-API-Key` header) or a JWT Bearer token. Tenant-scoped endpoints include `{tenant_id}` in the path.

---

## Authentication

### `POST /auth/tenants`
Create a new tenant with API key.
- **Auth**: None
- **Response**: `201` — tenant object with API key

### `POST /auth/token`
Exchange API key for JWT token.
- **Body**: `{ "api_key": "string" }`
- **Response**: `{ "access_token": "string", "token_type": "bearer" }`

### `GET /auth/me`
Get current logged-in user profile.
- **Auth**: JWT or Clerk session

### `GET /auth/api-keys`
List API keys for the authenticated dashboard user.

### `POST /auth/api-keys`
Create a new API key (admin only).
- **Response**: `201`

### `DELETE /auth/api-keys/{key_id}`
Revoke an API key.
- **Response**: `204`

---

## Health

### `GET /health`
System health check (database, Redis).
- **Auth**: None
- **Response**: `{ "status": "healthy", "database": "ok", "redis": "ok" }`

---

## Traces

Prefix: `/tenants/{tenant_id}/traces`

### `POST /traces/ingest`
Ingest OpenTelemetry spans. Returns `202 Accepted`. Auto-rejects with `503` under backpressure.
- **Body**: OTEL span export format (JSON)

### `GET /traces`
List traces with pagination and filtering.
- **Query**: `page`, `page_size`, `agent_id`, `date_from`, `date_to`, `status`

### `GET /traces/{trace_id}`
Get single trace with all spans.

### `GET /traces/{trace_id}/states`
Get all state snapshots in a trace.

### `POST /traces/{trace_id}/analyze`
Run all detection algorithms on a trace. Returns detection results.

---

## Conversations

Prefix: `/tenants/{tenant_id}/conversations`

### `POST /conversations/ingest`
Ingest a conversation trace. Supports formats: `mast-data`, `openai`, `claude`, `generic`.
- **Body**: `{ "format": "string", "data": {...} }`

### `GET /conversations`
List conversation traces with pagination.

### `GET /conversations/{conversation_id}`
Get conversation details.

### `GET /conversations/{conversation_id}/turns`
Get turn-by-turn breakdown.

### `POST /conversations/{conversation_id}/analyze`
Run turn-aware detection algorithms.

---

## Detections

Prefix: `/tenants/{tenant_id}/detections`

### `GET /detections`
List detections with pagination and filtering.
- **Query**: `detection_type`, `validated`, `confidence_min`, `confidence_max`, `trace_id`, `date_from`, `date_to`, `page`, `page_size`

### `GET /detections/{detection_id}`
Get single detection with explanation and evidence.

### `POST /detections/{detection_id}/validate`
Mark a detection as validated (true positive or false positive).
- **Body**: `{ "is_valid": true, "feedback": "optional note" }`

### `GET /detections/{detection_id}/fixes`
Get AI-generated fix suggestions for a detection.

### `POST /detections/{detection_id}/fixes/{fix_id}/apply`
Record that a fix was applied.

---

## Agents

### `GET /tenants/{tenant_id}/agents`
List agents derived from trace data with stats.
- **Response**: Array of `{ agent_id, step_count, tokens_used, avg_latency_ms, last_active_at, status }`

---

## Analytics

Prefix: `/tenants/{tenant_id}/analytics`

### `GET /analytics/loops`
Loop detection statistics: method breakdown, affected agents, time series.
- **Query**: `days` (1-365, default 30)

### `GET /analytics/cost`
Cost breakdown by framework and daily trends.
- **Query**: `days`

### `GET /analytics/quality`
Quality assessment stats: score distribution, grades, trends.
- **Query**: `days`

---

## Feedback

Prefix: `/tenants/{tenant_id}/feedback`

### `POST /feedback`
Submit feedback on detection accuracy.
- **Body**: `{ "detection_id": "string", "feedback_type": "true_positive|false_positive|true_negative|false_negative", "comment": "optional" }`
- **Response**: `201`

### `GET /feedback/stats`
Aggregated feedback statistics (precision, recall, F1 per detection type).

### `GET /feedback/recommendations`
Threshold adjustment recommendations based on accumulated feedback.

### `GET /feedback`
List feedback submissions with pagination.

---

## Healing

Prefix: `/tenants/{tenant_id}/healing`

### `GET /healing/operations`
List self-healing operations.
- **Query**: `status`, `fix_type`, `page`, `page_size`

### `GET /healing/operations/{operation_id}`
Get operation details including fix plan and rollback info.

### `POST /healing/operations/{operation_id}/execute`
Execute a healing operation.

### `POST /healing/operations/{operation_id}/approve`
Approve an operation for execution (for manual approval policies).

### `POST /healing/operations/{operation_id}/rollback`
Rollback a previously applied fix.

### `GET /healing/history`
History of all applied fixes.

---

## Settings

Prefix: `/tenants/{tenant_id}/settings`

### `GET /settings/thresholds`
Get current detection threshold settings.

### `PUT /settings/thresholds`
Update detection thresholds.
- **Body**: `{ "structural_threshold": 0.95, "semantic_threshold": 0.85, "loop_detection_window": 7, ... }`

### `DELETE /settings/thresholds`
Reset thresholds to defaults. Optional `framework` query param for per-framework reset.

### `GET /settings/thresholds/defaults`
Get default thresholds (public, no auth required).

### `GET /settings/thresholds/preview`
Preview effective thresholds with proposed changes applied.

---

## Workflow Groups

Prefix: `/tenants/{tenant_id}/workflow-groups`

### `POST /workflow-groups`
Create a workflow group with auto-detection rules.

### `GET /workflow-groups`
List workflow groups.

### `GET /workflow-groups/{group_id}`
Get group details.

### `PUT /workflow-groups/{group_id}`
Update group settings.

### `DELETE /workflow-groups/{group_id}`
Delete a group.

### `POST /workflow-groups/{group_id}/workflows`
Assign workflows to a group.

### `POST /workflow-groups/{group_id}/auto-detect`
Auto-assign workflows by matching rules (name pattern, source, complexity, grade).

---

## n8n Integration

Prefix: `/n8n`

### `POST /n8n/webhook`
Receive n8n execution webhook. Requires `X-MAO-API-Key` header.
- **Verification headers**: `X-MAO-Signature`, `X-MAO-Timestamp`, `X-MAO-Nonce`

### `POST /n8n/workflows`
Register an n8n workflow for monitoring.

### `GET /n8n/workflows`
List registered n8n workflows.

### `POST /n8n/sync`
Pull historical executions from n8n cloud.

### `GET /n8n/sync/status`
Get n8n sync configuration status.

### `POST /n8n/discover`
Discover workflows from a connected n8n instance.

### `GET /n8n/stream`
SSE endpoint for real-time execution updates.

---

## Dify Integration

Prefix: `/dify`

### `POST /dify/webhook`
Receive Dify workflow execution webhook.

### `POST /dify/instances` / `GET /dify/instances`
Register and list Dify instance connections.

### `POST /dify/apps` / `GET /dify/apps`
Register and list Dify apps for monitoring.

### `GET /dify/stream`
SSE endpoint for real-time execution updates.

---

## LangGraph Integration

Prefix: `/langgraph`

### `POST /langgraph/webhook`
Receive LangGraph deployment webhook.

### `POST /langgraph/deployments` / `GET /langgraph/deployments`
Register and list LangGraph deployments.

### `POST /langgraph/assistants` / `GET /langgraph/assistants`
Register and list LangGraph assistants.

### `GET /langgraph/stream`
SSE endpoint for real-time execution updates.

---

## OpenClaw Integration

Prefix: `/openclaw`

### `POST /openclaw/webhook`
Receive OpenClaw agent session webhook.

### `POST /openclaw/instances` / `GET /openclaw/instances`
Register and list OpenClaw instances.

### `POST /openclaw/agents` / `GET /openclaw/agents`
Register and list OpenClaw agents.

### `GET /openclaw/stream`
SSE endpoint for real-time execution updates.

---

## Claude Code Integration

### `POST /traces/claude-code/ingest`
Ingest traces from Claude Code CLI sessions.
- **Body**: `{ "timestamp", "tool_name", "hook_type", "session_id", "tool_input", "tool_output", "working_dir", "trace_type", "model", "tokens_in", "tokens_out", "cost_usd" }`

---

## Security

Prefix: `/security`

### `POST /security/injection/check`
Check text for prompt injection attempts.
- **Body**: `{ "text": "string" }`

### `POST /security/hallucination/check`
Check output against sources for hallucination.
- **Body**: `{ "output": "string", "sources": ["string"] }`

### `POST /security/overflow/check`
Check for context window overflow risk.
- **Body**: `{ "text": "string", "model": "string" }`

### `POST /security/cost/calculate`
Calculate token cost for a given model.
- **Body**: `{ "text": "string", "model": "string" }`

### `GET /security/models`
List supported models with token pricing.

---

## Import Jobs

Prefix: `/import-jobs`

### `POST /import-jobs`
Upload JSON/JSONL file for background processing (max 100MB).
- **Response**: `202`

### `GET /import-jobs`
List import jobs with pagination.

### `GET /import-jobs/{import_job_id}`
Get import job status.

### `GET /import-jobs/{import_job_id}/results`
Get import results and error details.

### `DELETE /import-jobs/{import_job_id}`
Delete an import job. **Response**: `204`

---

## Metrics

### `GET /metrics`
Prometheus-format metrics export (`text/plain`).

### `GET /metrics/json`
JSON metrics export.

### `POST /metrics/datadog/flush`
Flush metrics to Datadog.

### `GET /metrics/datadog/dashboard`
Get Datadog dashboard configuration JSON.

---

## Billing

### `GET /billing/plans`
List available pricing plans (public).

### `POST /billing/checkout`
Create a Stripe Checkout session.

### `GET /billing/portal`
Get Stripe Customer Portal URL.

### `GET /billing/status`
Get current billing status.

### `POST /billing/webhooks/stripe`
Handle Stripe webhook events. Requires `stripe-signature` header.

---

## Webhooks

### `POST /webhooks/clerk`
Handle Clerk user/org lifecycle events. Verified via Svix signature.

---

## Benchmarks

### `GET /benchmarks`
Get detection accuracy benchmarks for MAST failure taxonomy (public).
- **Response**: 16 failure modes (F1-F16) with detection rates and tier levels.

---

## Diagnostics

### `GET /diagnostics/detector-status`
Get detector health and readiness status.
- **Response**: Per-detector F1, precision, recall, sample count, tier (production/beta/experimental).

---

## Rate Limiting

- **Global**: 1000 requests per 60 seconds per IP
- **Auth endpoints**: 10 requests per 60 seconds per IP
- **Exempt**: `/health`, `/api/v1/health`, `/`, `OPTIONS`

## CORS

- Allowed methods: `GET`, `POST`, `PUT`, `DELETE`, `OPTIONS`
- Allowed headers: `Authorization`, `Content-Type`, `Accept`, `X-MAO-API-Key`, `X-MAO-Signature`, `X-MAO-Timestamp`, `X-MAO-Nonce`
- Credentials: enabled
- Max age: 3600s

## Authentication Methods

| Method | Usage |
|--------|-------|
| API Key + Token Exchange | SDK and CLI integrations |
| Clerk OAuth | Dashboard users |
| JWT Bearer | Programmatic access (from `/auth/token`) |
| Webhook Signatures | Clerk, Stripe, n8n verification |
