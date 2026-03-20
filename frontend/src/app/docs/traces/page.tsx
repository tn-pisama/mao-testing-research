import type { Metadata } from 'next'
import {
  Workflow,
  Clock,
  Layers,
  GitBranch,
  Zap,
  DollarSign,
  CheckCircle,
  XCircle,
  Loader2,
  Eye,
} from 'lucide-react'

export const metadata: Metadata = {
  title: 'Trace Format',
  description: 'Pisama trace format and OpenTelemetry ingestion. gen_ai.* semantic conventions and universal trace model.',
}

export default function TracesPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-4">Traces</h1>
        <p className="text-lg text-zinc-300">
          Understanding trace data and how to analyze multi-agent execution flows.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">What is a Trace?</h2>
        <p className="text-zinc-300 mb-4">
          A trace represents a complete execution of your multi-agent workflow, from initial
          input to final output. It captures every agent interaction, state change, tool call,
          and message exchange.
        </p>

        <div className="bg-zinc-800/50 rounded-xl border border-zinc-700 p-6">
          <h3 className="font-semibold text-white mb-4">Trace Anatomy</h3>
          <div className="space-y-4">
            <TraceComponent
              icon={Workflow}
              title="Session"
              description="Top-level container for the entire workflow execution"
            />
            <div className="ml-6 border-l-2 border-zinc-700 pl-4 space-y-4">
              <TraceComponent
                icon={Layers}
                title="Spans"
                description="Individual operations within the session (agent calls, tool invocations)"
              />
              <TraceComponent
                icon={GitBranch}
                title="States"
                description="Snapshots of agent state at each step"
              />
              <TraceComponent
                icon={Zap}
                title="Events"
                description="Messages, errors, and other occurrences"
              />
            </div>
          </div>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Trace Status</h2>
        <p className="text-zinc-300 mb-4">
          Each trace has a status indicating its current state:
        </p>

        <div className="grid md:grid-cols-3 gap-4">
          <StatusCard
            icon={Loader2}
            status="Running"
            color="text-blue-400"
            bgColor="bg-blue-500/20"
            description="Execution in progress"
          />
          <StatusCard
            icon={CheckCircle}
            status="Completed"
            color="text-emerald-400"
            bgColor="bg-emerald-500/20"
            description="Successfully finished"
          />
          <StatusCard
            icon={XCircle}
            status="Failed"
            color="text-red-400"
            bgColor="bg-red-500/20"
            description="Terminated with error"
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Key Metrics</h2>
        <p className="text-zinc-300 mb-4">
          Every trace includes these important metrics:
        </p>

        <div className="grid md:grid-cols-2 gap-4">
          <MetricCard
            icon={Zap}
            title="Total Tokens"
            description="Sum of input and output tokens across all LLM calls in the trace"
            example="45,230 tokens"
          />
          <MetricCard
            icon={DollarSign}
            title="Cost"
            description="Estimated cost based on token usage and model pricing"
            example="$0.23"
          />
          <MetricCard
            icon={Clock}
            title="Duration"
            description="Total time from first to last event in the trace"
            example="12.4 seconds"
          />
          <MetricCard
            icon={Layers}
            title="State Count"
            description="Number of state snapshots captured during execution"
            example="24 states"
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Reading the Timeline</h2>
        <p className="text-zinc-300 mb-4">
          The trace timeline shows the sequence of events and state changes:
        </p>

        <div className="bg-zinc-900 rounded-xl border border-zinc-700 p-6">
          <div className="space-y-4">
            <TimelineEntry
              time="0ms"
              agent="Coordinator"
              action="Session started"
              type="start"
            />
            <TimelineEntry
              time="120ms"
              agent="Coordinator"
              action="Delegating task to Researcher"
              type="message"
            />
            <TimelineEntry
              time="340ms"
              agent="Researcher"
              action="Tool call: search_documents()"
              type="tool"
            />
            <TimelineEntry
              time="1,240ms"
              agent="Researcher"
              action="Received 15 results"
              type="result"
            />
            <TimelineEntry
              time="1,890ms"
              agent="Researcher"
              action="Summarizing findings"
              type="thinking"
            />
            <TimelineEntry
              time="3,200ms"
              agent="Coordinator"
              action="Received summary, forwarding to Writer"
              type="message"
            />
          </div>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Filtering & Search</h2>
        <p className="text-zinc-300 mb-4">
          Use these filters to find specific traces:
        </p>

        <div className="space-y-3">
          <FilterRow filter="Status" example='status:failed' description="Filter by completion status" />
          <FilterRow filter="Framework" example='framework:langgraph' description="Filter by agent framework" />
          <FilterRow filter="Cost" example='cost:>0.50' description="Find expensive executions" />
          <FilterRow filter="Duration" example='duration:>10s' description="Find slow traces" />
          <FilterRow filter="Agent" example='agent:researcher' description="Traces involving specific agent" />
          <FilterRow filter="Detection" example='has:detection' description="Traces with failures detected" />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Analyzing State Changes</h2>
        <p className="text-zinc-300 mb-4">
          Click on any state in the timeline to see:
        </p>

        <ul className="space-y-2">
          <li className="flex items-start gap-2 text-zinc-300">
            <Eye size={16} className="text-blue-400 mt-1" />
            <span><strong className="text-white">State Diff:</strong> What changed from the previous state</span>
          </li>
          <li className="flex items-start gap-2 text-zinc-300">
            <Eye size={16} className="text-blue-400 mt-1" />
            <span><strong className="text-white">Full State:</strong> Complete state snapshot at that point</span>
          </li>
          <li className="flex items-start gap-2 text-zinc-300">
            <Eye size={16} className="text-blue-400 mt-1" />
            <span><strong className="text-white">Agent Context:</strong> What the agent saw when making decisions</span>
          </li>
          <li className="flex items-start gap-2 text-zinc-300">
            <Eye size={16} className="text-blue-400 mt-1" />
            <span><strong className="text-white">Token Usage:</strong> Tokens consumed in this step</span>
          </li>
        </ul>
      </section>

      <section className="bg-zinc-800/50 rounded-xl border border-zinc-700 p-6">
        <h3 className="font-semibold text-white mb-2">Pro Tip: Comparing Traces</h3>
        <p className="text-sm text-zinc-300">
          Select two traces to see a side-by-side comparison. This is useful for understanding
          why one execution succeeded while another failed, or for analyzing performance
          differences between runs.
        </p>
      </section>
    </div>
  )
}

