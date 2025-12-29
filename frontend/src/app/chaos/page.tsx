'use client'

import { useState } from 'react'
import { 
  Zap, Play, Square, AlertTriangle, Clock, 
  Target, Shield, Activity, RefreshCw 
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'

interface ExperimentType {
  id: string
  name: string
  description: string
  icon: React.ReactNode
  severity: 'low' | 'medium' | 'high'
}

interface ChaosSession {
  id: string
  experiment: string
  status: 'running' | 'completed' | 'aborted'
  startedAt: string
  affectedAgents: number
  injections: number
}

const EXPERIMENT_TYPES: ExperimentType[] = [
  { 
    id: 'latency', 
    name: 'Latency Injection', 
    description: 'Add 1-5s delay to LLM responses',
    icon: <Clock size={20} />,
    severity: 'low'
  },
  { 
    id: 'error', 
    name: 'Error Injection', 
    description: 'Simulate API failures and timeouts',
    icon: <AlertTriangle size={20} />,
    severity: 'medium'
  },
  { 
    id: 'malformed', 
    name: 'Malformed Output', 
    description: 'Return truncated or corrupted responses',
    icon: <Zap size={20} />,
    severity: 'medium'
  },
  { 
    id: 'tool_unavailable', 
    name: 'Tool Unavailable', 
    description: 'Simulate tool/function failures',
    icon: <Target size={20} />,
    severity: 'medium'
  },
  { 
    id: 'uncooperative', 
    name: 'Uncooperative Agent', 
    description: 'Agent refuses tasks or gives irrelevant responses',
    icon: <Shield size={20} />,
    severity: 'high'
  },
  { 
    id: 'context_truncation', 
    name: 'Context Truncation', 
    description: 'Simulate context window overflow',
    icon: <Activity size={20} />,
    severity: 'high'
  },
]

const RECENT_SESSIONS: ChaosSession[] = [
  { 
    id: 'cs-001', 
    experiment: 'Latency Injection', 
    status: 'completed', 
    startedAt: '2024-12-29 10:30',
    affectedAgents: 3,
    injections: 47
  },
  { 
    id: 'cs-002', 
    experiment: 'Error Injection', 
    status: 'completed', 
    startedAt: '2024-12-29 09:15',
    affectedAgents: 2,
    injections: 23
  },
  { 
    id: 'cs-003', 
    experiment: 'Tool Unavailable', 
    status: 'aborted', 
    startedAt: '2024-12-28 16:45',
    affectedAgents: 1,
    injections: 8
  },
]

export default function ChaosPage() {
  const [selectedExperiment, setSelectedExperiment] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [targetPercentage, setTargetPercentage] = useState(10)

  const startExperiment = () => {
    if (!selectedExperiment) return
    setIsRunning(true)
  }

  const stopExperiment = () => {
    setIsRunning(false)
  }

  const severityColor = (severity: string) => {
    switch (severity) {
      case 'low': return 'text-emerald-400 bg-emerald-400/10'
      case 'medium': return 'text-amber-400 bg-amber-400/10'
      case 'high': return 'text-red-400 bg-red-400/10'
      default: return 'text-slate-400 bg-slate-400/10'
    }
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Zap className="text-amber-400" />
              Chaos Engineering
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Test agent resilience with controlled failure injection
            </p>
          </div>
          {isRunning ? (
            <Button variant="danger" onClick={stopExperiment} leftIcon={<Square size={16} />}>
              Stop Experiment
            </Button>
          ) : (
            <Button 
              onClick={startExperiment} 
              disabled={!selectedExperiment}
              leftIcon={<Play size={16} />}
            >
              Start Experiment
            </Button>
          )}
        </div>

        {isRunning && (
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 mb-6 flex items-center gap-4">
            <RefreshCw className="text-amber-400 animate-spin" size={24} />
            <div>
              <p className="text-amber-400 font-medium">Chaos Experiment Running</p>
              <p className="text-amber-400/70 text-sm">
                {EXPERIMENT_TYPES.find(e => e.id === selectedExperiment)?.name} - 
                Targeting {targetPercentage}% of traffic
              </p>
            </div>
          </div>
        )}

        <div className="grid lg:grid-cols-3 gap-6 mb-6">
          <div className="lg:col-span-2">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
              <h2 className="text-lg font-semibold text-white mb-4">Experiment Types</h2>
              <div className="grid md:grid-cols-2 gap-3">
                {EXPERIMENT_TYPES.map((exp) => (
                  <button
                    key={exp.id}
                    onClick={() => setSelectedExperiment(exp.id)}
                    disabled={isRunning}
                    className={`p-4 rounded-lg border text-left transition-all ${
                      selectedExperiment === exp.id
                        ? 'border-primary-500 bg-primary-500/10'
                        : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                    } ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`p-2 rounded-lg ${severityColor(exp.severity)}`}>
                        {exp.icon}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <span className="text-white font-medium">{exp.name}</span>
                          <span className={`text-xs px-2 py-0.5 rounded-full ${severityColor(exp.severity)}`}>
                            {exp.severity}
                          </span>
                        </div>
                        <p className="text-slate-400 text-sm mt-1">{exp.description}</p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
              <h2 className="text-lg font-semibold text-white mb-4">Blast Radius</h2>
              <div className="space-y-4">
                <div>
                  <label className="text-slate-400 text-sm block mb-2">
                    Target Percentage: {targetPercentage}%
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="100"
                    value={targetPercentage}
                    onChange={(e) => setTargetPercentage(Number(e.target.value))}
                    disabled={isRunning}
                    className="w-full accent-primary-500"
                  />
                  <div className="flex justify-between text-xs text-slate-500 mt-1">
                    <span>1%</span>
                    <span>50%</span>
                    <span>100%</span>
                  </div>
                </div>
                <div className="pt-4 border-t border-slate-700">
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-slate-400">Safety Threshold</span>
                    <span className="text-emerald-400">Active</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Auto-Abort</span>
                    <span className="text-emerald-400">Enabled</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
              <h2 className="text-lg font-semibold text-white mb-4">Statistics</h2>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-slate-400">Total Experiments</span>
                  <span className="text-white font-mono">24</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Failures Discovered</span>
                  <span className="text-amber-400 font-mono">12</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Avg Recovery Time</span>
                  <span className="text-white font-mono">2.3s</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Sessions</h2>
          <div className="space-y-2">
            {RECENT_SESSIONS.map((session) => (
              <div 
                key={session.id}
                className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg"
              >
                <div className="flex items-center gap-4">
                  <span className={`w-2 h-2 rounded-full ${
                    session.status === 'running' ? 'bg-amber-400 animate-pulse' :
                    session.status === 'completed' ? 'bg-emerald-400' : 'bg-red-400'
                  }`} />
                  <div>
                    <span className="text-white">{session.experiment}</span>
                    <span className="text-slate-500 text-sm ml-2">{session.startedAt}</span>
                  </div>
                </div>
                <div className="flex items-center gap-6 text-sm">
                  <span className="text-slate-400">
                    {session.affectedAgents} agents
                  </span>
                  <span className="text-slate-400">
                    {session.injections} injections
                  </span>
                  <span className={`px-2 py-0.5 rounded-full text-xs ${
                    session.status === 'completed' ? 'bg-emerald-400/10 text-emerald-400' :
                    session.status === 'aborted' ? 'bg-red-400/10 text-red-400' :
                    'bg-amber-400/10 text-amber-400'
                  }`}>
                    {session.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  )
}
