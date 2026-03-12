import Link from 'next/link'
import { Terminal, Copy, AlertTriangle, Check } from 'lucide-react'

export default function WebhooksPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-4">Webhooks</h1>
        <p className="text-lg text-zinc-300">
          Receive real-time notifications when detections occur in your multi-agent systems.
          Configure webhooks to integrate with Slack, PagerDuty, or custom endpoints.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Overview</h2>
        <p className="text-zinc-300 mb-4">
          Pisama sends HTTP POST requests to your configured endpoints when events occur:
        </p>

        <div className="grid md:grid-cols-2 gap-4">
          <EventCard
            title="detection.created"
            description="A new failure detection was created (loop, corruption, drift, deadlock)"
          />
          <EventCard
            title="detection.validated"
            description="A detection was marked as validated or false positive"
          />
          <EventCard
            title="trace.completed"
            description="A trace finished (success or error)"
          />
          <EventCard
            title="trace.error"
            description="A trace ended with an error status"
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Webhook Payload</h2>
        <p className="text-zinc-300 mb-4">
          All webhook requests include a JSON payload with event details:
        </p>

        <CodeBlock title="Example Payload: detection.created" language="json">
{`{
  "event": "detection.created",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "detection": {
      "id": "det_abc123",
      "type": "loop",
      "confidence": 95,
      "trace_id": "trace_xyz789",
      "details": {
        "loop_count": 15,
        "pattern": "hash_collision",
        "agents": ["researcher", "writer"]
      }
    },
    "trace": {
      "id": "trace_xyz789",
      "session_id": "session_001",
      "framework": "langgraph",
      "status": "running"
    }
  }
}`}
        </CodeBlock>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Request Headers</h2>
        <p className="text-zinc-300 mb-4">
          Each webhook request includes these headers:
        </p>

        <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-zinc-800/50 border-b border-zinc-700">
              <tr>
                <th className="px-4 py-3 text-left text-zinc-300 font-medium">Header</th>
                <th className="px-4 py-3 text-left text-zinc-300 font-medium">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-700">
              <tr>
                <td className="px-4 py-3"><code className="text-blue-400">Content-Type</code></td>
                <td className="px-4 py-3 text-zinc-400">application/json</td>
              </tr>
              <tr>
                <td className="px-4 py-3"><code className="text-blue-400">X-MAO-Signature</code></td>
                <td className="px-4 py-3 text-zinc-400">HMAC-SHA256 signature for verification</td>
              </tr>
              <tr>
                <td className="px-4 py-3"><code className="text-blue-400">X-MAO-Timestamp</code></td>
                <td className="px-4 py-3 text-zinc-400">Unix timestamp when request was sent</td>
              </tr>
              <tr>
                <td className="px-4 py-3"><code className="text-blue-400">X-MAO-Event</code></td>
                <td className="px-4 py-3 text-zinc-400">Event type (detection.created, etc.)</td>
              </tr>
              <tr>
                <td className="px-4 py-3"><code className="text-blue-400">X-MAO-Delivery-ID</code></td>
                <td className="px-4 py-3 text-zinc-400">Unique ID for this delivery (for deduplication)</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Signature Verification</h2>
        <p className="text-zinc-300 mb-4">
          Always verify the webhook signature to ensure requests are from Pisama:
        </p>

        <CodeBlock title="Python Verification" language="python">
{`import hmac
import hashlib
import time

def verify_webhook(request, secret: str) -> bool:
    signature = request.headers.get('X-MAO-Signature')
    timestamp = request.headers.get('X-MAO-Timestamp')
    body = request.body
    
    # Check timestamp freshness (5 minute window)
    if abs(time.time() - int(timestamp)) > 300:
        return False
    
    # Compute expected signature
    message = f"{timestamp}.{body.decode()}"
    expected = "sha256=" + hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)`}
        </CodeBlock>

        <div className="mt-4">
          <CodeBlock title="Node.js Verification" language="javascript">
{`const crypto = require('crypto');

function verifyWebhook(req, secret) {
  const signature = req.headers['x-mao-signature'];
  const timestamp = req.headers['x-mao-timestamp'];
  const body = JSON.stringify(req.body);
  
  // Check timestamp freshness
  if (Math.abs(Date.now() / 1000 - parseInt(timestamp)) > 300) {
    return false;
  }
  
  // Compute expected signature
  const message = \`\${timestamp}.\${body}\`;
  const expected = 'sha256=' + crypto
    .createHmac('sha256', secret)
    .update(message)
    .digest('hex');
  
  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expected)
  );
}`}
          </CodeBlock>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Configuring Webhooks</h2>

        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-semibold text-white mb-3">Via Dashboard</h3>
            <ol className="space-y-2">
              <li className="flex items-start gap-2 text-zinc-300">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600/30 text-blue-400 text-xs flex items-center justify-center font-medium">1</span>
                Go to Settings → Webhooks
              </li>
              <li className="flex items-start gap-2 text-zinc-300">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600/30 text-blue-400 text-xs flex items-center justify-center font-medium">2</span>
                Click &quot;Add Webhook&quot;
              </li>
              <li className="flex items-start gap-2 text-zinc-300">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600/30 text-blue-400 text-xs flex items-center justify-center font-medium">3</span>
                Enter your endpoint URL and select events to subscribe to
              </li>
              <li className="flex items-start gap-2 text-zinc-300">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600/30 text-blue-400 text-xs flex items-center justify-center font-medium">4</span>
                Copy the signing secret and store it securely
              </li>
            </ol>
          </div>

          <div>
            <h3 className="text-lg font-semibold text-white mb-3">Via API</h3>
            <CodeBlock title="Create Webhook" language="bash">
{`curl -X POST https://api.mao-testing.com/api/v1/webhooks \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://your-server.com/webhooks/mao",
    "events": ["detection.created", "trace.error"],
    "description": "Production alerts"
  }'`}
            </CodeBlock>
          </div>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Integration Examples</h2>

        <div className="space-y-6">
          <IntegrationExample
            name="Slack"
            description="Send detection alerts to a Slack channel"
            code={`# Use Slack incoming webhook
curl -X POST https://hooks.slack.com/services/T00/B00/XXX \\
  -H "Content-Type: application/json" \\
  -d '{
    "text": "🚨 *New Detection*",
    "attachments": [{
      "color": "danger",
      "fields": [
        {"title": "Type", "value": "Loop", "short": true},
        {"title": "Confidence", "value": "95%", "short": true},
        {"title": "Trace", "value": "<https://app.mao-testing.com/traces/xyz|View Trace>"}
      ]
    }]
  }'`}
          />

          <IntegrationExample
            name="PagerDuty"
            description="Create incidents for high-confidence detections"
            code={`import requests

def handle_webhook(payload):
    if payload['data']['detection']['confidence'] >= 90:
        requests.post(
            'https://events.pagerduty.com/v2/enqueue',
            json={
                'routing_key': 'YOUR_ROUTING_KEY',
                'event_action': 'trigger',
                'payload': {
                    'summary': f"MAO Detection: {payload['data']['detection']['type']}",
                    'severity': 'critical',
                    'source': 'mao-testing',
                    'custom_details': payload['data']
                }
            }
        )`}
          />

          <IntegrationExample
            name="Discord"
            description="Post alerts to a Discord channel"
            code={`import requests

def handle_webhook(payload):
    detection = payload['data']['detection']
    requests.post(
        'https://discord.com/api/webhooks/YOUR_WEBHOOK',
        json={
            'embeds': [{
                'title': f"🔴 Detection: {detection['type']}",
                'color': 0xFF0000,
                'fields': [
                    {'name': 'Confidence', 'value': f"{detection['confidence']}%", 'inline': True},
                    {'name': 'Trace ID', 'value': detection['trace_id'], 'inline': True}
                ]
            }]
        }
    )`}
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Retry Policy</h2>
        <p className="text-zinc-300 mb-4">
          If your endpoint returns a non-2xx status code, we&apos;ll retry the delivery:
        </p>

        <div className="rounded-lg bg-zinc-800/50 border border-zinc-700 p-4">
          <ul className="space-y-2 text-zinc-300">
            <li className="flex items-center gap-2">
              <Check size={16} className="text-blue-400" />
              <strong>Attempt 1:</strong> Immediate
            </li>
            <li className="flex items-center gap-2">
              <Check size={16} className="text-blue-400" />
              <strong>Attempt 2:</strong> After 1 minute
            </li>
            <li className="flex items-center gap-2">
              <Check size={16} className="text-blue-400" />
              <strong>Attempt 3:</strong> After 5 minutes
            </li>
            <li className="flex items-center gap-2">
              <Check size={16} className="text-blue-400" />
              <strong>Attempt 4:</strong> After 30 minutes
            </li>
            <li className="flex items-center gap-2">
              <Check size={16} className="text-blue-400" />
              <strong>Attempt 5:</strong> After 2 hours (final)
            </li>
          </ul>
        </div>

        <div className="mt-4 p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
          <div className="flex gap-2">
            <AlertTriangle size={18} className="text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-amber-200 font-medium">Timeout</p>
              <p className="text-amber-200/80 text-sm">
                Your endpoint must respond within 10 seconds. Longer responses are treated as failures.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-zinc-800/50 rounded-xl border border-zinc-700 p-6">
        <h2 className="text-lg font-bold text-white mb-4">Related</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <Link
            href="/docs/api-reference"
            className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-700 hover:border-blue-500/50 transition-colors"
          >
            <h3 className="font-medium text-white">API Reference</h3>
            <p className="text-sm text-zinc-400">Webhook management endpoints</p>
          </Link>
          <Link
            href="/docs/detections"
            className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-700 hover:border-blue-500/50 transition-colors"
          >
            <h3 className="font-medium text-white">Detections</h3>
            <p className="text-sm text-zinc-400">Understanding detection types and data</p>
          </Link>
        </div>
      </section>
    </div>
  )
}

