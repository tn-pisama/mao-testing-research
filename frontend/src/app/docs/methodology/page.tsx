import Link from 'next/link'
import {
  Database,
  GitBranch,
  Layers,
  Target,
  CheckCircle,
  FileText,
  AlertTriangle,
  ArrowRight,
  ExternalLink,
} from 'lucide-react'

export default function MethodologyPage() {
  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-emerald-600/20 rounded-lg">
            <Target className="w-6 h-6 text-emerald-400" />
          </div>
          <h1 className="text-3xl font-bold text-white">Benchmark Methodology</h1>
        </div>
        <p className="text-zinc-300 text-lg">
          How we measure detection accuracy and ensure transparent, reproducible results.
        </p>
      </div>

      {/* Overview */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold text-white mb-4">Overview</h2>
        <p className="text-zinc-300 mb-4">
          PISAMA detection benchmarks are run against real-world agent traces sourced from
          public datasets and research. We use the MAST (Multi-Agent System Testing) taxonomy
          which defines 16 failure modes across content, structural, and RAG categories.
        </p>
        <div className="bg-zinc-800/50 rounded-lg p-4 border border-zinc-700">
          <div className="grid md:grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-emerald-400">82.4%</div>
              <div className="text-sm text-zinc-400">Overall Detection Rate</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-white">16</div>
              <div className="text-sm text-zinc-400">Failure Modes (F1-F16)</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-white">20,575</div>
              <div className="text-sm text-zinc-400">Evaluation Traces</div>
            </div>
          </div>
        </div>
      </section>

      {/* Dataset */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <Database size={20} className="text-indigo-400" />
          Dataset
        </h2>
        <p className="text-zinc-300 mb-4">
          All benchmark traces are sourced from real-world agent executions. We do not use
          synthetic or mock data for evaluation.
        </p>

        <div className="space-y-4">
          <div className="bg-zinc-800 rounded-lg p-4 border border-zinc-700">
            <h3 className="font-medium text-white mb-3">Data Sources</h3>
            <div className="grid md:grid-cols-2 gap-3">
              <SourceItem
                name="HuggingFace"
                description="Agent traces from HF datasets (expanded traces)"
              />
              <SourceItem
                name="GitHub"
                description="Open-source agent repository traces"
              />
              <SourceItem
                name="Anthropic"
                description="Claude-based agent execution traces"
              />
              <SourceItem
                name="Research Papers"
                description="Published agent benchmark traces (Toolathlon, AgentBench)"
              />
            </div>
          </div>

          <div className="bg-zinc-800 rounded-lg p-4 border border-zinc-700">
            <h3 className="font-medium text-white mb-3">Framework Coverage</h3>
            <div className="flex flex-wrap gap-2">
              {['LangChain', 'LangGraph', 'AutoGen', 'CrewAI', 'OpenAI', 'Anthropic', 'React', 'Function Calling'].map((fw) => (
                <span key={fw} className="px-3 py-1 bg-zinc-700 text-zinc-300 rounded-lg text-sm">
                  {fw}
                </span>
              ))}
            </div>
          </div>

          <div className="bg-zinc-800 rounded-lg p-4 border border-zinc-700">
            <h3 className="font-medium text-white mb-3">Dataset Statistics</h3>
            <div className="grid md:grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-zinc-400">Total Size:</span>
                <span className="text-white ml-2">207 MB</span>
              </div>
              <div>
                <span className="text-zinc-400">Trace Count:</span>
                <span className="text-white ml-2">20,575</span>
              </div>
              <div>
                <span className="text-zinc-400">F1-F14 Eval:</span>
                <span className="text-white ml-2">1,300 traces</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Detection Approach */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <Layers size={20} className="text-purple-400" />
          Detection Approach
        </h2>
        <p className="text-zinc-300 mb-4">
          PISAMA uses a tiered detection architecture, starting with fast rule-based checks
          and escalating to semantic analysis when needed.
        </p>

        <div className="space-y-3">
          <ApproachItem
            tier={1}
            name="Pattern Matching"
            description="Exact string matching, hash collision detection for loops and structural issues. Cost: $0, Latency: <1ms"
          />
          <ApproachItem
            tier={2}
            name="State Delta Analysis"
            description="Sequential state comparison, transition validation, corruption detection. Cost: $0, Latency: <5ms"
          />
          <ApproachItem
            tier={3}
            name="Semantic Analysis"
            description="Sentence embeddings for semantic similarity, intent parsing, context overlap. Cost: $0, Latency: <50ms"
          />
          <ApproachItem
            tier={4}
            name="LLM Judge (Optional)"
            description="Claude/GPT-4 as judge for ambiguous cases. Used sparingly for calibration. Cost: ~$0.50, Latency: <2s"
          />
        </div>
      </section>

      {/* MAST Taxonomy */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <GitBranch size={20} className="text-amber-400" />
          MAST Failure Taxonomy
        </h2>
        <p className="text-zinc-300 mb-4">
          The Multi-Agent System Testing (MAST) taxonomy defines 16 failure modes organized
          into three categories.
        </p>

        <div className="space-y-6">
          <CategorySection
            name="Content Failures"
            description="Issues with what the agent produces"
            modes={[
              { code: 'F1', name: 'Specification Mismatch', rate: 98 },
              { code: 'F6', name: 'Task Derailment', rate: 100 },
              { code: 'F7', name: 'Context Neglect', rate: 100 },
              { code: 'F8', name: 'Information Withholding', rate: 100 },
              { code: 'F10', name: 'Communication Breakdown', rate: 64 },
              { code: 'F13', name: 'Quality Gate Bypass', rate: 96 },
              { code: 'F14', name: 'Completion Misjudgment', rate: 84 },
            ]}
          />

          <CategorySection
            name="Structural Failures"
            description="Issues with how the agent operates"
            modes={[
              { code: 'F2', name: 'Poor Task Decomposition', rate: 100 },
              { code: 'F3', name: 'Resource Misallocation', rate: 66.7 },
              { code: 'F4', name: 'Inadequate Tool Provision', rate: 66.7 },
              { code: 'F5', name: 'Flawed Workflow Design', rate: 100 },
              { code: 'F9', name: 'Role Usurpation', rate: 66.7 },
              { code: 'F11', name: 'Coordination Failure', rate: 100 },
              { code: 'F12', name: 'Output Validation Failure', rate: 66.7 },
            ]}
          />

          <CategorySection
            name="RAG Failures (New)"
            description="Issues with retrieval-augmented generation"
            modes={[
              { code: 'F15', name: 'Grounding Failure', rate: null },
              { code: 'F16', name: 'Retrieval Quality Failure', rate: null },
            ]}
          />
        </div>
      </section>

      {/* Improvement Techniques */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <CheckCircle size={20} className="text-emerald-400" />
          Improvement Techniques
        </h2>
        <p className="text-zinc-300 mb-4">
          Detection improved from 68.7% to 82.4% baseline through targeted enhancements.
        </p>

        <div className="space-y-4">
          <ImprovementItem
            code="F1"
            name="Specification Mismatch"
            before={0}
            after={98}
            technique="Intent parsing from scenario descriptions + semantic comparison of keywords vs output"
          />
          <ImprovementItem
            code="F2"
            name="Task Decomposition"
            before={10}
            after={100}
            technique="Structural analysis for granularity, dependency, and duplicate detection"
          />
          <ImprovementItem
            code="F7"
            name="Context Neglect"
            before={10}
            after={100}
            technique="Semantic overlap of key terms + numerical data tracking"
          />
          <ImprovementItem
            code="F14"
            name="Completion Misjudgment"
            before={6}
            after={84}
            technique="Comprehensive marker detection (TODO, placeholder, truncation patterns)"
          />
        </div>
      </section>

      {/* Reproducibility */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <FileText size={20} className="text-blue-400" />
          Reproducibility
        </h2>
        <p className="text-zinc-300 mb-4">
          All evaluation code is available in the repository for independent verification.
        </p>

        <div className="bg-zinc-800 rounded-lg p-4 border border-zinc-700">
          <h3 className="font-medium text-white mb-3">Evaluation Scripts</h3>
          <div className="space-y-2 font-mono text-sm">
            <code className="block text-zinc-300">
              /benchmarks/evaluation/run_all_detectors.py
            </code>
            <code className="block text-zinc-300">
              /benchmarks/evaluation/phase1_synthetic_eval.py
            </code>
            <code className="block text-zinc-300">
              /benchmarks/evaluation/phase2_adversarial_eval.py
            </code>
          </div>
        </div>

        <div className="mt-4 bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
          <div className="flex items-start gap-2">
            <AlertTriangle className="text-blue-400 mt-0.5 flex-shrink-0" size={16} />
            <div className="text-sm text-zinc-300">
              <strong className="text-blue-300">Note:</strong> Results may vary based on
              embedding model version and threshold configuration. We recommend running
              on the provided dataset for consistent comparison.
            </div>
          </div>
        </div>
      </section>

      {/* Links */}
      <section className="flex gap-4">
        <Link
          href="/benchmarks"
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
        >
          View Benchmark Results
          <ArrowRight size={16} />
        </Link>
        <Link
          href="/docs/detections"
          className="flex items-center gap-2 px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg transition-colors"
        >
          Detection Types
          <ArrowRight size={16} />
        </Link>
      </section>
    </div>
  )
}

function SourceItem({ name, description }: { name: string; description: string }) {
  return (
    <div className="flex items-start gap-2">
      <CheckCircle className="text-emerald-400 mt-0.5 flex-shrink-0" size={14} />
      <div>
        <span className="text-white font-medium">{name}</span>
        <span className="text-zinc-400 text-sm ml-2">{description}</span>
      </div>
    </div>
  )
}

function ApproachItem({ tier, name, description }: { tier: number; name: string; description: string }) {
  const tierColors = {
    1: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    2: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    3: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    4: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  }

  return (
    <div className="bg-zinc-800 rounded-lg p-4 border border-zinc-700">
      <div className="flex items-center gap-3 mb-2">
        <span className={`px-2 py-0.5 text-xs rounded border ${tierColors[tier as keyof typeof tierColors]}`}>
          Tier {tier}
        </span>
        <span className="text-white font-medium">{name}</span>
      </div>
      <p className="text-zinc-400 text-sm">{description}</p>
    </div>
  )
}

function CategorySection({
  name,
  description,
  modes,
}: {
  name: string
  description: string
  modes: { code: string; name: string; rate: number | null }[]
}) {
  return (
    <div className="bg-zinc-800 rounded-lg border border-zinc-700 overflow-hidden">
      <div className="p-4 border-b border-zinc-700">
        <h3 className="font-medium text-white">{name}</h3>
        <p className="text-zinc-400 text-sm">{description}</p>
      </div>
      <div className="divide-y divide-zinc-700">
        {modes.map((mode) => (
          <div key={mode.code} className="flex items-center justify-between px-4 py-2">
            <div className="flex items-center gap-2">
              <span className="text-zinc-400 text-sm">{mode.code}</span>
              <span className="text-zinc-300 text-sm">{mode.name}</span>
            </div>
            {mode.rate !== null ? (
              <span className={`text-sm font-medium ${mode.rate >= 95 ? 'text-emerald-400' : mode.rate >= 60 ? 'text-amber-400' : 'text-red-400'}`}>
                {mode.rate}%
              </span>
            ) : (
              <span className="text-zinc-500 text-sm">TBD</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function ImprovementItem({
  code,
  name,
  before,
  after,
  technique,
}: {
  code: string
  name: string
  before: number
  after: number
  technique: string
}) {
  return (
    <div className="bg-zinc-800 rounded-lg p-4 border border-zinc-700">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-emerald-400 text-sm">{code}</span>
          <span className="text-white">{name}</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-zinc-500">{before}%</span>
          <ArrowRight size={14} className="text-emerald-400" />
          <span className="text-emerald-400 font-semibold">{after}%</span>
        </div>
      </div>
      <p className="text-zinc-400 text-sm">{technique}</p>
    </div>
  )
}
