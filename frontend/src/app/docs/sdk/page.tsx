import Link from 'next/link'
import { Terminal, Copy, Check } from 'lucide-react'

export default function SDKPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-4">Python SDK Reference</h1>
        <p className="text-lg text-zinc-300">
          Complete reference for the Pisama Python SDK. Instrument your multi-agent 
          systems with minimal code changes.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Installation</h2>
        <CodeBlock title="pip" language="bash">
          pip install mao-testing
        </CodeBlock>
        
        <div className="mt-4">
          <CodeBlock title="With framework integrations" language="bash">
{`pip install mao-testing[langgraph]   # LangGraph support
pip install mao-testing[autogen]     # AutoGen support
pip install mao-testing[crewai]      # CrewAI support
pip install mao-testing[all]         # All integrations`}
          </CodeBlock>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Quick Start</h2>
        <CodeBlock title="Basic Usage" language="python">
{`from mao_testing import MAOTracer

# Initialize with API key from environment (MAO_API_KEY)
tracer = MAOTracer()

# Or pass explicitly
tracer = MAOTracer(api_key="your-api-key")

# Trace a workflow
with tracer.trace("my-workflow") as session:
    # Your agent code here
    result = run_agents()
    
    # Capture state snapshots
    session.capture_state("result", {"output": result})`}
        </CodeBlock>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">MAOTracer Class</h2>
        <p className="text-zinc-300 mb-4">
          The main entry point for tracing multi-agent workflows.
        </p>

        <div className="space-y-6">
          <APIMethod
            name="MAOTracer"
            signature="MAOTracer(api_key=None, endpoint=None, **kwargs)"
            description="Initialize the tracer with configuration options."
            params={[
              { name: "api_key", type: "str", description: "API key for authentication. Defaults to MAO_API_KEY env var." },
              { name: "endpoint", type: "str", description: "API endpoint URL. Defaults to https://api.mao-testing.com" },
              { name: "environment", type: "str", description: "Environment tag (production, staging, development)" },
              { name: "service_name", type: "str", description: "Name of your service for filtering" },
              { name: "sample_rate", type: "float", description: "Sampling rate 0.0-1.0. Default 1.0 (trace everything)" },
              { name: "batch_size", type: "int", description: "Spans per batch. Default 100" },
              { name: "flush_interval", type: "float", description: "Seconds between flushes. Default 5.0" },
              { name: "on_error", type: "str", description: "Error handling: 'log', 'raise', or 'ignore'" },
            ]}
          />

          <APIMethod
            name="trace"
            signature="tracer.trace(name, framework=None, metadata=None)"
            description="Start a new trace session. Use as a context manager."
            params={[
              { name: "name", type: "str", description: "Name for this trace/workflow" },
              { name: "framework", type: "str", description: "Framework identifier (langgraph, autogen, crewai, custom)" },
              { name: "metadata", type: "dict", description: "Additional metadata to attach to the trace" },
            ]}
            returns="TraceSession context manager"
          />

          <APIMethod
            name="span"
            signature="tracer.span(name, parent=None)"
            description="Create a custom span for tracking specific operations."
            params={[
              { name: "name", type: "str", description: "Name for this span" },
              { name: "parent", type: "Span", description: "Optional parent span for nesting" },
            ]}
            returns="Span context manager"
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">TraceSession Class</h2>
        <p className="text-zinc-300 mb-4">
          Returned by <code className="bg-zinc-800 px-1 rounded">tracer.trace()</code>. 
          Use to capture state and add metadata during a trace.
        </p>

        <div className="space-y-6">
          <APIMethod
            name="capture_state"
            signature="session.capture_state(name, state, agent_id=None)"
            description="Capture a state snapshot at a specific point in the workflow."
            params={[
              { name: "name", type: "str", description: "Label for this state (e.g., 'initial', 'after_research')" },
              { name: "state", type: "dict", description: "State data to capture (will be serialized to JSON)" },
              { name: "agent_id", type: "str", description: "Optional agent identifier for this state" },
            ]}
          />

          <APIMethod
            name="set_metadata"
            signature="session.set_metadata(metadata)"
            description="Add metadata to the trace session."
            params={[
              { name: "metadata", type: "dict", description: "Key-value pairs of metadata" },
            ]}
          />

          <APIMethod
            name="add_tag"
            signature="session.add_tag(tag)"
            description="Add a tag to the trace for filtering."
            params={[
              { name: "tag", type: "str", description: "Tag string (e.g., 'production', 'high-priority')" },
            ]}
          />

          <APIMethod
            name="span"
            signature="session.span(name)"
            description="Create a span within this trace session."
            params={[
              { name: "name", type: "str", description: "Name for this span" },
            ]}
            returns="Span context manager"
          />

          <APIMethod
            name="set_status"
            signature="session.set_status(status, message=None)"
            description="Set the final status of the trace."
            params={[
              { name: "status", type: "str", description: "'ok', 'error', or 'warning'" },
              { name: "message", type: "str", description: "Optional status message" },
            ]}
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Framework Integrations</h2>

        <div className="space-y-8">
          <FrameworkIntegration
            name="LangGraph"
            importPath="from mao_testing.integrations import LangGraphTracer"
            example={`from mao_testing.integrations import LangGraphTracer
from langgraph.graph import StateGraph

tracer = LangGraphTracer()

# Create your graph
graph = StateGraph(AgentState)
graph.add_node("researcher", researcher_agent)
graph.add_node("writer", writer_agent)
graph.add_edge("researcher", "writer")

# Instrument it (wraps all nodes automatically)
graph = tracer.instrument(graph)

# Run as normal - tracing happens automatically
app = graph.compile()
result = app.invoke({"messages": []})`}
            features={[
              "Automatic node tracing",
              "State capture between nodes",
              "Edge transition tracking",
              "Conditional edge support",
            ]}
          />

          <FrameworkIntegration
            name="AutoGen"
            importPath="from mao_testing.integrations import AutoGenTracer"
            example={`from mao_testing.integrations import AutoGenTracer
import autogen

tracer = AutoGenTracer()

# Create agents
assistant = autogen.AssistantAgent(
    "assistant",
    llm_config={"model": "gpt-4"}
)
user_proxy = autogen.UserProxyAgent("user_proxy")

# Instrument agents
assistant = tracer.instrument(assistant)
user_proxy = tracer.instrument(user_proxy)

# Run conversation - tracing happens automatically
user_proxy.initiate_chat(assistant, message="Write a poem")`}
            features={[
              "Automatic message tracing",
              "Agent interaction tracking",
              "Function call monitoring",
              "GroupChat support",
            ]}
          />

          <FrameworkIntegration
            name="CrewAI"
            importPath="from mao_testing.integrations import CrewAITracer"
            example={`from mao_testing.integrations import CrewAITracer
from crewai import Agent, Task, Crew

tracer = CrewAITracer()

# Create crew
researcher = Agent(role="Researcher", ...)
writer = Agent(role="Writer", ...)
crew = Crew(agents=[researcher, writer], tasks=[...])

# Instrument crew
crew = tracer.instrument(crew)

# Kickoff - tracing happens automatically
result = crew.kickoff()`}
            features={[
              "Agent task tracing",
              "Tool usage monitoring",
              "Delegation tracking",
              "Memory access logging",
            ]}
          />

          <FrameworkIntegration
            name="n8n"
            importPath="from mao_testing.integrations import N8nTracer"
            example={`from mao_testing.integrations import N8nTracer

tracer = N8nTracer(
    n8n_url="https://your-n8n.example.com",
    n8n_api_key="your-n8n-api-key",
)

# Poll for recent executions and sync to MAO
from datetime import datetime, timedelta
since = datetime.utcnow() - timedelta(hours=1)

results = await tracer.sync_executions(
    since=since,
    mao_endpoint="https://api.mao-testing.com",
    mao_api_key="your-mao-api-key",
)

# Or send individual executions
execution = await tracer.get_execution("exec-123")
await tracer.send_to_mao(execution)`}
            features={[
              "Poll n8n API for executions",
              "AI node detection (OpenAI, Anthropic, LangChain)",
              "HMAC webhook signature support",
              "Batch sync capabilities",
            ]}
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Span Attributes</h2>
        <p className="text-zinc-300 mb-4">
          Set attributes on spans to provide additional context:
        </p>

        <CodeBlock title="Span Attributes" language="python">
{`with session.span("llm-call") as span:
    # Standard attributes
    span.set_attribute("gen_ai.system", "openai")
    span.set_attribute("gen_ai.request.model", "gpt-4")
    span.set_attribute("gen_ai.request.temperature", 0.7)
    span.set_attribute("gen_ai.request.max_tokens", 1000)
    
    # After the call
    span.set_attribute("gen_ai.usage.prompt_tokens", 150)
    span.set_attribute("gen_ai.usage.completion_tokens", 200)
    span.set_attribute("gen_ai.usage.total_tokens", 350)
    
    # Custom attributes
    span.set_attribute("custom.agent_name", "researcher")
    span.set_attribute("custom.task_type", "summarization")`}
        </CodeBlock>

        <div className="mt-6">
          <h3 className="text-lg font-semibold text-white mb-3">Standard Attribute Prefixes</h3>
          <div className="grid md:grid-cols-2 gap-4">
            <AttributeCard
              prefix="gen_ai.*"
              description="AI/LLM specific attributes (model, tokens, prompts)"
            />
            <AttributeCard
              prefix="langgraph.*"
              description="LangGraph node and state attributes"
            />
            <AttributeCard
              prefix="autogen.*"
              description="AutoGen agent and message attributes"
            />
            <AttributeCard
              prefix="crewai.*"
              description="CrewAI agent and task attributes"
            />
          </div>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Error Handling</h2>
        <CodeBlock title="Error Handling Configuration" language="python">
{`from mao_testing import MAOTracer
from mao_testing.errors import TracingError, ConfigurationError

# Option 1: Log errors (recommended for production)
tracer = MAOTracer(on_error="log")

# Option 2: Raise exceptions
tracer = MAOTracer(on_error="raise")

try:
    with tracer.trace("workflow") as session:
        result = run_agents()
except TracingError as e:
    logger.error(f"Tracing failed: {e}")
    # Application continues

# Option 3: Ignore errors silently
tracer = MAOTracer(on_error="ignore")`}
        </CodeBlock>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Environment Variables</h2>
        <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-zinc-800/50 border-b border-zinc-700">
              <tr>
                <th className="px-4 py-3 text-left text-zinc-300 font-medium">Variable</th>
                <th className="px-4 py-3 text-left text-zinc-300 font-medium">Description</th>
                <th className="px-4 py-3 text-left text-zinc-300 font-medium">Default</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-700">
              <EnvRow name="MAO_API_KEY" description="API key for authentication" required />
              <EnvRow name="MAO_ENDPOINT" description="API endpoint URL" defaultValue="https://api.mao-testing.com" />
              <EnvRow name="MAO_ENVIRONMENT" description="Environment tag" defaultValue="production" />
              <EnvRow name="MAO_SERVICE_NAME" description="Service identifier" defaultValue="mao-agent" />
              <EnvRow name="MAO_SAMPLE_RATE" description="Trace sampling rate (0.0-1.0)" defaultValue="1.0" />
              <EnvRow name="MAO_DEBUG" description="Enable debug logging" defaultValue="false" />
            </tbody>
          </table>
        </div>
      </section>

      <section className="bg-zinc-800/50 rounded-xl border border-zinc-700 p-6">
        <h2 className="text-lg font-bold text-white mb-4">Next Steps</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <Link
            href="/docs/cli"
            className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-700 hover:border-blue-500/50 transition-colors"
          >
            <h3 className="font-medium text-white">CLI Reference</h3>
            <p className="text-sm text-zinc-400">Import traces, query detections from command line</p>
          </Link>
          <Link
            href="/docs/api-reference"
            className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-700 hover:border-blue-500/50 transition-colors"
          >
            <h3 className="font-medium text-white">REST API</h3>
            <p className="text-sm text-zinc-400">Direct API access for custom integrations</p>
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

