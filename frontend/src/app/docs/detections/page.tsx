import { 
  AlertTriangle, 
  RefreshCw, 
  Shield, 
  Eye, 
  Zap, 
  CheckCircle,
  XCircle,
  HelpCircle,
  TrendingUp,
} from 'lucide-react'

export default function DetectionsPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-4">Detections</h1>
        <p className="text-lg text-slate-300">
          Understanding the failure patterns Pisama detects and how to interpret them.
        </p>
      </div>

      <div className="mb-8 p-4 rounded-xl bg-primary-600/10 border border-primary-500/30">
        <p className="text-sm text-slate-300">
          For a complete reference of all 21 failure mode detectors including examples, detection methods, and accuracy metrics, see the{' '}
          <a href="/docs/failure-modes" className="text-primary-400 hover:underline font-medium">Failure Modes Reference</a>.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Detection Types</h2>
        <p className="text-slate-300 mb-6">
          Pisama identifies four primary categories of multi-agent failures:
        </p>

        <div className="space-y-6">
          <DetectionTypeCard
            icon={RefreshCw}
            title="Infinite Loop"
            severity="critical"
            description="Agents stuck repeating the same sequence of actions without making progress toward the goal."
            examples={[
              "Agent A asks Agent B for clarification, B asks A, creating endless back-and-forth",
              "Tool call returns error, agent retries indefinitely without changing approach",
              "State oscillates between two values without converging",
            ]}
            methods={[
              { name: "Structural Matching", description: "Detects repeated action sequences" },
              { name: "Hash Collision", description: "Identifies identical state hashes" },
              { name: "Semantic Clustering", description: "Groups semantically similar messages" },
            ]}
          />

          <DetectionTypeCard
            icon={Shield}
            title="State Corruption"
            severity="high"
            description="Agent state drifts from expected values or contains inconsistent/invalid data."
            examples={[
              "Numeric field contains string value after transformation",
              "Required context lost during agent handoff",
              "Accumulated context exceeds coherent limits",
            ]}
            methods={[
              { name: "Schema Validation", description: "Checks state against expected types" },
              { name: "Semantic Analysis", description: "Detects meaning drift in text fields" },
              { name: "Cross-field Validation", description: "Ensures field relationships are consistent" },
            ]}
          />

          <DetectionTypeCard
            icon={Eye}
            title="Persona Drift"
            severity="medium"
            description="Agent deviates from its intended role, personality, or behavioral constraints."
            examples={[
              "Helper agent starts making unauthorized decisions",
              "Formal agent adopts casual tone mid-conversation",
              "Agent exceeds scope of assigned responsibilities",
            ]}
            methods={[
              { name: "Role Embedding", description: "Compares behavior to role definition" },
              { name: "Constraint Checking", description: "Validates against behavioral rules" },
              { name: "Tone Analysis", description: "Monitors communication style consistency" },
            ]}
          />

          <DetectionTypeCard
            icon={Zap}
            title="Coordination Deadlock"
            severity="critical"
            description="Multiple agents waiting on each other, preventing any progress."
            examples={[
              "Agent A waits for B's output, B waits for A's approval",
              "Resource lock held indefinitely by crashed agent",
              "Circular dependency in task delegation chain",
            ]}
            methods={[
              { name: "Dependency Graph", description: "Analyzes wait relationships" },
              { name: "Timeout Detection", description: "Identifies stalled operations" },
              { name: "Progress Tracking", description: "Monitors advancement metrics" },
            ]}
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Confidence Scores</h2>
        <p className="text-slate-300 mb-4">
          Each detection includes a confidence score (0-100%) indicating how certain the system
          is that this is a genuine failure versus normal behavior:
        </p>

        <div className="grid md:grid-cols-3 gap-4">
          <ConfidenceCard
            range="90-100%"
            label="High Confidence"
            color="text-red-400"
            bgColor="bg-red-500/20"
            description="Very likely a real failure. Immediate investigation recommended."
          />
          <ConfidenceCard
            range="70-89%"
            label="Medium Confidence"
            color="text-amber-400"
            bgColor="bg-amber-500/20"
            description="Probable failure. Review when convenient."
          />
          <ConfidenceCard
            range="50-69%"
            label="Low Confidence"
            color="text-slate-400"
            bgColor="bg-slate-500/20"
            description="Possible false positive. May be normal behavior."
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Validating Detections</h2>
        <p className="text-slate-300 mb-4">
          After reviewing a detection, you can validate it to improve future accuracy:
        </p>

        <div className="grid md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle size={18} className="text-emerald-400" />
              <h3 className="font-semibold text-emerald-400">Confirm as Valid</h3>
            </div>
            <p className="text-sm text-slate-300">
              Mark the detection as a genuine failure. This trains the system to catch
              similar patterns with higher confidence.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-500/10 border border-slate-500/30">
            <div className="flex items-center gap-2 mb-2">
              <XCircle size={18} className="text-slate-400" />
              <h3 className="font-semibold text-slate-400">Mark as False Positive</h3>
            </div>
            <p className="text-sm text-slate-300">
              Flag as normal behavior incorrectly flagged. Helps reduce noise in
              future detections.
            </p>
          </div>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Severity Levels</h2>
        <p className="text-slate-300 mb-4">
          Detections are categorized by potential impact:
        </p>

        <div className="space-y-3">
          <SeverityRow level="Critical" color="text-red-400" dot="bg-red-500" description="System failure imminent or occurring. Requires immediate action." />
          <SeverityRow level="High" color="text-orange-400" dot="bg-orange-500" description="Significant degradation likely. Address within hours." />
          <SeverityRow level="Medium" color="text-amber-400" dot="bg-amber-500" description="Potential issue developing. Monitor and plan remediation." />
          <SeverityRow level="Low" color="text-slate-400" dot="bg-slate-500" description="Minor anomaly detected. Review during regular maintenance." />
        </div>
      </section>

      <section className="bg-slate-800/50 rounded-xl border border-slate-700 p-6">
        <div className="flex items-start gap-3">
          <HelpCircle size={20} className="text-primary-400 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-white mb-2">Need Help Interpreting Detections?</h3>
            <p className="text-sm text-slate-300">
              Each detection in the dashboard includes detailed context about what triggered it,
              which agents were involved, and the specific state at the time of detection.
              Click on any detection to see the full trace and timeline.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}

