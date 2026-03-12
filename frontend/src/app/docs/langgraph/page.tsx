'use client'

import { GitBranch, Network, RefreshCw, Shield } from 'lucide-react'
import { CodeBlock, FeatureCard, MethodCard, SetupStep, DetectionTable, DataMappingTable, SecurityNote, RelatedDocs } from '@/components/docs/SharedDocComponents'

export default function LangGraphDocsPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-4">LangGraph Integration</h1>
        <p className="text-lg text-zinc-300">
          Monitor stateful graph-based agents built with LangGraph. Detect recursion limits,
          state corruption, edge misroutes, and checkpoint integrity issues.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Why LangGraph Integration?</h2>
        <p className="text-zinc-300 mb-4">
          LangGraph agents use stateful graph execution with nodes, edges, and checkpoints that can exhibit unique failure modes:
        </p>
        <div className="grid md:grid-cols-2 gap-4">
          <FeatureCard icon={Network} title="Graph State Monitoring"
            description="Track state mutations across graph nodes and detect corruption or invalid transitions" accentColor="text-emerald-400" />
          <FeatureCard icon={RefreshCw} title="Recursion Detection"
            description="Detect when graph execution exceeds recursion limits or enters infinite loops" accentColor="text-emerald-400" />
          <FeatureCard icon={Shield} title="Checkpoint Integrity"
            description="Verify checkpoint data consistency with graph state after each step" accentColor="text-emerald-400" />
          <FeatureCard icon={GitBranch} title="Parallel Branch Tracking"
            description="Monitor parallel execution branches and detect conflicting state updates" accentColor="text-emerald-400" />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Graph Concepts</h2>
        <p className="text-zinc-300 mb-4">
          LangGraph models agent workflows as directed graphs. Pisama maps these to traces:
        </p>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-zinc-800/50 border border-zinc-700">
            <h3 className="font-semibold text-white mb-2">Nodes</h3>
            <p className="text-sm text-zinc-400">
              Each graph node (agent, tool, router) becomes a state entry in the trace with its inputs and outputs.
            </p>
          </div>
          <div className="p-4 rounded-xl bg-zinc-800/50 border border-zinc-700">
            <h3 className="font-semibold text-white mb-2">Edges</h3>
            <p className="text-sm text-zinc-400">
              Conditional edges are tracked to detect misroutes where the wrong node is selected.
            </p>
          </div>
          <div className="p-4 rounded-xl bg-zinc-800/50 border border-zinc-700">
            <h3 className="font-semibold text-white mb-2">State</h3>
            <p className="text-sm text-zinc-400">
              The graph state object is captured at each step boundary to detect corruption and drift.
            </p>
          </div>
          <div className="p-4 rounded-xl bg-zinc-800/50 border border-zinc-700">
            <h3 className="font-semibold text-white mb-2">Checkpoints</h3>
            <p className="text-sm text-zinc-400">
              Checkpoint data is verified against the running state to detect serialization or consistency issues.
            </p>
          </div>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Integration Methods</h2>
        <div className="space-y-6">
          <MethodCard
            title="Method 1: Python SDK (Recommended)"
            description="Use the LangGraphTracer to automatically capture state transitions and send them to Pisama."
            pros={['Automatic node/edge tracing', 'State capture at boundaries', 'Minimal code changes']}
            cons={['Requires Python SDK installation']}
          >
            <CodeBlock title="LangGraph Tracer" language="python">
{`from mao_testing.integrations import LangGraphTracer
from langgraph.graph import StateGraph

tracer = LangGraphTracer()

# Define your graph
builder = StateGraph(AgentState)
builder.add_node("researcher", research_node)
builder.add_node("writer", writer_node)
builder.add_edge("researcher", "writer")
builder.set_entry_point("researcher")

# Compile with tracer
app = builder.compile()

# Run — tracer auto-captures state at each node boundary
result = await app.ainvoke(
    {"query": "Explain quantum computing"},
    config={"callbacks": [tracer]}
)`}
            </CodeBlock>

            <div className="mt-4 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
              <p className="text-emerald-200 text-sm">
                The tracer automatically captures: node execution order, state deltas, edge decisions,
                tool calls, and timing. No manual instrumentation needed.
              </p>
            </div>
          </MethodCard>

          <MethodCard
            title="Method 2: Webhook"
            description="Configure your LangGraph deployment to send run data to Pisama via webhook callback."
            pros={['Works with LangGraph Cloud', 'No SDK needed in agent code', 'Centralized configuration']}
            cons={['Requires deployment-level config']}
          >
            <h4 className="text-sm font-semibold text-zinc-400 mb-2 mt-4">Setup Steps</h4>
            <ol className="space-y-3">
              <SetupStep number={1} accentColor="bg-emerald-600">
                <strong>Register your deployment</strong> in Pisama:
                <CodeBlock title="Register Deployment" language="bash">
{`curl -X POST https://api.mao-testing.com/api/v1/langgraph/deployments \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"name": "Production", "api_url": "https://api.langgraph.cloud/v1", "api_key": "lsv2_xxx"}'`}
                </CodeBlock>
              </SetupStep>
              <SetupStep number={2} accentColor="bg-emerald-600">
                <strong>Register assistants</strong> to monitor:
                <CodeBlock title="Register Assistant" language="bash">
{`curl -X POST https://api.mao-testing.com/api/v1/langgraph/assistants \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"deployment_id": "DEPLOY_ID", "assistant_id": "asst_xxx", "graph_id": "research_graph"}'`}
                </CodeBlock>
              </SetupStep>
              <SetupStep number={3} accentColor="bg-emerald-600">
                <strong>Send run data</strong> to the webhook after each graph execution:
                <CodeBlock title="Webhook Payload" language="json">
{`{
  "run_id": "run_abc123",
  "assistant_id": "asst_xxx",
  "thread_id": "thread_xyz",
  "graph_id": "research_graph",
  "status": "completed",
  "total_steps": 5,
  "total_tokens": 2450,
  "steps": [
    {"node": "researcher", "inputs": {...}, "outputs": {...}},
    {"node": "writer", "inputs": {...}, "outputs": {...}}
  ]
}`}
                </CodeBlock>
              </SetupStep>
            </ol>
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
          The webhook secret is generated when you register your assistant. Include signature
          headers in your webhook calls for production use.
        </SecurityNote>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Detection Capabilities</h2>
        <DetectionTable detections={[
          { name: 'Recursion', description: 'Graph execution exceeds configured recursion limit', trigger: 'Step count > recursion_limit' },
          { name: 'State Corruption', description: 'State object modified with invalid keys or types', trigger: 'State schema validation failure' },
          { name: 'Edge Misroute', description: 'Conditional edge routes to unexpected node', trigger: 'Edge decision does not match expected conditions' },
          { name: 'Tool Failure', description: 'ToolNode call fails and is not handled by graph', trigger: 'Tool error without catch/retry edge' },
          { name: 'Parallel Sync', description: 'Parallel branches produce conflicting state updates', trigger: 'Merge conflict in parallel branch outputs' },
          { name: 'Checkpoint Corruption', description: 'Checkpoint data inconsistent with current graph state', trigger: 'Checkpoint hash mismatch after resume' },
        ]} />
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Data Mapping</h2>
        <p className="text-zinc-300 mb-4">
          LangGraph run data is mapped to Pisama traces as follows:
        </p>
        <DataMappingTable sourceLabel="LangGraph" mappings={[
          { source: 'run_id', target: 'trace.session_id' },
          { source: 'assistant_id', target: 'trace.metadata.assistant_id' },
          { source: 'graph_id', target: 'trace.metadata.graph_id' },
          { source: 'step.node', target: 'state.agent_id' },
          { source: 'step.inputs', target: 'state.state_delta.inputs (redacted)' },
          { source: 'step.outputs', target: 'state.state_delta.outputs (redacted)' },
          { source: 'total_tokens', target: 'trace.total_tokens' },
          { source: 'thread_id', target: 'trace.metadata.thread_id' },
        ]} />
      </section>

      <RelatedDocs links={[
        { href: '/docs/sdk', title: 'Python SDK', description: 'LangGraphTracer class reference' },
        { href: '/docs/api-reference', title: 'API Reference', description: 'Webhook endpoint documentation' },
        { href: '/docs/getting-started', title: 'Getting Started', description: 'Quick setup guide' },
        { href: '/docs/detections', title: 'Detections', description: 'All detection types explained' },
      ]} />
    </div>
  )
}