function APIMethod({
  name: _name,
  signature,
  description,
  params,
  returns,
}: {
  name: string
  signature: string
  description: string
  params: Array<{ name: string; type: string; description: string }>
  returns?: string
}) {
  return (
    <div className="rounded-lg bg-zinc-800/50 border border-zinc-700 overflow-hidden">
      <div className="px-4 py-3 bg-zinc-900/50 border-b border-zinc-700">
        <code className="text-blue-400 font-mono text-sm">{signature}</code>
      </div>
      <div className="p-4">
        <p className="text-zinc-300 mb-4">{description}</p>
        
        <h4 className="text-sm font-semibold text-zinc-400 mb-2">Parameters</h4>
        <div className="space-y-2 mb-4">
          {params.map((param) => (
            <div key={param.name} className="flex gap-2 text-sm">
              <code className="text-blue-400">{param.name}</code>
              <span className="text-zinc-500">({param.type})</span>
              <span className="text-zinc-400">- {param.description}</span>
            </div>
          ))}
        </div>
        
        {returns && (
          <>
            <h4 className="text-sm font-semibold text-zinc-400 mb-2">Returns</h4>
            <p className="text-sm text-zinc-300">{returns}</p>
          </>
        )}
      </div>
    </div>
  )
}

function FrameworkIntegration({
  name,
  importPath,
  example,
  features,
}: {
  name: string
  importPath: string
  example: string
  features: string[]
}) {
  return (
    <div className="rounded-lg bg-zinc-800/30 border border-zinc-700 p-6">
      <h3 className="text-lg font-bold text-white mb-2">{name}</h3>
      <code className="text-sm text-blue-400 bg-zinc-900 px-2 py-1 rounded">{importPath}</code>
      
      <div className="mt-4">
        <CodeBlock title={`${name} Example`} language="python">
          {example}
        </CodeBlock>
      </div>
      
      <div className="mt-4">
        <h4 className="text-sm font-semibold text-zinc-400 mb-2">Features</h4>
        <ul className="grid grid-cols-2 gap-2">
          {features.map((feature) => (
            <li key={feature} className="flex items-center gap-2 text-sm text-zinc-300">
              <Check size={14} className="text-emerald-400" />
              {feature}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function AttributeCard({ prefix, description }: { prefix: string; description: string }) {
  return (
    <div className="p-3 rounded-lg bg-zinc-800/50 border border-zinc-700">
      <code className="text-blue-400 text-sm">{prefix}</code>
      <p className="text-sm text-zinc-400 mt-1">{description}</p>
    </div>
  )
}

function EnvRow({
  name,
  description,
  defaultValue,
  required,
}: {
  name: string
  description: string
  defaultValue?: string
  required?: boolean
}) {
  return (
    <tr>
      <td className="px-4 py-3">
        <code className="text-blue-400">{name}</code>
        {required && <span className="ml-2 text-xs text-red-400">required</span>}
      </td>
      <td className="px-4 py-3 text-zinc-300">{description}</td>
      <td className="px-4 py-3 text-zinc-400">{defaultValue || "-"}</td>
    </tr>
  )
}