function DetectionTypeCard({
  icon: Icon,
  title,
  severity,
  description,
  examples,
  methods,
}: {
  icon: typeof AlertTriangle
  title: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  description: string
  examples: string[]
  methods: { name: string; description: string }[]
}) {
  const severityColors = {
    critical: 'border-red-500/30 bg-red-500/5',
    high: 'border-orange-500/30 bg-orange-500/5',
    medium: 'border-amber-500/30 bg-amber-500/5',
    low: 'border-slate-500/30 bg-slate-500/5',
  }

  return (
    <div className={`rounded-xl border p-6 ${severityColors[severity]}`}>
      <div className="flex items-center gap-3 mb-3">
        <div className="p-2 rounded-lg bg-slate-800">
          <Icon size={20} className="text-primary-400" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <span className="text-xs text-slate-400 uppercase">{severity} severity</span>
        </div>
      </div>

      <p className="text-slate-300 mb-4">{description}</p>

      <div className="mb-4">
        <h4 className="text-sm font-medium text-slate-400 mb-2">Common Examples:</h4>
        <ul className="space-y-1">
          {examples.map((example, i) => (
            <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
              <span className="text-slate-500">•</span>
              {example}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h4 className="text-sm font-medium text-slate-400 mb-2">Detection Methods:</h4>
        <div className="flex flex-wrap gap-2">
          {methods.map((method) => (
            <span
              key={method.name}
              className="px-2 py-1 text-xs rounded bg-slate-800 text-slate-300"
              title={method.description}
            >
              {method.name}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

function ConfidenceCard({
  range,
  label,
  color,
  bgColor,
  description,
}: {
  range: string
  label: string
  color: string
  bgColor: string
  description: string
}) {
  return (
    <div className={`p-4 rounded-xl border border-slate-700 ${bgColor}`}>
      <div className={`text-2xl font-bold ${color} mb-1`}>{range}</div>
      <div className="font-medium text-white mb-2">{label}</div>
      <p className="text-sm text-slate-400">{description}</p>
    </div>
  )
}

function SeverityRow({
  level,
  color,
  dot,
  description,
}: {
  level: string
  color: string
  dot: string
  description: string
}) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-800/50">
      <div className={`w-3 h-3 rounded-full ${dot}`} />
      <span className={`font-medium w-20 ${color}`}>{level}</span>
      <span className="text-sm text-slate-400">{description}</span>
    </div>
  )
}
