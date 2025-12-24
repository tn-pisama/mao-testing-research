import Link from 'next/link'
import { 
  Activity, 
  AlertTriangle, 
  BarChart3, 
  Workflow,
  ArrowRight 
} from 'lucide-react'

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800">
      <div className="container mx-auto px-4 py-16">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-white mb-4">
            MAO Testing Platform
          </h1>
          <p className="text-xl text-slate-300 max-w-2xl mx-auto">
            Detect infinite loops, state corruption, persona drift, and 
            coordination failures in your multi-agent LLM systems.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 mb-16">
          <FeatureCard
            icon={<Workflow className="w-8 h-8" />}
            title="Trace Analysis"
            description="Real-time OTEL trace ingestion with automatic failure detection"
          />
          <FeatureCard
            icon={<AlertTriangle className="w-8 h-8" />}
            title="Loop Detection"
            description="Multi-level detection: structural, hash, semantic clustering"
          />
          <FeatureCard
            icon={<Activity className="w-8 h-8" />}
            title="State Monitoring"
            description="Semantic corruption detection and cross-field validation"
          />
          <FeatureCard
            icon={<BarChart3 className="w-8 h-8" />}
            title="Cost Analytics"
            description="Track token usage and identify expensive failure patterns"
          />
        </div>

        <div className="flex justify-center gap-4">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
          >
            Open Dashboard
            <ArrowRight className="w-5 h-5" />
          </Link>
          <Link
            href="/traces"
            className="inline-flex items-center gap-2 bg-slate-700 hover:bg-slate-600 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
          >
            View Traces
          </Link>
        </div>
      </div>
    </main>
  )
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 hover:border-primary-500/50 transition-colors">
      <div className="text-primary-400 mb-4">{icon}</div>
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-slate-400 text-sm">{description}</p>
    </div>
  )
}