function CodeBlock({ title, language: _language, children }: { title: string; language: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-700 bg-zinc-800/50">
        <div className="flex items-center gap-2">
          <Terminal size={14} className="text-zinc-400" />
          <span className="text-sm text-zinc-400">{title}</span>
        </div>
        <button className="p-1 text-zinc-400 hover:text-white transition-colors" aria-label="Copy code">
          <Copy size={14} />
        </button>
      </div>
      <pre className="p-4 text-sm text-zinc-300 overflow-x-auto">
        <code>{children}</code>
      </pre>
    </div>
  )
}

function EventCard({ title, description }: { title: string; description: string }) {
  return (
    <div className="p-4 rounded-lg bg-zinc-800/50 border border-zinc-700">
      <code className="text-blue-400 text-sm">{title}</code>
      <p className="text-sm text-zinc-400 mt-1">{description}</p>
    </div>
  )
}

function IntegrationExample({ name, description, code }: { name: string; description: string; code: string }) {
  return (
    <div className="rounded-lg bg-zinc-800/30 border border-zinc-700 p-4">
      <h4 className="font-semibold text-white mb-1">{name}</h4>
      <p className="text-sm text-zinc-400 mb-3">{description}</p>
      <CodeBlock title={`${name} Example`} language="bash">
        {code}
      </CodeBlock>
    </div>
  )
}
