'use client'

import { AlertTriangle, MessageCircle, Shield, Users, Zap } from 'lucide-react'
import { CodeBlock, FeatureCard, MethodCard, SetupStep, DetectionTable, DataMappingTable, SecurityNote, RelatedDocs } from '@/components/docs/SharedDocComponents'

export default function OpenClawDocsPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-4">OpenClaw Integration</h1>
        <p className="text-lg text-slate-300">
          Monitor multi-channel AI agents deployed via OpenClaw. Track sessions across
          WhatsApp, Telegram, Slack, and more with real-time failure detection.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Why OpenClaw Integration?</h2>
        <p className="text-slate-300 mb-4">
          OpenClaw agents operate across multiple channels with complex spawning and session patterns:
        </p>
        <div className="grid md:grid-cols-2 gap-4">
          <FeatureCard icon={MessageCircle} title="Multi-Channel Monitoring"
            description="Track agent sessions across WhatsApp, Telegram, Slack, Discord, and web channels" accentColor="text-cyan-400" />
          <FeatureCard icon={Users} title="Spawn Chain Tracking"
            description="Detect unbounded agent spawning that can cause resource exhaustion" accentColor="text-cyan-400" />
          <FeatureCard icon={Shield} title="Sandbox Enforcement"
            description="Verify agents stay within their sandbox boundaries and permission scopes" accentColor="text-cyan-400" />
          <FeatureCard icon={Zap} title="Real-Time Risk Assessment"
            description="Monitor elevated privilege usage and flag unauthorized escalations" accentColor="text-cyan-400" />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Supported Channels</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {['WhatsApp', 'Telegram', 'Slack', 'Discord', 'Web'].map((channel) => (
            <div key={channel} className="p-3 rounded-lg bg-slate-800/50 border border-slate-700 text-center">
              <div className="font-medium text-white">{channel}</div>
              <code className="text-xs text-slate-400">{channel.toLowerCase()}</code>
            </div>
          ))}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Integration Methods</h2>
        <div className="space-y-6">
          <MethodCard
            title="Method 1: Webhook (Recommended)"
            description="Configure your OpenClaw gateway to send session events to Pisama via webhook."
            pros={['Real-time detection', 'Works with all channels', 'Captures full session history']}
            cons={['Requires gateway configuration']}
          >
            <h4 className="text-sm font-semibold text-slate-400 mb-2 mt-4">Setup Steps</h4>
            <ol className="space-y-3">
              <SetupStep number={1} accentColor="bg-cyan-600">
                <strong>Register your OpenClaw instance</strong> in Pisama:
                <CodeBlock title="Register Instance" language="bash">
{`curl -X POST https://api.mao-testing.com/api/v1/openclaw/instances \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"name": "Production Gateway", "gateway_url": "https://gateway.openclaw.io", "api_key": "oc_xxx"}'`}
                </CodeBlock>
              </SetupStep>
              <SetupStep number={2} accentColor="bg-cyan-600">
                <strong>Register agents</strong> to monitor:
                <CodeBlock title="Register Agent" language="bash">
{`curl -X POST https://api.mao-testing.com/api/v1/openclaw/agents \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"instance_id": "INSTANCE_ID", "agent_key": "support-agent", "agent_name": "Customer Support"}'`}
                </CodeBlock>
              </SetupStep>
              <SetupStep number={3} accentColor="bg-cyan-600">
                <strong>Configure the webhook</strong> in your OpenClaw gateway config:
                <CodeBlock title="Gateway Config (YAML)" language="yaml">
{`callbacks:
  pisama:
    url: https://api.mao-testing.com/api/v1/openclaw/webhook
    headers:
      X-MAO-API-Key: your_api_key
    events:
      - session.completed
      - session.error`}
                </CodeBlock>
              </SetupStep>
            </ol>
          </MethodCard>

          <MethodCard
            title="Method 2: OTEL Export"
            description="OpenClaw supports native OpenTelemetry trace export. Configure it to send to Pisama's OTEL collector."
            pros={['Standard OTEL format', 'Integrates with existing observability']}
            cons={['Less framework-specific context', 'Requires OTEL collector setup']}
          >
            <CodeBlock title="Gateway OTEL Config" language="yaml">
{`otel:
  enabled: true
  endpoint: https://api.mao-testing.com/v1/traces
  headers:
    Authorization: Bearer YOUR_TOKEN
  service_name: openclaw-gateway`}
            </CodeBlock>
          </MethodCard>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Multi-Agent Monitoring</h2>
        <p className="text-slate-300 mb-4">
          OpenClaw supports agent spawning where one agent can create child agents. Pisama tracks the full spawn tree:
        </p>
        <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
          <div className="space-y-2 text-sm font-mono text-slate-300">
            <div className="flex items-center gap-2">
              <span className="text-cyan-400">root-agent</span>
              <span className="text-slate-500">session-001</span>
            </div>
            <div className="flex items-center gap-2 ml-6">
              <span className="text-slate-500">|--</span>
              <span className="text-cyan-400">research-agent</span>
              <span className="text-slate-500">session-002</span>
              <span className="text-emerald-400 text-xs">(spawned)</span>
            </div>
            <div className="flex items-center gap-2 ml-6">
              <span className="text-slate-500">|--</span>
              <span className="text-cyan-400">writer-agent</span>
              <span className="text-slate-500">session-003</span>
              <span className="text-emerald-400 text-xs">(spawned)</span>
            </div>
          </div>
          <p className="text-sm text-slate-400 mt-4">
            Pisama detects when spawn chains grow unbounded or when spawned agents exceed their permission scope.
          </p>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Webhook Security</h2>
        <p className="text-slate-300 mb-4">
          Enable HMAC signature verification for production:
        </p>
        <CodeBlock title="Signed Webhook Headers" language="text">
{`X-MAO-API-Key: your_api_key
X-MAO-Timestamp: 1709251200
X-MAO-Nonce: unique-request-id
X-MAO-Signature: sha256=<hmac-of-timestamp.body>`}
        </CodeBlock>
        <SecurityNote>
          Store your webhook secret securely. OpenClaw gateway supports environment variable references in config.
        </SecurityNote>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Detection Capabilities</h2>
        <DetectionTable detections={[
          { name: 'Session Loop', description: 'Session stuck in repetitive request-response cycle', trigger: 'Repeated event patterns within session' },
          { name: 'Tool Abuse', description: 'Agent making excessive or unauthorized tool calls', trigger: 'Tool call rate exceeds threshold' },
          { name: 'Elevated Risk', description: 'Agent operating in elevated privilege mode without approval', trigger: 'Elevated mode flag without authorization record' },
          { name: 'Spawn Chain', description: 'Unbounded agent spawning creating resource exhaustion', trigger: 'Spawn depth or count exceeds limit' },
          { name: 'Channel Mismatch', description: 'Response format inappropriate for delivery channel', trigger: 'Rich content sent to text-only channel' },
          { name: 'Sandbox Escape', description: 'Agent attempting operations outside sandbox boundaries', trigger: 'Disallowed operation pattern detected' },
        ]} />
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Data Mapping</h2>
        <p className="text-slate-300 mb-4">
          OpenClaw session data is mapped to Pisama traces as follows:
        </p>
        <DataMappingTable sourceLabel="OpenClaw" mappings={[
          { source: 'session_id', target: 'trace.session_id' },
          { source: 'instance_id', target: 'trace.metadata.instance_id' },
          { source: 'agent_name', target: 'state.agent_id' },
          { source: 'channel', target: 'trace.metadata.channel' },
          { source: 'events[].type', target: 'state.state_delta.event_type' },
          { source: 'events[].data', target: 'state.state_delta (redacted)' },
          { source: 'message_count', target: 'trace.metadata.message_count' },
        ]} />
      </section>

      <RelatedDocs links={[
        { href: '/docs/sdk', title: 'Python SDK', description: 'OpenClawTracer class reference' },
        { href: '/docs/api-reference', title: 'API Reference', description: 'Webhook endpoint documentation' },
        { href: '/docs/webhooks', title: 'Webhooks', description: 'Webhook security and configuration' },
        { href: '/docs/detections', title: 'Detections', description: 'All detection types explained' },
      ]} />
    </div>
  )
}
