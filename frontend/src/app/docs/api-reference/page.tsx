import { 
  Terminal, 
  Copy,
  Check,
  ArrowRight,
  Code,
} from 'lucide-react'

export default function ApiReferencePage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-4">API Reference</h1>
        <p className="text-lg text-slate-300">
          Complete reference for the MAO Testing REST API and SDK methods.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Authentication</h2>
        <p className="text-slate-300 mb-4">
          All API requests require authentication via Bearer token:
        </p>

        <CodeBlock title="Authentication Header">
{`Authorization: Bearer your_api_key_here`}
        </CodeBlock>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Base URL</h2>
        <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
          <code className="text-primary-400">https://api.mao-testing.com/v1</code>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Endpoints</h2>
        
        <div className="space-y-6">
          <ApiEndpoint
            method="GET"
            path="/traces"
            description="List all traces with optional filtering"
            params={[
              { name: 'limit', type: 'number', description: 'Max results (default: 50, max: 100)' },
              { name: 'offset', type: 'number', description: 'Pagination offset' },
              { name: 'status', type: 'string', description: 'Filter by status: running, completed, failed' },
              { name: 'framework', type: 'string', description: 'Filter by framework: langgraph, autogen, crewai' },
              { name: 'from', type: 'string', description: 'Start time (ISO 8601)' },
              { name: 'to', type: 'string', description: 'End time (ISO 8601)' },
            ]}
            response={`{
  "traces": [
    {
      "id": "trace_abc123",
      "name": "my-workflow",
      "status": "completed",
      "framework": "langgraph",
      "start_time": "2024-01-15T10:30:00Z",
      "end_time": "2024-01-15T10:30:12Z",
      "duration_ms": 12340,
      "total_tokens": 45230,
      "cost_usd": 0.23,
      "state_count": 24,
      "detection_count": 0
    }
  ],
  "total": 1543,
  "has_more": true
}`}
          />

          <ApiEndpoint
            method="GET"
            path="/traces/:id"
            description="Get detailed trace information including all spans and states"
            params={[
              { name: 'include_states', type: 'boolean', description: 'Include full state snapshots (default: true)' },
              { name: 'include_spans', type: 'boolean', description: 'Include all span details (default: true)' },
            ]}
            response={`{
  "id": "trace_abc123",
  "name": "my-workflow",
  "status": "completed",
  "metadata": {
    "user_id": "user_123",
    "environment": "production"
  },
  "spans": [
    {
      "id": "span_001",
      "name": "researcher_agent",
      "start_time": "2024-01-15T10:30:00Z",
      "end_time": "2024-01-15T10:30:05Z",
      "attributes": {...}
    }
  ],
  "states": [
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "name": "initial",
      "data": {...}
    }
  ]
}`}
          />

          <ApiEndpoint
            method="GET"
            path="/detections"
            description="List failure detections"
            params={[
              { name: 'limit', type: 'number', description: 'Max results (default: 50)' },
              { name: 'type', type: 'string', description: 'Filter by type: infinite_loop, state_corruption, persona_drift, deadlock' },
              { name: 'severity', type: 'string', description: 'Filter by severity: critical, high, medium, low' },
              { name: 'status', type: 'string', description: 'Filter by status: new, acknowledged, resolved, false_positive' },
            ]}
            response={`{
  "detections": [
    {
      "id": "det_xyz789",
      "trace_id": "trace_abc123",
      "type": "infinite_loop",
      "severity": "critical",
      "confidence": 0.95,
      "message": "Detected loop: Agent A → Agent B → Agent A (3 cycles)",
      "detected_at": "2024-01-15T10:30:08Z",
      "status": "new"
    }
  ],
  "total": 42
}`}
          />

          <ApiEndpoint
            method="PATCH"
            path="/detections/:id"
            description="Update detection status (acknowledge, resolve, mark as false positive)"
            params={[
              { name: 'status', type: 'string', description: 'New status: acknowledged, resolved, false_positive', required: true },
              { name: 'notes', type: 'string', description: 'Optional notes about the resolution' },
            ]}
            response={`{
  "id": "det_xyz789",
  "status": "resolved",
  "resolved_at": "2024-01-15T11:00:00Z",
  "notes": "Fixed by updating routing logic"
}`}
          />

          <ApiEndpoint
            method="POST"
            path="/traces"
            description="Create a new trace (typically done via SDK)"
            params={[
              { name: 'name', type: 'string', description: 'Trace name', required: true },
              { name: 'framework', type: 'string', description: 'Framework identifier' },
              { name: 'metadata', type: 'object', description: 'Custom metadata key-value pairs' },
              { name: 'tags', type: 'string[]', description: 'Array of tags' },
            ]}
            response={`{
  "id": "trace_new456",
  "name": "my-workflow",
  "status": "running",
  "created_at": "2024-01-15T12:00:00Z"
}`}
          />

          <ApiEndpoint
            method="GET"
            path="/analytics/summary"
            description="Get aggregated analytics for a time period"
            params={[
              { name: 'from', type: 'string', description: 'Start time (ISO 8601)', required: true },
              { name: 'to', type: 'string', description: 'End time (ISO 8601)', required: true },
              { name: 'group_by', type: 'string', description: 'Group by: hour, day, week' },
            ]}
            response={`{
  "period": {
    "from": "2024-01-01T00:00:00Z",
    "to": "2024-01-15T00:00:00Z"
  },
  "totals": {
    "traces": 15432,
    "detections": 89,
    "tokens": 45000000,
    "cost_usd": 234.56
  },
  "by_framework": {
    "langgraph": 8543,
    "autogen": 4321,
    "crewai": 2568
  },
  "by_detection_type": {
    "infinite_loop": 45,
    "state_corruption": 23,
    "persona_drift": 15,
    "deadlock": 6
  }
}`}
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">SDK Reference</h2>
        
        <div className="space-y-4">
          <SdkMethod
            name="MAOTracer()"
            description="Initialize the tracer with configuration options"
            params={[
              'api_key: str - API key (or use MAO_API_KEY env var)',
              'endpoint: str - API endpoint URL',
              'environment: str - Environment name for tagging',
              'service_name: str - Service identifier',
              'sample_rate: float - Trace sampling rate (0.0-1.0)',
            ]}
          />

          <SdkMethod
            name="tracer.trace(name: str)"
            description="Start a new trace session (context manager)"
            params={[
              'name: str - Trace name for identification',
              'Returns: TraceSession context manager',
            ]}
          />

          <SdkMethod
            name="session.span(name: str)"
            description="Create a child span within the trace (context manager)"
            params={[
              'name: str - Span name',
              'Returns: Span context manager',
            ]}
          />

          <SdkMethod
            name="session.capture_state(name: str, data: dict)"
            description="Capture a state snapshot at the current point"
            params={[
              'name: str - State identifier',
              'data: dict - State data to capture',
            ]}
          />

          <SdkMethod
            name="session.set_metadata(metadata: dict)"
            description="Set metadata key-value pairs on the trace"
            params={[
              'metadata: dict - Key-value pairs',
            ]}
          />

          <SdkMethod
            name="session.add_tag(tag: str)"
            description="Add a tag to the trace for filtering"
            params={[
              'tag: str - Tag name',
            ]}
          />

          <SdkMethod
            name="span.set_attribute(key: str, value: any)"
            description="Set an attribute on the current span"
            params={[
              'key: str - Attribute name',
              'value: any - Attribute value (string, number, boolean)',
            ]}
          />

          <SdkMethod
            name="span.set_status(status: str, message: str)"
            description="Set the span status"
            params={[
              'status: str - "ok" or "error"',
              'message: str - Optional status message',
            ]}
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Error Codes</h2>
        
        <div className="space-y-2">
          <ErrorCode code={400} message="Bad Request" description="Invalid parameters or malformed request" />
          <ErrorCode code={401} message="Unauthorized" description="Missing or invalid API key" />
          <ErrorCode code={403} message="Forbidden" description="API key lacks required permissions" />
          <ErrorCode code={404} message="Not Found" description="Requested resource does not exist" />
          <ErrorCode code={429} message="Too Many Requests" description="Rate limit exceeded (see X-RateLimit-* headers)" />
          <ErrorCode code={500} message="Internal Server Error" description="Server error, please retry" />
        </div>
      </section>

      <section className="bg-slate-800/50 rounded-xl border border-slate-700 p-6">
        <h3 className="font-semibold text-white mb-2">Rate Limits</h3>
        <p className="text-sm text-slate-300 mb-4">
          API rate limits vary by plan. Current limits are returned in response headers:
        </p>
        <div className="space-y-1 text-sm">
          <div className="flex gap-4">
            <code className="text-primary-400 w-48">X-RateLimit-Limit</code>
            <span className="text-slate-400">Requests allowed per minute</span>
          </div>
          <div className="flex gap-4">
            <code className="text-primary-400 w-48">X-RateLimit-Remaining</code>
            <span className="text-slate-400">Requests remaining in current window</span>
          </div>
          <div className="flex gap-4">
            <code className="text-primary-400 w-48">X-RateLimit-Reset</code>
            <span className="text-slate-400">Unix timestamp when limit resets</span>
          </div>
        </div>
      </section>
    </div>
  )
}

function CodeBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-slate-900 border border-slate-700 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700 bg-slate-800/50">
        <span className="text-sm text-slate-400">{title}</span>
        <button className="p-1 text-slate-400 hover:text-white transition-colors">
          <Copy size={14} />
        </button>
      </div>
      <pre className="p-4 text-sm text-slate-300 overflow-x-auto">
        <code>{children}</code>
      </pre>
    </div>
  )
}

function ApiEndpoint({
  method,
  path,
  description,
  params,
  response,
}: {
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  path: string
  description: string
  params: { name: string; type: string; description: string; required?: boolean }[]
  response: string
}) {
  const methodColors = {
    GET: 'bg-emerald-500/20 text-emerald-400',
    POST: 'bg-blue-500/20 text-blue-400',
    PATCH: 'bg-amber-500/20 text-amber-400',
    DELETE: 'bg-red-500/20 text-red-400',
  }

  return (
    <div className="rounded-xl border border-slate-700 overflow-hidden">
      <div className="p-4 bg-slate-800/50 border-b border-slate-700">
        <div className="flex items-center gap-3 mb-2">
          <span className={`px-2 py-1 rounded text-xs font-bold ${methodColors[method]}`}>
            {method}
          </span>
          <code className="text-white">{path}</code>
        </div>
        <p className="text-sm text-slate-400">{description}</p>
      </div>
      
      <div className="p-4 border-b border-slate-700">
        <h4 className="text-sm font-medium text-slate-400 mb-2">Parameters</h4>
        <div className="space-y-2">
          {params.map((param) => (
            <div key={param.name} className="flex items-start gap-2 text-sm">
              <code className="text-primary-400">{param.name}</code>
              <span className="text-slate-500">({param.type})</span>
              {param.required && <span className="text-red-400 text-xs">required</span>}
              <span className="text-slate-400">- {param.description}</span>
            </div>
          ))}
        </div>
      </div>
      
      <div className="p-4 bg-slate-900">
        <h4 className="text-sm font-medium text-slate-400 mb-2">Response</h4>
        <pre className="text-xs text-slate-300 overflow-x-auto">
          <code>{response}</code>
        </pre>
      </div>
    </div>
  )
}

function SdkMethod({
  name,
  description,
  params,
}: {
  name: string
  description: string
  params: string[]
}) {
  return (
    <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
      <code className="text-primary-400 font-medium">{name}</code>
      <p className="text-sm text-slate-400 mt-1 mb-2">{description}</p>
      <div className="space-y-1">
        {params.map((param, i) => (
          <div key={i} className="text-xs text-slate-500 pl-4 border-l-2 border-slate-700">
            {param}
          </div>
        ))}
      </div>
    </div>
  )
}

function ErrorCode({
  code,
  message,
  description,
}: {
  code: number
  message: string
  description: string
}) {
  return (
    <div className="flex items-center gap-4 p-3 rounded-lg bg-slate-800/50">
      <span className="font-mono text-red-400 w-12">{code}</span>
      <span className="font-medium text-white w-40">{message}</span>
      <span className="text-sm text-slate-400">{description}</span>
    </div>
  )
}
