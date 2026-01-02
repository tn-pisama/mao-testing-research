'use client'

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useTenant } from '@/hooks/useTenant'
import {
  Zap, Play, Square, AlertTriangle, Clock,
  Target, Shield, Activity, RefreshCw
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { createApiClient, ChaosSession as APIChaosSession, ChaosExperimentType } from '@/lib/api'

interface DisplayExperimentType {
  id: string
  name: string
  description: string
  icon: React.ReactNode
  severity: 'low' | 'medium' | 'high'
}

interface DisplayChaosSession {
  id: string
  experiment: string
  status: 'running' | 'completed' | 'aborted'
  startedAt: string
  affectedAgents: number
  injections: number
}

function getExperimentIcon(type: string): React.ReactNode {
  switch (type) {
    case 'latency': return <Clock size={20} />
    case 'error': return <AlertTriangle size={20} />
    case 'malformed': return <Zap size={20} />
    case 'tool_unavailable': return <Target size={20} />
    case 'uncooperative': return <Shield size={20} />
    case 'context_truncation': return <Activity size={20} />
    default: return <Zap size={20} />
  }
}

function getExperimentSeverity(type: string): 'low' | 'medium' | 'high' {
  if (['latency'].includes(type)) return 'low'
  if (['error', 'malformed', 'tool_unavailable'].includes(type)) return 'medium'
  return 'high'
}

function mapExperimentType(exp: ChaosExperimentType): DisplayExperimentType {
  return {
    id: exp.type,
    name: exp.name,
    description: exp.description,
    icon: getExperimentIcon(exp.type),
    severity: getExperimentSeverity(exp.type)
  }
}

function mapChaosSession(session: APIChaosSession): DisplayChaosSession {
  return {
    id: session.id,
    experiment: session.name,
    status: session.status as 'running' | 'completed' | 'aborted',
    startedAt: session.started_at ? new Date(session.started_at).toLocaleString() : new Date(session.created_at).toLocaleString(),
    affectedAgents: 0, // Would come from session details
    injections: session.experiment_count
  }
}

export default function ChaosPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [experimentTypes, setExperimentTypes] = useState<DisplayExperimentType[]>([])
  const [sessions, setSessions] = useState<DisplayChaosSession[]>([])
  const [selectedExperiment, setSelectedExperiment] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [targetPercentage, setTargetPercentage] = useState(10)
  const [isLoading, setIsLoading] = useState(true)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setIsLoading(true)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      const [expTypesData, sessionsData] = await Promise.all([
        api.getChaosExperimentTypes(),
        api.listChaosSessions()
      ])

      setExperimentTypes(expTypesData.map(mapExperimentType))
      setSessions(sessionsData.map(mapChaosSession))

      // Check if any session is running
      const runningSession = sessionsData.find(s => s.status === 'running')
      if (runningSession) {
        setIsRunning(true)
        setActiveSessionId(runningSession.id)
      }
    } catch (err) {
      console.warn('API unavailable, using fallback data:', err)
      // Fallback to default experiment types
      setExperimentTypes([
        { id: 'latency', name: 'Latency Injection', description: 'Add 1-5s delay to LLM responses', icon: <Clock size={20} />, severity: 'low' },
        { id: 'error', name: 'Error Injection', description: 'Simulate API failures and timeouts', icon: <AlertTriangle size={20} />, severity: 'medium' },
        { id: 'malformed', name: 'Malformed Output', description: 'Return truncated or corrupted responses', icon: <Zap size={20} />, severity: 'medium' },
        { id: 'tool_unavailable', name: 'Tool Unavailable', description: 'Simulate tool/function failures', icon: <Target size={20} />, severity: 'medium' },
        { id: 'uncooperative', name: 'Uncooperative Agent', description: 'Agent refuses tasks or gives irrelevant responses', icon: <Shield size={20} />, severity: 'high' },
        { id: 'context_truncation', name: 'Context Truncation', description: 'Simulate context window overflow', icon: <Activity size={20} />, severity: 'high' },
      ])
      setSessions([])
    }
    setIsLoading(false)
  }, [getToken, tenantId])

  useEffect(() => {
    loadData()
  }, [loadData])

  const startExperiment = async () => {
    if (!selectedExperiment) return
    setIsRunning(true)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      const expType = experimentTypes.find(e => e.id === selectedExperiment)
      const session = await api.createChaosSession(
        `${expType?.name || 'Chaos'} - ${new Date().toLocaleString()}`,
        [{
          experiment_type: selectedExperiment,
          name: expType?.name || 'Experiment',
          probability: targetPercentage / 100
        }],
        { percentage: targetPercentage },
        { auto_abort_on_cascade: true, max_blast_radius: 'tenant' }
      )

      await api.startChaosSession(session.id)
      setActiveSessionId(session.id)

      // Refresh sessions list
      const sessionsData = await api.listChaosSessions()
      setSessions(sessionsData.map(mapChaosSession))
    } catch (err) {
      console.error('Failed to start experiment:', err)
      setIsRunning(false)
    }
  }

  const stopExperiment = async () => {
    if (!activeSessionId) {
      setIsRunning(false)
      return
    }

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.stopChaosSession(activeSessionId)

      // Refresh sessions list
      const sessionsData = await api.listChaosSessions()
      setSessions(sessionsData.map(mapChaosSession))
    } catch (err) {
      console.error('Failed to stop experiment:', err)
    }

    setIsRunning(false)
    setActiveSessionId(null)
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
                {experimentTypes.find(e => e.id === selectedExperiment)?.name} -
                Targeting {targetPercentage}% of traffic
              </p>
            </div>
          </div>
        )}

        <div className="grid lg:grid-cols-3 gap-6 mb-6">
          <div className="lg:col-span-2">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
              <h2 className="text-lg font-semibold text-white mb-4">Experiment Types</h2>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-400"></div>
                </div>
              ) : (
              <div className="grid md:grid-cols-2 gap-3">
                {experimentTypes.map((exp) => (
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
              )}
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
                  <span className="text-slate-400">Total Sessions</span>
                  <span className="text-white font-mono">{sessions.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Completed</span>
                  <span className="text-emerald-400 font-mono">{sessions.filter(s => s.status === 'completed').length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Aborted</span>
                  <span className="text-red-400 font-mono">{sessions.filter(s => s.status === 'aborted').length}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Sessions</h2>
          <div className="space-y-2">
            {sessions.length === 0 ? (
              <p className="text-slate-500 text-center py-4">No chaos sessions yet</p>
            ) : sessions.map((session) => (
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

