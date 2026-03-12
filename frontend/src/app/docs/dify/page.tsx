'use client'

import { AlertTriangle, Database, RefreshCw, Shield } from 'lucide-react'
import { CodeBlock, FeatureCard, MethodCard, SetupStep, DetectionTable, DataMappingTable, SecurityNote, RelatedDocs } from '@/components/docs/SharedDocComponents'

export default function DifyDocsPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-4">Dify Integration</h1>
        <p className="text-lg text-zinc-300">
          Monitor AI workflows, chatbots, and agents built in Dify. Detect RAG poisoning,
          iteration escapes, model fallbacks, and more.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Why Dify Integration?</h2>
        <p className="text-zinc-300 mb-4">
          Dify applications can exhibit complex failure patterns across workflows, RAG pipelines, and agent loops:
        </p>
        <div className="grid md:grid-cols-2 gap-4">
          <FeatureCard icon={Database} title="RAG Pipeline Monitoring"
            description="Detect poisoned or irrelevant documents injected into RAG retrieval context" accentColor="text-violet-400" />
          <FeatureCard icon={RefreshCw} title="Iteration Tracking"
            description="Detect workflow iteration nodes that exceed their configured loop limits" accentColor="text-violet-400" />
          <FeatureCard icon={AlertTriangle} title="Model Fallback Detection"
            description="Know when your primary model fails and a fallback model is used silently" accentColor="text-violet-400" />
          <FeatureCard icon={Shield} title="Variable Leak Prevention"
            description="Detect sensitive workflow variables exposed in agent output" accentColor="text-violet-400" />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Supported App Types</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {['Chatbot', 'Agent', 'Workflow', 'Chatflow'].map((type) => (
            <div key={type} className="p-3 rounded-lg bg-zinc-800/50 border border-zinc-700 text-center">
              <div className="font-medium text-white">{type}</div>
              <code className="text-xs text-zinc-400">{type.toLowerCase()}</code>
            </div>
          ))}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Integration Methods</h2>
        <div className="space-y-6">
          <MethodCard
            title="Method 1: Webhook (Recommended)"
            description="Configure Dify to send workflow run data to Pisama via webhook after each execution."
            pros={['Real-time detection', 'Works with Dify Cloud and self-hosted', 'No SDK needed']}
            cons={['Requires Dify webhook configuration']}
          >
            <h4 className="text-sm font-semibold text-zinc-400 mb-2 mt-4">Setup Steps</h4>
            <ol className="space-y-3">
              <SetupStep number={1} accentColor="bg-violet-600">
                <strong>Register your Dify instance</strong> in Pisama dashboard or via API:
                <CodeBlock title="Register Instance" language="bash">
{`curl -X POST https://api.mao-testing.com/api/v1/dify/instances \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"name": "Production Dify", "base_url": "https://api.dify.ai/v1", "api_key": "app-xxx"}'`}
                </CodeBlock>
              </SetupStep>
              <SetupStep number={2} accentColor="bg-violet-600">
                <strong>Register an app</strong> within the instance:
                <CodeBlock title="Register App" language="bash">
{`curl -X POST https://api.mao-testing.com/api/v1/dify/apps \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"instance_id": "INSTANCE_ID", "app_id": "your-dify-app-id", "app_type": "workflow"}'`}
                </CodeBlock>
              </SetupStep>
              <SetupStep number={3} accentColor="bg-violet-600">
                <strong>Configure the webhook</strong> in your Dify app to POST execution data:
                <div className="mt-2 rounded-lg bg-zinc-900 border border-zinc-700 p-4">
                  <div className="grid gap-2 text-sm">
                    <div className="flex">
                      <span className="w-32 text-zinc-400">URL:</span>
                      <code className="text-blue-400">https://api.mao-testing.com/api/v1/dify/webhook</code>
                    </div>
                    <div className="flex">
                      <span className="w-32 text-zinc-400">Headers:</span>
                      <code className="text-zinc-300">X-MAO-API-Key: your_api_key</code>
                    </div>
                  </div>
                </div>
              </SetupStep>
            </ol>
          </MethodCard>

          <MethodCard
            title="Method 2: SDK Integration"
            description="Use the Python SDK to instrument your Dify application directly."
            pros={['Fine-grained control', 'Custom metadata', 'Historical import']}
            cons={['Requires code changes', 'Not real-time for Dify Cloud']}
          >
            <CodeBlock title="Python SDK" language="python">
{`from mao_testing.integrations import DifyTracer

tracer = DifyTracer(
    dify_url="https://api.dify.ai/v1",
    dify_api_key="app-xxx",
)

# Sync recent runs to Pisama
results = await tracer.sync_runs(
    app_id="your-app-id",
    mao_endpoint="https://api.mao-testing.com",
    mao_api_key="your-mao-api-key",
)`}
            </CodeBlock>
          </MethodCard>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Webhook Security</h2>
        <p className="text-zinc-300 mb-4">
          Enable HMAC signature verification for production webhook endpoints:
        </p>
        <CodeBlock title="Signed Webhook Headers" language="text">
{`X-MAO-API-Key: your_api_key
X-MAO-Timestamp: 1709251200
X-MAO-Nonce: unique-request-id
X-MAO-Signature: sha256=<hmac-of-timestamp.body>`}
        </CodeBlock>
        <SecurityNote>
          The webhook secret is generated when you register your app. Store it securely
          and include signature headers for production use.
        </SecurityNote>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Detection Capabilities</h2>
        <DetectionTable detections={[
          { name: 'RAG Poisoning', description: 'Poisoned or irrelevant documents in RAG retrieval context', trigger: 'Retrieval quality score below threshold' },
          { name: 'Iteration Escape', description: 'Workflow iteration node exceeds configured max loops', trigger: 'Iteration count > limit' },
          { name: 'Model Fallback', description: 'Primary model fails, fallback model used silently', trigger: 'Model mismatch between config and execution' },
          { name: 'Variable Leak', description: 'Sensitive workflow variables exposed in output', trigger: 'Variable patterns detected in response' },
          { name: 'Classifier Drift', description: 'Intent classifier accuracy degraded below threshold', trigger: 'Classification confidence below baseline' },
          { name: 'Tool Schema Mismatch', description: 'Tool call parameters do not match expected schema', trigger: 'Schema validation failure on tool input' },
        ]} />
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Data Mapping</h2>
        <p className="text-zinc-300 mb-4">
          Dify execution data is mapped to Pisama traces as follows:
        </p>
        <DataMappingTable sourceLabel="Dify" mappings={[
          { source: 'workflow_run_id', target: 'trace.session_id' },
          { source: 'app_id', target: 'trace.metadata.app_id' },
          { source: 'app_type', target: 'trace.metadata.app_type' },
          { source: 'node.title', target: 'state.agent_id' },
          { source: 'node.elapsed_time', target: 'state.latency_ms' },
          { source: 'node.outputs', target: 'state.state_delta (redacted)' },
          { source: 'total_tokens', target: 'trace.total_tokens' },
        ]} />
      </section>

      <RelatedDocs links={[
        { href: '/docs/sdk', title: 'Python SDK', description: 'DifyTracer class reference' },
        { href: '/docs/api-reference', title: 'API Reference', description: 'Webhook endpoint documentation' },
        { href: '/docs/webhooks', title: 'Webhooks', description: 'Webhook security and configuration' },
        { href: '/docs/detections', title: 'Detections', description: 'All detection types explained' },
      ]} />
    </div>
  )
}