function TraceComponent({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof Workflow
  title: string
  description: string
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="p-2 rounded-lg bg-zinc-900">
        <Icon size={16} className="text-blue-400" />
      </div>
      <div>
        <h4 className="font-medium text-white">{title}</h4>
        <p className="text-sm text-zinc-400">{description}</p>
      </div>
    </div>
  )
}

function StatusCard({
  icon: Icon,
  status,
  color,
  bgColor,
  description,
}: {
  icon: typeof CheckCircle
  status: string
  color: string
  bgColor: string
  description: string
}) {
  return (
    <div className={`p-4 rounded-xl border border-zinc-700 ${bgColor}`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon size={18} className={color} />
        <span className={`font-medium ${color}`}>{status}</span>
      </div>
      <p className="text-sm text-zinc-400">{description}</p>
    </div>
  )
}

function MetricCard({
  icon: Icon,
  title,
  description,
  example,
}: {
  icon: typeof Zap
  title: string
  description: string
  example: string
}) {
  return (
    <div className="p-4 rounded-xl bg-zinc-800/50 border border-zinc-700">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={16} className="text-blue-400" />
        <span className="font-medium text-white">{title}</span>
      </div>
      <p className="text-sm text-zinc-400 mb-2">{description}</p>
      <div className="text-xs text-zinc-500">Example: {example}</div>
    </div>
  )
}

function TimelineEntry({
  time,
  agent,
  action,
  type,
}: {
  time: string
  agent: string
  action: string
  type: 'start' | 'message' | 'tool' | 'result' | 'thinking'
}) {
  const typeColors = {
    start: 'bg-emerald-500',
    message: 'bg-blue-500',
    tool: 'bg-purple-500',
    result: 'bg-amber-500',
    thinking: 'bg-zinc-500',
  }

  return (
    <div className="flex items-start gap-4">
      <span className="text-xs text-zinc-500 w-16 text-right pt-1">{time}</span>
      <div className={`w-2 h-2 rounded-full ${typeColors[type]} mt-2`} />
      <div>
        <span className="text-sm font-medium text-white">{agent}</span>
        <p className="text-sm text-zinc-400">{action}</p>
      </div>
    </div>
  )
}

function FilterRow({
  filter,
  example,
  description,
}: {
  filter: string
  example: string
  description: string
}) {
  return (
    <div className="flex items-center gap-4 p-3 rounded-lg bg-zinc-800/50">
      <span className="font-medium text-white w-24">{filter}</span>
      <code className="px-2 py-1 rounded bg-zinc-900 text-blue-400 text-sm">{example}</code>
      <span className="text-sm text-zinc-400">{description}</span>
    </div>
  )
}
