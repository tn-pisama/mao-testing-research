import Link from 'next/link'
import {
  Rocket,
  AlertTriangle,
  Plug,
  ArrowRight,
  Zap,
  Shield,
  Eye,
} from 'lucide-react'

export default function DocsPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-white mb-4">PISAMA Agent Forensics</h1>
        <p className="text-xl text-zinc-300">
          Comprehensive failure detection for multi-agent LLM systems. Detect infinite loops,
          state corruption, persona drift, and coordination failures before they impact production.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-4 mb-12">
        <QuickStartCard
          href="/docs/getting-started"
          icon={Rocket}
          title="Getting Started"
          description="Set up PISAMA in your agent system in under 5 minutes"
        />
        <QuickStartCard
          href="/docs/integration"
          icon={Plug}
          title="Integration Guide"
          description="Connect your LangGraph, AutoGen, or CrewAI agents"
        />
      </div>

      <section className="mb-12">
        <h2 className="text-2xl font-bold text-white mb-4">What is PISAMA?</h2>
        <p className="text-zinc-300 mb-4">
          AI agent systems are powerful but prone to subtle failures that
          traditional monitoring misses. PISAMA provides specialized forensics for:
        </p>
        
        <div className="grid md:grid-cols-2 gap-4 mt-6">
          <FeatureCard
            icon={AlertTriangle}
            title="Infinite Loop Detection"
            description="Identify when agents get stuck repeating the same actions. Uses structural matching, hash collision detection, and semantic clustering to catch loops at multiple levels."
          />
          <FeatureCard
            icon={Shield}
            title="State Corruption"
            description="Detect when agent state drifts from expected values. Semantic analysis catches corruption that simple validation misses."
          />
          <FeatureCard
            icon={Eye}
            title="Persona Drift"
            description="Monitor when agents deviate from their intended behavior patterns or role definitions over time."
          />
          <FeatureCard
            icon={Zap}
            title="Coordination Deadlock"
            description="Identify when agents are waiting on each other indefinitely, preventing task completion."
          />
        </div>
      </section>

      <section className="mb-12">
        <h2 className="text-2xl font-bold text-white mb-4">How It Works</h2>
        <div className="bg-zinc-800/50 rounded-xl border border-zinc-700 p-6">
          <ol className="space-y-4">
            <Step number={1} title="Instrument Your Agents">
              Add our lightweight SDK or configure OTEL export to send trace data to PISAMA.
            </Step>
            <Step number={2} title="Automatic Analysis">
              Our detection engine analyzes traces in real-time using multiple detection algorithms.
            </Step>
            <Step number={3} title="Get Alerted">
              Receive notifications via Slack, webhook, or email when failures are detected.
            </Step>
            <Step number={4} title="Debug & Fix">
              Use our trace viewer to understand exactly what went wrong and why.
            </Step>
          </ol>
        </div>
      </section>

      <section className="mb-12">
        <h2 className="text-2xl font-bold text-white mb-4">Supported Frameworks</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <FrameworkBadge name="LangGraph" status="Full Support" />
          <FrameworkBadge name="AutoGen" status="Full Support" />
          <FrameworkBadge name="CrewAI" status="Full Support" />
          <FrameworkBadge name="Custom" status="Via OTEL" />
        </div>
      </section>

      <section className="bg-gradient-to-r from-blue-600/10 to-purple-600/10 rounded-xl border border-zinc-800 p-6">
        <h2 className="text-xl font-bold text-white mb-2">Ready to get started?</h2>
        <p className="text-zinc-300 mb-4">
          Follow our quick start guide to integrate PISAMA with your agent system.
        </p>
        <Link
          href="/docs/getting-started"
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-lg transition-colors"
        >
          Start Integration
          <ArrowRight size={16} />
        </Link>
      </section>
    </div>
  )
}

function QuickStartCard({
  href,
  icon: Icon,
  title,
  description,
}: {
  href: string
  icon: typeof Rocket
  title: string
  description: string
}) {
  return (
    <Link
      href={href}
      className="flex items-start gap-4 p-4 rounded-xl bg-zinc-800/50 border border-zinc-700 hover:border-zinc-700 transition-colors group"
    >
      <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 group-hover:bg-blue-500/20 transition-colors">
        <Icon size={20} />
      </div>
      <div>
        <h3 className="font-semibold text-white group-hover:text-blue-400 transition-colors">
          {title}
        </h3>
        <p className="text-sm text-zinc-400">{description}</p>
      </div>
    </Link>
  )
}

function FeatureCard({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof AlertTriangle
  title: string
  description: string
}) {
  return (
    <div className="p-4 rounded-xl bg-zinc-800/50 border border-zinc-700">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={18} className="text-blue-400" />
        <h3 className="font-semibold text-white">{title}</h3>
      </div>
      <p className="text-sm text-zinc-400">{description}</p>
    </div>
  )
}

function Step({ number, title, children }: { number: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 text-white font-bold flex items-center justify-center text-sm">
        {number}
      </div>
      <div>
        <h4 className="font-semibold text-white">{title}</h4>
        <p className="text-sm text-zinc-400">{children}</p>
      </div>
    </li>
  )
}

function FrameworkBadge({ name, status }: { name: string; status: string }) {
  return (
    <div className="p-3 rounded-lg bg-zinc-800/50 border border-zinc-700 text-center">
      <div className="font-medium text-white">{name}</div>
      <div className="text-xs text-zinc-400">{status}</div>
    </div>
  )
}
