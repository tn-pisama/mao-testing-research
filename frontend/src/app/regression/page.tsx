'use client'

import { useState } from 'react'
import { 
  GitBranch, TrendingDown, TrendingUp, AlertTriangle,
  CheckCircle, Clock, Database, RefreshCw, Plus
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'

interface Baseline {
  id: string
  name: string
  model: string
  promptCount: number
  createdAt: string
  lastTested: string
}

interface DriftAlert {
  id: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  type: 'semantic' | 'performance' | 'format'
  prompt: string
  similarity: number
  detectedAt: string
}

interface ModelFingerprint {
  model: string
  version: string
  provider: string
  lastSeen: string
  status: 'stable' | 'updated' | 'deprecated'
}

const BASELINES: Baseline[] = [
  {
    id: 'bl-001',
    name: 'Production Prompts v2.1',
    model: 'gpt-4o-2024-08-06',
    promptCount: 47,
    createdAt: '2024-12-15',
    lastTested: '2024-12-29'
  },
  {
    id: 'bl-002',
    name: 'Customer Service Prompts',
    model: 'claude-3-5-sonnet-20241022',
    promptCount: 23,
    createdAt: '2024-12-10',
    lastTested: '2024-12-28'
  },
]

const DRIFT_ALERTS: DriftAlert[] = [
  {
    id: 'da-001',
    severity: 'high',
    type: 'semantic',
    prompt: 'Summarize the following document...',
    similarity: 0.67,
    detectedAt: '2024-12-29 09:15'
  },
  {
    id: 'da-002',
    severity: 'medium',
    type: 'performance',
    prompt: 'Generate a response to customer complaint...',
    similarity: 0.82,
    detectedAt: '2024-12-29 08:30'
  },
  {
    id: 'da-003',
    severity: 'low',
    type: 'format',
    prompt: 'Extract entities from the text...',
    similarity: 0.91,
    detectedAt: '2024-12-28 16:45'
  },
]

const MODEL_FINGERPRINTS: ModelFingerprint[] = [
  { model: 'gpt-4o', version: '2024-08-06', provider: 'OpenAI', lastSeen: '2024-12-29', status: 'stable' },
  { model: 'gpt-4o', version: '2024-11-20', provider: 'OpenAI', lastSeen: '2024-12-29', status: 'updated' },
  { model: 'claude-3-5-sonnet', version: '20241022', provider: 'Anthropic', lastSeen: '2024-12-29', status: 'stable' },
  { model: 'gpt-4-turbo', version: '2024-04-09', provider: 'OpenAI', lastSeen: '2024-12-20', status: 'deprecated' },
]

export default function RegressionPage() {
  const [selectedBaseline, setSelectedBaseline] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)

  const runRegressionTest = () => {
    if (!selectedBaseline) return
    setIsRunning(true)
    setTimeout(() => setIsRunning(false), 3000)
  }

  const severityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-400 bg-red-400/10'
      case 'high': return 'text-orange-400 bg-orange-400/10'
      case 'medium': return 'text-amber-400 bg-amber-400/10'
      case 'low': return 'text-slate-400 bg-slate-400/10'
      default: return 'text-slate-400 bg-slate-400/10'
    }
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <GitBranch className="text-cyan-400" />
              Model Regression Testing
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Detect behavioral drift when models are updated
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" leftIcon={<Plus size={16} />}>
              Create Baseline
            </Button>
            <Button 
              onClick={runRegressionTest}
              disabled={!selectedBaseline || isRunning}
              loading={isRunning}
              leftIcon={<RefreshCw size={16} />}
            >
              {isRunning ? 'Testing...' : 'Run Regression Test'}
            </Button>
          </div>
        </div>

        <div className="grid lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
              <Database size={16} />
              Baselines
            </div>
            <span className="text-2xl font-bold text-white">{BASELINES.length}</span>
          </div>
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
              <AlertTriangle size={16} />
              Active Alerts
            </div>
            <span className="text-2xl font-bold text-amber-400">{DRIFT_ALERTS.length}</span>
          </div>
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
              <TrendingUp size={16} />
              Avg Similarity
            </div>
            <span className="text-2xl font-bold text-emerald-400">94.2%</span>
          </div>
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
              <Clock size={16} />
              Last Test
            </div>
            <span className="text-2xl font-bold text-white">2h ago</span>
          </div>
        </div>

        <div className="grid lg:grid-cols-3 gap-6 mb-6">
          <div className="lg:col-span-2">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6">
              <h2 className="text-lg font-semibold text-white mb-4">Baselines</h2>
              <div className="space-y-2">
                {BASELINES.map((baseline) => (
                  <button
                    key={baseline.id}
                    onClick={() => setSelectedBaseline(baseline.id)}
                    className={`w-full p-4 rounded-lg border text-left transition-all ${
                      selectedBaseline === baseline.id
                        ? 'border-primary-500 bg-primary-500/10'
                        : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-white font-medium">{baseline.name}</span>
                        <div className="flex items-center gap-3 mt-1">
                          <span className="text-slate-500 text-sm font-mono">{baseline.model}</span>
                          <span className="text-slate-500 text-sm">{baseline.promptCount} prompts</span>
                        </div>
                      </div>
                      <div className="text-right text-sm">
                        <div className="text-slate-400">Last tested</div>
                        <div className="text-white">{baseline.lastTested}</div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <AlertTriangle className="text-amber-400" size={20} />
                Drift Alerts
              </h2>
              <div className="space-y-2">
                {DRIFT_ALERTS.map((alert) => (
                  <div 
                    key={alert.id}
                    className="p-4 rounded-lg border border-slate-600 bg-slate-700/30"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs ${severityColor(alert.severity)}`}>
                          {alert.severity}
                        </span>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-white">{alert.type} drift</span>
                            <span className={`text-sm font-mono ${
                              alert.similarity >= 0.9 ? 'text-emerald-400' :
                              alert.similarity >= 0.7 ? 'text-amber-400' : 'text-red-400'
                            }`}>
                              {(alert.similarity * 100).toFixed(0)}% similar
                            </span>
                          </div>
                          <p className="text-slate-400 text-sm mt-1 truncate max-w-md">
                            {alert.prompt}
                          </p>
                        </div>
                      </div>
                      <span className="text-slate-500 text-sm">{alert.detectedAt}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div>
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
              <h2 className="text-lg font-semibold text-white mb-4">Model Fingerprints</h2>
              <div className="space-y-3">
                {MODEL_FINGERPRINTS.map((fp, idx) => (
                  <div 
                    key={idx}
                    className="p-3 rounded-lg bg-slate-700/50 border border-slate-600"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-white font-medium text-sm">{fp.model}</span>
                      <span className={`px-2 py-0.5 rounded-full text-xs ${
                        fp.status === 'stable' ? 'bg-emerald-400/10 text-emerald-400' :
                        fp.status === 'updated' ? 'bg-amber-400/10 text-amber-400' :
                        'bg-red-400/10 text-red-400'
                      }`}>
                        {fp.status}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-400">{fp.provider}</span>
                      <span className="text-slate-500 font-mono">{fp.version}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}
