'use client'

import Link from 'next/link'
import { AlertTriangle, Boxes, Shield, Zap } from 'lucide-react'
import { CodeBlock, FeatureCard, MethodCard, SetupStep } from '@/components/docs/SharedDocComponents'

export default function N8nPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-4">n8n Integration</h1>
        <p className="text-lg text-zinc-300">
          Monitor AI/LLM nodes in your n8n workflows for failures, loops, and errors.
          Detect issues in OpenAI, Anthropic, and LangChain nodes automatically.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Why n8n Integration?</h2>
        <p className="text-zinc-300 mb-4">
          n8n workflows with AI nodes can exhibit the same failure patterns as code-based agents:
        </p>
        
        <div className="grid md:grid-cols-2 gap-4">
          <FeatureCard
            icon={AlertTriangle}
            title="Loop Detection"
            description="Detect when workflows trigger themselves repeatedly or get stuck in retry loops"
          />
          <FeatureCard
            icon={Shield}
            title="AI Error Monitoring"
            description="Track rate limits, token overflows, and malformed responses from LLM nodes"
          />
          <FeatureCard
            icon={Zap}
            title="Performance Tracking"
            description="Monitor execution times and token usage across AI nodes"
          />
          <FeatureCard
            icon={Boxes}
            title="Multi-Node Analysis"
            description="Understand how data flows between AI nodes and detect corruption"
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Supported AI Nodes</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <NodeBadge name="OpenAI" type="n8n-nodes-base.openAi" />
          <NodeBadge name="Anthropic Claude" type="n8n-nodes-base.anthropic" />
          <NodeBadge name="LangChain Agent" type="n8n-nodes-langchain.agent" />
          <NodeBadge name="LangChain LLM" type="n8n-nodes-langchain.chainLlm" />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Integration Methods</h2>

        <div className="space-y-6">
          <MethodCard
            title="Method 1: Webhook (Recommended)"
            description="Add a webhook node to your n8n workflow to send execution data to Pisama in real-time."
            pros={["Real-time detection", "No n8n API access needed", "Works with n8n Cloud"]}
            cons={["Requires modifying workflows"]}
          >
            <h4 className="text-sm font-semibold text-zinc-400 mb-2 mt-4">Setup Steps</h4>
            <ol className="space-y-3">
              <SetupStep number={1}>
                <strong>Register your workflow</strong> in Pisama dashboard or via API:
                <CodeBlock title="Register Workflow" language="bash">
{`curl -X POST https://api.mao-testing.com/api/v1/n8n/workflows \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"workflow_id": "your-n8n-workflow-id", "workflow_name": "My AI Workflow"}'`}
                </CodeBlock>
              </SetupStep>
              
              <SetupStep number={2}>
                <strong>Add an HTTP Request node</strong> at the end of your workflow with these settings:
                <div className="mt-2 rounded-lg bg-zinc-900 border border-zinc-700 p-4">
                  <div className="grid gap-2 text-sm">
                    <div className="flex">
                      <span className="w-32 text-zinc-400">Method:</span>
                      <span className="text-white">POST</span>
                    </div>
                    <div className="flex">
                      <span className="w-32 text-zinc-400">URL:</span>
                      <code className="text-blue-400">https://api.mao-testing.com/api/v1/n8n/webhook</code>
                    </div>
                    <div className="flex">
                      <span className="w-32 text-zinc-400">Headers:</span>
                      <code className="text-zinc-300">X-MAO-API-Key: your_api_key</code>
                    </div>
                  </div>
                </div>
              </SetupStep>

              <SetupStep number={3}>
                <strong>Configure the request body</strong> using this expression:
                <CodeBlock title="Request Body (n8n Expression)" language="json">
{`{
  "executionId": "{{ $execution.id }}",
  "workflowId": "{{ $workflow.id }}",
  "workflowName": "{{ $workflow.name }}",
  "mode": "{{ $execution.mode }}",
  "startedAt": "{{ $execution.startedAt }}",
  "finishedAt": "{{ $now.toISO() }}",
  "status": "success",
  "data": {{ JSON.stringify($execution) }}
}`}
                </CodeBlock>
              </SetupStep>
            </ol>
          </MethodCard>

          <MethodCard
            title="Method 2: API Polling (SDK)"
            description="Use the Python SDK to poll your n8n instance for executions and sync them to Pisama."
            pros={["No workflow changes needed", "Import historical data", "Batch processing"]}
            cons={["Requires n8n API access", "Not real-time"]}
          >
            <CodeBlock title="Python SDK Polling" language="python">
{`from mao_testing.integrations import N8nTracer
from datetime import datetime, timedelta

# Initialize tracer with n8n credentials
tracer = N8nTracer(
    n8n_url="https://your-n8n.example.com",
    n8n_api_key="your-n8n-api-key",
)

# Sync recent executions to MAO
since = datetime.utcnow() - timedelta(hours=1)

results = await tracer.sync_executions(
    since=since,
    workflow_id="optional-specific-workflow",
    mao_endpoint="https://api.mao-testing.com",
    mao_api_key="your-mao-api-key",
)

print(f"Synced {len(results)} executions")`}
            </CodeBlock>
          </MethodCard>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Webhook Security</h2>
        <p className="text-zinc-300 mb-4">
          For production use, enable HMAC signature verification to prevent spoofed webhook calls:
        </p>

        <CodeBlock title="Signed Webhook Request" language="javascript">
{`// In your n8n HTTP Request node, add these headers:
{
  "X-MAO-API-Key": "{{ $env.MAO_API_KEY }}",
  "X-MAO-Timestamp": "{{ Math.floor(Date.now() / 1000) }}",
  "X-MAO-Nonce": "{{ $randomString() }}",
  "X-MAO-Signature": "sha256={{ $hmac('sha256', $env.WEBHOOK_SECRET, timestamp + '.' + body) }}"
}`}
        </CodeBlock>

        <div className="mt-4 p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
          <div className="flex gap-2">
            <AlertTriangle size={18} className="text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-amber-200 font-medium">Security Note</p>
              <p className="text-amber-200/80 text-sm">
                The webhook secret is generated when you register your workflow. Store it securely 
                in n8n environment variables.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Detection Capabilities</h2>
        
        <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-zinc-800/50 border-b border-zinc-700">
              <tr>
                <th className="px-4 py-3 text-left text-zinc-300 font-medium">Detection Type</th>
                <th className="px-4 py-3 text-left text-zinc-300 font-medium">Description</th>
                <th className="px-4 py-3 text-left text-zinc-300 font-medium">Trigger</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-700">
              <tr>
                <td className="px-4 py-3 text-white">Execution Loop</td>
                <td className="px-4 py-3 text-zinc-400">Workflow triggered multiple times rapidly</td>
                <td className="px-4 py-3 text-zinc-400">3+ executions in 60 seconds</td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-white">Rate Limit</td>
                <td className="px-4 py-3 text-zinc-400">AI provider rate limit exceeded</td>
                <td className="px-4 py-3 text-zinc-400">Error message contains &quot;rate limit&quot;</td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-white">Token Overflow</td>
                <td className="px-4 py-3 text-zinc-400">Token limit exceeded on LLM call</td>
                <td className="px-4 py-3 text-zinc-400">Error contains &quot;token&quot; + &quot;limit&quot;</td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-white">Parse Error</td>
                <td className="px-4 py-3 text-zinc-400">LLM output failed JSON/schema validation</td>
                <td className="px-4 py-3 text-zinc-400">Downstream node parse failure</td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-white">Timeout</td>
                <td className="px-4 py-3 text-zinc-400">AI node took too long to respond</td>
                <td className="px-4 py-3 text-zinc-400">Execution time &gt; configured threshold</td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-white">Node Failure</td>
                <td className="px-4 py-3 text-zinc-400">Any node in workflow failed</td>
                <td className="px-4 py-3 text-zinc-400">Node status = error</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Data Mapping</h2>
        <p className="text-zinc-300 mb-4">
          n8n execution data is mapped to Pisama traces as follows:
        </p>

        <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-zinc-800/50 border-b border-zinc-700">
              <tr>
                <th className="px-4 py-3 text-left text-zinc-300 font-medium">n8n Field</th>
                <th className="px-4 py-3 text-left text-zinc-300 font-medium">MAO Field</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-700">
              <tr>
                <td className="px-4 py-3"><code className="text-blue-400">execution.id</code></td>
                <td className="px-4 py-3 text-zinc-400">trace.session_id</td>
              </tr>
              <tr>
                <td className="px-4 py-3"><code className="text-blue-400">workflow.id</code></td>
                <td className="px-4 py-3 text-zinc-400">trace.metadata.workflow_id</td>
              </tr>
              <tr>
                <td className="px-4 py-3"><code className="text-blue-400">node.name</code></td>
                <td className="px-4 py-3 text-zinc-400">state.agent_id</td>
              </tr>
              <tr>
                <td className="px-4 py-3"><code className="text-blue-400">node.executionTime</code></td>
                <td className="px-4 py-3 text-zinc-400">state.latency_ms</td>
              </tr>
              <tr>
                <td className="px-4 py-3"><code className="text-blue-400">node.data</code></td>
                <td className="px-4 py-3 text-zinc-400">state.state_delta (redacted)</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Example Workflow</h2>
        <p className="text-zinc-300 mb-4">
          Here&apos;s a complete example of an n8n workflow with Pisama integration:
        </p>

        <div className="rounded-xl bg-zinc-800/50 border border-zinc-700 p-6">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <WorkflowNode name="Webhook Trigger" type="trigger" />
            <Arrow />
            <WorkflowNode name="OpenAI" type="ai" />
            <Arrow />
            <WorkflowNode name="Process Data" type="code" />
            <Arrow />
            <WorkflowNode name="Anthropic" type="ai" />
            <Arrow />
            <WorkflowNode name="MAO Webhook" type="http" highlight />
          </div>
          
          <p className="text-sm text-zinc-400 mt-4">
            The MAO Webhook node at the end sends execution data for analysis after the workflow completes.
          </p>
        </div>
      </section>

      <section className="bg-zinc-800/50 rounded-xl border border-zinc-700 p-6">
        <h2 className="text-lg font-bold text-white mb-4">Related Documentation</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <Link
            href="/docs/sdk"
            className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-700 hover:border-blue-500/50 transition-colors"
          >
            <h3 className="font-medium text-white">Python SDK</h3>
            <p className="text-sm text-zinc-400">N8nTracer class reference</p>
          </Link>
          <Link
            href="/docs/api-reference"
            className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-700 hover:border-blue-500/50 transition-colors"
          >
            <h3 className="font-medium text-white">API Reference</h3>
            <p className="text-sm text-zinc-400">Webhook endpoint documentation</p>
          </Link>
        </div>
      </section>
    </div>
  )
}

function NodeBadge({ name, type }: { name: string; type: string }) {
  return (
    <div className="p-3 rounded-lg bg-zinc-800/50 border border-zinc-700 text-center">
      <div className="font-medium text-white">{name}</div>
      <code className="text-xs text-zinc-400">{type}</code>
    </div>
  )
}

function WorkflowNode({ name, type, highlight }: { name: string; type: string; highlight?: boolean }) {
  const bgColor = highlight ? "bg-blue-600/30 border-blue-500" : "bg-zinc-700/50 border-zinc-600"
  const textColor = highlight ? "text-blue-400" : "text-white"
  
  return (
    <div className={`px-4 py-2 rounded-lg border ${bgColor}`}>
      <div className={`font-medium ${textColor}`}>{name}</div>
      <div className="text-xs text-zinc-400">{type}</div>
    </div>
  )
}

function Arrow() {
  return (
    <div className="text-zinc-500 hidden md:block">→</div>
  )
}
