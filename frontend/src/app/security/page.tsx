'use client'

export const dynamic = 'force-dynamic'

import { useState, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  Shield, AlertTriangle, CheckCircle, XCircle,
  Search, Brain, Database, DollarSign, Loader2, WifiOff
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { createApiClient, InjectionCheckResult, HallucinationCheckResult, OverflowCheckResult, CostCalculation } from '@/lib/api'
import {
  generateDemoInjectionCheck,
  generateDemoHallucinationCheck,
  generateDemoOverflowCheck,
  generateDemoCostCalculation,
} from '@/lib/demo-data'

type CheckType = 'injection' | 'hallucination' | 'overflow' | 'cost'

interface CheckInfo {
  id: CheckType
  name: string
  description: string
  icon: React.ReactNode
}

const CHECK_TYPES: CheckInfo[] = [
  { id: 'injection', name: 'Prompt Injection', description: 'Detect injection attacks in user input', icon: <AlertTriangle size={20} /> },
  { id: 'hallucination', name: 'Hallucination', description: 'Check if output is grounded in sources', icon: <Brain size={20} /> },
  { id: 'overflow', name: 'Context Overflow', description: 'Monitor token usage and context limits', icon: <Database size={20} /> },
  { id: 'cost', name: 'Cost Calculation', description: 'Calculate API usage costs', icon: <DollarSign size={20} /> },
]

export default function SecurityPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [selectedCheck, setSelectedCheck] = useState<CheckType>('injection')
  const [isChecking, setIsChecking] = useState(false)
  const [isDemoMode, setIsDemoMode] = useState(false)

  // Injection check state
  const [injectionText, setInjectionText] = useState('')
  const [injectionContext, setInjectionContext] = useState('')
  const [injectionResult, setInjectionResult] = useState<InjectionCheckResult | null>(null)

  // Hallucination check state
  const [hallucinationOutput, setHallucinationOutput] = useState('')
  const [hallucinationSources, setHallucinationSources] = useState('')
  const [hallucinationResult, setHallucinationResult] = useState<HallucinationCheckResult | null>(null)

  // Overflow check state
  const [overflowTokens, setOverflowTokens] = useState(4000)
  const [overflowModel, setOverflowModel] = useState('gpt-4')
  const [overflowResult, setOverflowResult] = useState<OverflowCheckResult | null>(null)

  // Cost check state
  const [costModel, setCostModel] = useState('gpt-4')
  const [costInputTokens, setCostInputTokens] = useState(1000)
  const [costOutputTokens, setCostOutputTokens] = useState(500)
  const [costResult, setCostResult] = useState<CostCalculation | null>(null)

  const [error, setError] = useState<string | null>(null)

  const runCheck = useCallback(async () => {
    setIsChecking(true)
    setError(null)
    setIsDemoMode(false)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      switch (selectedCheck) {
        case 'injection':
          if (!injectionText.trim()) {
            setError('Please enter text to check')
            break
          }
          const injRes = await api.checkInjection(injectionText, injectionContext || undefined)
          setInjectionResult(injRes)
          break

        case 'hallucination':
          if (!hallucinationOutput.trim()) {
            setError('Please enter output to check')
            break
          }
          const sources = hallucinationSources.trim()
            ? hallucinationSources.split('\n').filter(s => s.trim())
            : undefined
          const halRes = await api.checkHallucination(hallucinationOutput, sources)
          setHallucinationResult(halRes)
          break

        case 'overflow':
          const ovfRes = await api.checkOverflow(overflowTokens, overflowModel)
          setOverflowResult(ovfRes)
          break

        case 'cost':
          const costRes = await api.calculateCost(costModel, costInputTokens, costOutputTokens)
          setCostResult(costRes)
          break
      }
    } catch (err) {
      console.error('Check failed, falling back to demo mode:', err)

      // Fall back to demo data
      switch (selectedCheck) {
        case 'injection':
          if (!injectionText.trim()) {
            setError('Please enter text to check')
            break
          }
          setInjectionResult(generateDemoInjectionCheck(injectionText))
          setIsDemoMode(true)
          break

        case 'hallucination':
          if (!hallucinationOutput.trim()) {
            setError('Please enter output to check')
            break
          }
          setHallucinationResult(generateDemoHallucinationCheck())
          setIsDemoMode(true)
          break

        case 'overflow':
          setOverflowResult(generateDemoOverflowCheck(overflowModel))
          setIsDemoMode(true)
          break

        case 'cost':
          setCostResult(generateDemoCostCalculation(costModel))
          setIsDemoMode(true)
          break
      }
    }
    setIsChecking(false)
  }, [selectedCheck, injectionText, injectionContext, hallucinationOutput, hallucinationSources, overflowTokens, overflowModel, costModel, costInputTokens, costOutputTokens, getToken, tenantId])

  const clearResults = () => {
    setInjectionResult(null)
    setHallucinationResult(null)
    setOverflowResult(null)
    setCostResult(null)
    setError(null)
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-400 bg-red-400/10'
      case 'high': return 'text-orange-400 bg-orange-400/10'
      case 'medium': return 'text-amber-400 bg-amber-400/10'
      case 'low': return 'text-emerald-400 bg-emerald-400/10'
      default: return 'text-zinc-400 bg-zinc-400/10'
    }
  }

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-red-600/20 rounded-lg">
              <Shield className="w-6 h-6 text-red-400" />
            </div>
            <h1 className="text-2xl font-bold text-white">Security Checks</h1>
            {isDemoMode && (
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30">
                <WifiOff size={14} className="text-amber-400" />
                <span className="text-xs font-medium text-amber-200">Demo Mode</span>
              </div>
            )}
          </div>
          <p className="text-zinc-400">
            Detect prompt injection, hallucinations, and monitor resource usage
          </p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Check Type Selection */}
          <div className="space-y-4">
            <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
              <h3 className="text-sm font-medium text-zinc-300 mb-3">Check Type</h3>
              <div className="space-y-2">
                {CHECK_TYPES.map((check) => (
                  <button
                    key={check.id}
                    onClick={() => {
                      setSelectedCheck(check.id)
                      clearResults()
                    }}
                    className={`w-full p-3 rounded-lg border text-left transition-all ${
                      selectedCheck === check.id
                        ? 'border-red-500 bg-red-500/10'
                        : 'border-zinc-600 bg-zinc-700/50 hover:border-zinc-500'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className={selectedCheck === check.id ? 'text-red-400' : 'text-zinc-400'}>
                        {check.icon}
                      </span>
                      <div>
                        <span className="text-white text-sm font-medium">{check.name}</span>
                        <p className="text-zinc-500 text-xs">{check.description}</p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Input Section */}
          <div className="space-y-4">
            {selectedCheck === 'injection' && (
              <>
                <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
                  <label className="text-sm font-medium text-zinc-300 block mb-2">
                    Text to Check *
                  </label>
                  <textarea
                    value={injectionText}
                    onChange={(e) => setInjectionText(e.target.value)}
                    placeholder="Enter user input or prompt to check for injection attacks..."
                    className="w-full h-32 bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm resize-none focus:border-red-500 focus:outline-none"
                  />
                </div>
                <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
                  <label className="text-sm font-medium text-zinc-300 block mb-2">
                    Context (Optional)
                  </label>
                  <textarea
                    value={injectionContext}
                    onChange={(e) => setInjectionContext(e.target.value)}
                    placeholder="Provide additional context..."
                    className="w-full h-20 bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm resize-none focus:border-red-500 focus:outline-none"
                  />
                </div>
              </>
            )}

            {selectedCheck === 'hallucination' && (
              <>
                <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
                  <label className="text-sm font-medium text-zinc-300 block mb-2">
                    LLM Output to Check *
                  </label>
                  <textarea
                    value={hallucinationOutput}
                    onChange={(e) => setHallucinationOutput(e.target.value)}
                    placeholder="Enter the LLM output to check for hallucinations..."
                    className="w-full h-32 bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm resize-none focus:border-red-500 focus:outline-none"
                  />
                </div>
                <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
                  <label className="text-sm font-medium text-zinc-300 block mb-2">
                    Sources (One per line)
                  </label>
                  <textarea
                    value={hallucinationSources}
                    onChange={(e) => setHallucinationSources(e.target.value)}
                    placeholder="Enter source documents/facts for grounding..."
                    className="w-full h-24 bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm resize-none focus:border-red-500 focus:outline-none"
                  />
                </div>
              </>
            )}

            {selectedCheck === 'overflow' && (
              <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700 space-y-4">
                <div>
                  <label className="text-sm font-medium text-zinc-300 block mb-2">
                    Model
                  </label>
                  <select
                    value={overflowModel}
                    onChange={(e) => setOverflowModel(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm focus:border-red-500 focus:outline-none"
                  >
                    <option value="gpt-4">GPT-4 (8K)</option>
                    <option value="gpt-4-32k">GPT-4 (32K)</option>
                    <option value="gpt-4-turbo">GPT-4 Turbo (128K)</option>
                    <option value="gpt-4o">GPT-4o (128K)</option>
                    <option value="claude-3-opus">Claude 3 Opus (200K)</option>
                    <option value="claude-3-sonnet">Claude 3 Sonnet (200K)</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-300 block mb-2">
                    Current Token Count: {overflowTokens.toLocaleString()}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="200000"
                    step="1000"
                    value={overflowTokens}
                    onChange={(e) => setOverflowTokens(Number(e.target.value))}
                    className="w-full accent-red-500"
                  />
                </div>
              </div>
            )}

            {selectedCheck === 'cost' && (
              <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700 space-y-4">
                <div>
                  <label className="text-sm font-medium text-zinc-300 block mb-2">
                    Model
                  </label>
                  <select
                    value={costModel}
                    onChange={(e) => setCostModel(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm focus:border-red-500 focus:outline-none"
                  >
                    <option value="gpt-4">GPT-4</option>
                    <option value="gpt-4-turbo">GPT-4 Turbo</option>
                    <option value="gpt-4o">GPT-4o</option>
                    <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                    <option value="claude-3-opus">Claude 3 Opus</option>
                    <option value="claude-3-sonnet">Claude 3 Sonnet</option>
                    <option value="claude-3-haiku">Claude 3 Haiku</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-300 block mb-2">
                    Input Tokens: {costInputTokens.toLocaleString()}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="100000"
                    step="100"
                    value={costInputTokens}
                    onChange={(e) => setCostInputTokens(Number(e.target.value))}
                    className="w-full accent-red-500"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-300 block mb-2">
                    Output Tokens: {costOutputTokens.toLocaleString()}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="50000"
                    step="100"
                    value={costOutputTokens}
                    onChange={(e) => setCostOutputTokens(Number(e.target.value))}
                    className="w-full accent-red-500"
                  />
                </div>
              </div>
            )}

            {error && (
              <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <Button
              onClick={runCheck}
              disabled={isChecking}
              loading={isChecking}
              className="w-full"
              leftIcon={<Search size={16} />}
            >
              {isChecking ? 'Checking...' : 'Run Check'}
            </Button>
          </div>

          {/* Results Section */}
          <div>
            {injectionResult && (
              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">Injection Check</h2>
                  {injectionResult.detected ? (
                    <XCircle className="text-red-400" size={24} />
                  ) : (
                    <CheckCircle className="text-emerald-400" size={24} />
                  )}
                </div>

                <div className={`p-4 rounded-lg mb-4 ${injectionResult.detected ? 'bg-red-500/10' : 'bg-emerald-500/10'}`}>
                  <span className={injectionResult.detected ? 'text-red-400' : 'text-emerald-400'}>
                    {injectionResult.detected ? 'Injection Detected!' : 'No Injection Detected'}
                  </span>
                </div>

                {injectionResult.detected && (
                  <>
                    <div className="space-y-3">
                      <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                        <span className="text-zinc-400">Attack Type</span>
                        <span className="text-white">{injectionResult.attack_type || 'Unknown'}</span>
                      </div>
                      <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                        <span className="text-zinc-400">Confidence</span>
                        <span className="text-white">{(injectionResult.confidence * 100).toFixed(1)}%</span>
                      </div>
                      <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                        <span className="text-zinc-400">Severity</span>
                        <span className={`px-2 py-0.5 rounded-full text-xs ${getSeverityColor(injectionResult.severity)}`}>
                          {injectionResult.severity}
                        </span>
                      </div>
                    </div>
                    {injectionResult.matched_patterns.length > 0 && (
                      <div className="mt-4 p-3 bg-zinc-900 rounded-lg">
                        <span className="text-zinc-500 text-sm">Matched Patterns:</span>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {injectionResult.matched_patterns.map((p, i) => (
                            <span key={i} className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs font-mono">
                              {p}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {hallucinationResult && (
              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">Hallucination Check</h2>
                  {hallucinationResult.detected ? (
                    <XCircle className="text-red-400" size={24} />
                  ) : (
                    <CheckCircle className="text-emerald-400" size={24} />
                  )}
                </div>

                <div className={`p-4 rounded-lg mb-4 ${hallucinationResult.detected ? 'bg-amber-500/10' : 'bg-emerald-500/10'}`}>
                  <span className={hallucinationResult.detected ? 'text-amber-400' : 'text-emerald-400'}>
                    {hallucinationResult.detected ? 'Potential Hallucination' : 'Output is Grounded'}
                  </span>
                </div>

                <div className="space-y-3">
                  <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                    <span className="text-zinc-400">Grounding Score</span>
                    <span className={`${hallucinationResult.grounding_score >= 0.8 ? 'text-emerald-400' : hallucinationResult.grounding_score >= 0.6 ? 'text-amber-400' : 'text-red-400'}`}>
                      {(hallucinationResult.grounding_score * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                    <span className="text-zinc-400">Confidence</span>
                    <span className="text-white">{(hallucinationResult.confidence * 100).toFixed(1)}%</span>
                  </div>
                  {hallucinationResult.hallucination_type && (
                    <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                      <span className="text-zinc-400">Type</span>
                      <span className="text-white">{hallucinationResult.hallucination_type}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {overflowResult && (
              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">Context Overflow</h2>
                  <span className={`px-2 py-0.5 rounded-full text-xs ${getSeverityColor(overflowResult.severity)}`}>
                    {overflowResult.severity}
                  </span>
                </div>

                <div className="mb-4">
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-zinc-400">Usage</span>
                    <span className={`${overflowResult.usage_percent >= 90 ? 'text-red-400' : overflowResult.usage_percent >= 70 ? 'text-amber-400' : 'text-emerald-400'}`}>
                      {overflowResult.usage_percent.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-zinc-600 rounded-full h-3">
                    <div
                      className={`h-3 rounded-full ${overflowResult.usage_percent >= 90 ? 'bg-red-400' : overflowResult.usage_percent >= 70 ? 'bg-amber-400' : 'bg-emerald-400'}`}
                      style={{ width: `${Math.min(overflowResult.usage_percent, 100)}%` }}
                    />
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                    <span className="text-zinc-400">Current Tokens</span>
                    <span className="text-white">{overflowResult.current_tokens.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                    <span className="text-zinc-400">Context Window</span>
                    <span className="text-white">{overflowResult.context_window.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                    <span className="text-zinc-400">Remaining</span>
                    <span className="text-white">{overflowResult.remaining_tokens.toLocaleString()}</span>
                  </div>
                </div>

                {overflowResult.warnings.length > 0 && (
                  <div className="mt-4 p-3 bg-amber-500/10 rounded-lg">
                    <span className="text-amber-400 text-sm font-medium">Warnings:</span>
                    <ul className="mt-2 space-y-1">
                      {overflowResult.warnings.map((w, i) => (
                        <li key={i} className="text-amber-300 text-sm">{w}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {costResult && (
              <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
                <h2 className="text-lg font-semibold text-white mb-4">Cost Calculation</h2>

                <div className="p-4 bg-emerald-500/10 rounded-lg mb-4">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-300">Total Cost</span>
                    <span className="text-2xl font-bold text-emerald-400">
                      ${costResult.total_cost_usd.toFixed(4)}
                    </span>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                    <span className="text-zinc-400">Model</span>
                    <span className="text-white">{costResult.model}</span>
                  </div>
                  <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                    <span className="text-zinc-400">Provider</span>
                    <span className="text-white">{costResult.provider}</span>
                  </div>
                  <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                    <span className="text-zinc-400">Input Cost</span>
                    <span className="text-white">${costResult.input_cost_usd.toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                    <span className="text-zinc-400">Output Cost</span>
                    <span className="text-white">${costResult.output_cost_usd.toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
                    <span className="text-zinc-400">Total Tokens</span>
                    <span className="text-white">{costResult.total_tokens.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            )}

            {!injectionResult && !hallucinationResult && !overflowResult && !costResult && (
              <div className="h-full flex items-center justify-center bg-zinc-800/50 rounded-xl border border-zinc-700 border-dashed p-8">
                <div className="text-center text-zinc-500">
                  <Shield className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium mb-2">No results yet</p>
                  <p className="text-sm">Select a check type and run to see results</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  )
}
