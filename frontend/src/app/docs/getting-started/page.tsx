import Link from 'next/link'
import { ArrowRight, Check, Copy, Terminal, AlertTriangle } from 'lucide-react'

export default function GettingStartedPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-4">Getting Started</h1>
        <p className="text-lg text-slate-300">
          Get Pisama running with your multi-agent system in under 5 minutes.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Prerequisites</h2>
        <ul className="space-y-2">
          <Prerequisite>A running multi-agent system (LangGraph, AutoGen, CrewAI, or custom)</Prerequisite>
          <Prerequisite>Python 3.9+ or Node.js 18+</Prerequisite>
          <Prerequisite>Pisama API key (get one from Settings)</Prerequisite>
        </ul>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Step 1: Install the SDK</h2>
        <p className="text-slate-300 mb-4">
          Choose the installation method for your runtime:
        </p>
        
        <div className="space-y-4">
          <CodeBlock title="Python" language="bash">
            pip install mao-testing
          </CodeBlock>
          
          <CodeBlock title="Node.js" language="bash">
            npm install @mao-testing/sdk
          </CodeBlock>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Step 2: Configure Your API Key</h2>
        <p className="text-slate-300 mb-4">
          Set your API key as an environment variable:
        </p>
        
        <CodeBlock title="Environment Variable" language="bash">
          export MAO_API_KEY=your_api_key_here
        </CodeBlock>

        <div className="mt-4 p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
          <div className="flex gap-2">
            <AlertTriangle size={18} className="text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-amber-200 font-medium">Security Note</p>
              <p className="text-amber-200/80 text-sm">
                Never commit your API key to version control. Use environment variables or a secrets manager.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Step 3: Instrument Your Agents</h2>
        <p className="text-slate-300 mb-4">
          Add the Pisama wrapper to your agent initialization:
        </p>

        <CodeBlock title="LangGraph Example" language="python">
{`from mao_testing import MAOTracer
from langgraph.graph import StateGraph

# Initialize the tracer
tracer = MAOTracer()

# Wrap your graph
graph = StateGraph(AgentState)
graph.add_node("researcher", researcher_agent)
graph.add_node("writer", writer_agent)

# Start tracing
with tracer.trace("my-workflow"):
    result = graph.invoke(initial_state)`}
        </CodeBlock>

        <CodeBlock title="AutoGen Example" language="python">
{`from mao_testing import MAOTracer
import autogen

tracer = MAOTracer()

# Your existing AutoGen setup
assistant = autogen.AssistantAgent("assistant", llm_config=config)
user_proxy = autogen.UserProxyAgent("user_proxy")

# Start tracing
with tracer.trace("autogen-chat"):
    user_proxy.initiate_chat(assistant, message="Hello")`}
        </CodeBlock>

        <CodeBlock title="CrewAI Example" language="python">
{`from mao_testing import MAOTracer
from crewai import Crew, Agent, Task

tracer = MAOTracer()

# Your existing CrewAI setup
crew = Crew(agents=[researcher, writer], tasks=[research_task])

# Start tracing
with tracer.trace("crew-execution"):
    result = crew.kickoff()`}
        </CodeBlock>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Step 4: Run Your Agents</h2>
        <p className="text-slate-300 mb-4">
          Execute your agent workflow as normal. Pisama will automatically:
        </p>
        <ul className="space-y-2 mb-4">
          <Prerequisite>Capture all agent interactions and state changes</Prerequisite>
          <Prerequisite>Analyze traces for failure patterns in real-time</Prerequisite>
          <Prerequisite>Send alerts when issues are detected</Prerequisite>
        </ul>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Step 5: View Results</h2>
        <p className="text-slate-300 mb-4">
          Open the Pisama dashboard to see your traces and any detected issues:
        </p>
        <div className="flex gap-4">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white font-medium px-4 py-2 rounded-lg transition-colors"
          >
            Open Dashboard
            <ArrowRight size={16} />
          </Link>
          <Link
            href="/traces"
            className="inline-flex items-center gap-2 bg-slate-700 hover:bg-slate-600 text-white font-medium px-4 py-2 rounded-lg transition-colors"
          >
            View Traces
          </Link>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Alternative: OTEL Export</h2>
        <p className="text-slate-300 mb-4">
          If you prefer to use OpenTelemetry directly, configure your OTEL exporter to send traces to our endpoint:
        </p>
        
        <CodeBlock title="OTEL Configuration" language="bash">
{`export OTEL_EXPORTER_OTLP_ENDPOINT=https://api.mao-testing.com/v1/traces
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer $MAO_API_KEY"`}
        </CodeBlock>
      </section>

      <section className="bg-slate-800/50 rounded-xl border border-slate-700 p-6">
        <h2 className="text-lg font-bold text-white mb-2">Next Steps</h2>
        <div className="grid md:grid-cols-2 gap-4 mt-4">
          <Link
            href="/docs/detections"
            className="p-4 rounded-lg bg-slate-900/50 border border-slate-700 hover:border-primary-500/50 transition-colors"
          >
            <h3 className="font-medium text-white">Understanding Detections</h3>
            <p className="text-sm text-slate-400">Learn about the types of failures we detect</p>
          </Link>
          <Link
            href="/docs/integration"
            className="p-4 rounded-lg bg-slate-900/50 border border-slate-700 hover:border-primary-500/50 transition-colors"
          >
            <h3 className="font-medium text-white">Advanced Integration</h3>
            <p className="text-sm text-slate-400">Custom spans, metadata, and filtering</p>
          </Link>
        </div>
      </section>
    </div>
  )
}

function Prerequisite({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-center gap-2 text-slate-300">
      <Check size={16} className="text-emerald-400" />
      {children}
    </li>
  )
}

function CodeBlock({ title, language, children }: { title: string; language: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-slate-900 border border-slate-700 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700 bg-slate-800/50">
        <div className="flex items-center gap-2">
          <Terminal size={14} className="text-slate-400" />
          <span className="text-sm text-slate-400">{title}</span>
        </div>
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
