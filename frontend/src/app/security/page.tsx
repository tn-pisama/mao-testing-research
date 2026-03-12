'use client'

export const dynamic = 'force-dynamic'

import { useState, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  Shield, AlertTriangle, Search, Brain, Database, DollarSign, WifiOff
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
import { InjectionCheckForm, InjectionCheckResult as InjectionResult } from '@/components/security/InjectionCheck'
import { HallucinationCheckForm, HallucinationCheckResult as HallucinationResult } from '@/components/security/HallucinationCheck'
import { OverflowCheckForm, OverflowCheckResult as OverflowResult } from '@/components/security/OverflowCheck'
import { CostCheckForm, CostCheckResult } from '@/components/security/CostCheck'

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
              <InjectionCheckForm text={injectionText} setText={setInjectionText} context={injectionContext} setContext={setInjectionContext} />
            )}
            {selectedCheck === 'hallucination' && (
              <HallucinationCheckForm output={hallucinationOutput} setOutput={setHallucinationOutput} sources={hallucinationSources} setSources={setHallucinationSources} />
            )}
            {selectedCheck === 'overflow' && (
              <OverflowCheckForm model={overflowModel} setModel={setOverflowModel} tokens={overflowTokens} setTokens={setOverflowTokens} />
            )}
            {selectedCheck === 'cost' && (
              <CostCheckForm model={costModel} setModel={setCostModel} inputTokens={costInputTokens} setInputTokens={setCostInputTokens} outputTokens={costOutputTokens} setOutputTokens={setCostOutputTokens} />
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
            <InjectionResult result={injectionResult} />
            <HallucinationResult result={hallucinationResult} />
            <OverflowResult result={overflowResult} />
            <CostCheckResult result={costResult} />

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
