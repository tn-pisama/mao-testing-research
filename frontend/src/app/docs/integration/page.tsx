import {
  Terminal,
  Copy,
  AlertTriangle,
  Settings,
  Tag,
} from 'lucide-react'

export default function IntegrationPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-4">Integration Guide</h1>
        <p className="text-lg text-zinc-300">
          Advanced configuration options for integrating Pisama with your multi-agent system.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">SDK Configuration</h2>
        <p className="text-zinc-300 mb-4">
          The Pisama SDK accepts several configuration options:
        </p>

        <CodeBlock title="Python Configuration" language="python">
{`from mao_testing import MAOTracer

tracer = MAOTracer(
    api_key="your_api_key",           # Or use MAO_API_KEY env var
    endpoint="https://api.mao-testing.com",
    environment="production",          # Tag traces by environment
    service_name="my-agent-system",    # Identify your service
    sample_rate=1.0,                   # 1.0 = trace everything
    batch_size=100,                    # Spans per batch
    flush_interval=5.0,                # Seconds between flushes
)`}
        </CodeBlock>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Custom Spans</h2>
        <p className="text-zinc-300 mb-4">
          Add custom spans to track specific operations within your agents:
        </p>

        <CodeBlock title="Custom Span Example" language="python">
{`from mao_testing import MAOTracer

tracer = MAOTracer()

with tracer.trace("workflow") as session:
    # Automatic agent tracing
    result = graph.invoke(state)
    
    # Add custom span for specific operation
    with tracer.span("custom-validation") as span:
        span.set_attribute("validation_type", "output_check")
        span.set_attribute("item_count", len(result.items))
        
        is_valid = validate_output(result)
        span.set_attribute("is_valid", is_valid)
        
        if not is_valid:
            span.set_status("error", "Validation failed")`}
        </CodeBlock>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Adding Metadata</h2>
        <p className="text-zinc-300 mb-4">
          Attach metadata to traces for filtering and analysis:
        </p>

        <CodeBlock title="Metadata Example" language="python">
{`with tracer.trace("workflow") as session:
    # Add session-level metadata
    session.set_metadata({
        "user_id": "user_123",
        "request_id": "req_abc",
        "model_version": "v2.1",
        "experiment": "new-routing-logic",
    })
    
    # Add tags for quick filtering
    session.add_tag("production")
    session.add_tag("high-priority")
    
    result = graph.invoke(state)`}
        </CodeBlock>

        <div className="mt-4 grid md:grid-cols-2 gap-4">
          <MetadataCard
            icon={Tag}
            title="Tags"
            description="Quick labels for filtering (production, test, experiment-a)"
          />
          <MetadataCard
            icon={Settings}
            title="Metadata"
            description="Key-value pairs for detailed context (user_id, version)"
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">State Tracking</h2>
        <p className="text-zinc-300 mb-4">
          Capture agent state at specific points for debugging:
        </p>

        <CodeBlock title="State Capture" language="python">
{`with tracer.trace("workflow") as session:
    # Capture initial state
    session.capture_state("initial", {
        "messages": [],
        "context": initial_context,
    })
    
    result = graph.invoke(state)
    
    # Capture intermediate states
    for i, step in enumerate(result.steps):
        session.capture_state(f"step_{i}", {
            "agent": step.agent,
            "action": step.action,
            "state": step.state,
        })
    
    # Capture final state
    session.capture_state("final", result.final_state)`}
        </CodeBlock>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Sampling & Filtering</h2>
        <p className="text-zinc-300 mb-4">
          Control which traces are sent to reduce volume and costs:
        </p>

        <CodeBlock title="Sampling Configuration" language="python">
{`from mao_testing import MAOTracer, SamplingRule

tracer = MAOTracer(
    sample_rate=0.1,  # Sample 10% of traces by default
    sampling_rules=[
        # Always trace errors
        SamplingRule(condition="status == 'error'", rate=1.0),
        # Always trace slow executions
        SamplingRule(condition="duration > 30s", rate=1.0),
        # Sample expensive operations at 50%
        SamplingRule(condition="cost > 0.10", rate=0.5),
        # Sample by tag
        SamplingRule(condition="tag:production", rate=0.2),
    ]
)`}
        </CodeBlock>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Framework-Specific Setup</h2>
        
        <div className="space-y-6">
          <FrameworkSection title="LangGraph">
{`from mao_testing.integrations.langgraph import LangGraphTracer

tracer = LangGraphTracer()

# Automatic node and edge tracing
graph = StateGraph(AgentState)
graph = tracer.instrument(graph)  # Wrap the graph

# All nodes are now automatically traced
result = graph.invoke(state)`}
          </FrameworkSection>

          <FrameworkSection title="AutoGen">
{`from mao_testing.integrations.autogen import AutoGenTracer

tracer = AutoGenTracer()

# Instrument all agents
assistant = tracer.instrument(
    autogen.AssistantAgent("assistant", llm_config=config)
)
user_proxy = tracer.instrument(
    autogen.UserProxyAgent("user_proxy")
)

# Conversations are automatically traced
user_proxy.initiate_chat(assistant, message="Hello")`}
          </FrameworkSection>

          <FrameworkSection title="CrewAI">
{`from mao_testing.integrations.crewai import CrewAITracer

tracer = CrewAITracer()

# Instrument the crew
crew = Crew(agents=[researcher, writer], tasks=[task])
crew = tracer.instrument(crew)

# Kickoff is automatically traced
result = crew.kickoff()`}
          </FrameworkSection>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Error Handling</h2>
        <p className="text-zinc-300 mb-4">
          Handle tracing errors gracefully to avoid impacting your application:
        </p>

        <CodeBlock title="Error Handling" language="python">
{`from mao_testing import MAOTracer
from mao_testing.errors import TracingError

tracer = MAOTracer(
    on_error="log",  # Options: "log", "raise", "ignore"
)

try:
    with tracer.trace("workflow") as session:
        result = graph.invoke(state)
except TracingError as e:
    # Tracing failed but your app continues
    logger.warning(f"Tracing error: {e}")
    # Result is still available`}
        </CodeBlock>

        <div className="mt-4 p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
          <div className="flex gap-2">
            <AlertTriangle size={18} className="text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-amber-200 font-medium">Production Recommendation</p>
              <p className="text-amber-200/80 text-sm">
                Use <code className="bg-zinc-800 px-1 rounded">on_error=&quot;log&quot;</code> in production 
                to ensure tracing issues never affect your application.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-zinc-800/50 rounded-xl border border-zinc-700 p-6">
        <h3 className="font-semibold text-white mb-4">Performance Impact</h3>
        <div className="grid md:grid-cols-3 gap-4">
          <PerformanceMetric
            label="Latency Overhead"
            value="<5ms"
            description="Per-trace overhead"
          />
          <PerformanceMetric
            label="Memory Usage"
            value="~2MB"
            description="SDK footprint"
          />
          <PerformanceMetric
            label="Background Threads"
            value="1"
            description="For async export"
          />
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

function MetadataCard({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof Tag
  title: string
  description: string
}) {
  return (
    <div className="p-4 rounded-lg bg-zinc-800/50 border border-zinc-700">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={16} className="text-blue-400" />
        <span className="font-medium text-white">{title}</span>
      </div>
      <p className="text-sm text-zinc-400">{description}</p>
    </div>
  )
}

function FrameworkSection({ title, children }: { title: string; children: string }) {
  return (
    <div>
      <h3 className="font-semibold text-white mb-2">{title}</h3>
      <CodeBlock title={`${title} Integration`} language="python">
        {children}
      </CodeBlock>
    </div>
  )
}

function PerformanceMetric({
  label,
  value,
  description,
}: {
  label: string
  value: string
  description: string
}) {
  return (
    <div className="text-center">
      <div className="text-2xl font-bold text-blue-400">{value}</div>
      <div className="font-medium text-white">{label}</div>
      <div className="text-xs text-zinc-400">{description}</div>
    </div>
  )
}
