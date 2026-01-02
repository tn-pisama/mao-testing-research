'use client'

export const dynamic = 'force-dynamic'

import { useState, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useTenant } from '@/hooks/useTenant'
import {
  CheckSquare, Play, Loader2, AlertCircle,
  Sparkles, Target, Shield, MessageSquare
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { createApiClient, EvalResult, QuickEvalResult, LLMJudgeResult } from '@/lib/api'

interface EvalTypeInfo {
  id: string
  name: string
  description: string
  icon: React.ReactNode
}

const EVAL_TYPES: EvalTypeInfo[] = [
  { id: 'relevance', name: 'Relevance', description: 'How relevant is the output to the context?', icon: <Target size={18} /> },
  { id: 'coherence', name: 'Coherence', description: 'Is the output logically coherent?', icon: <MessageSquare size={18} /> },
  { id: 'helpfulness', name: 'Helpfulness', description: 'Is the output helpful to the user?', icon: <Sparkles size={18} /> },
  { id: 'safety', name: 'Safety', description: 'Is the output safe and appropriate?', icon: <Shield size={18} /> },
]

export default function EvalsPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [output, setOutput] = useState('')
  const [context, setContext] = useState('')
  const [expected, setExpected] = useState('')
  const [selectedTypes, setSelectedTypes] = useState<string[]>(['relevance', 'coherence', 'helpfulness', 'safety'])
  const [useLlmJudge, setUseLlmJudge] = useState(false)
  const [threshold, setThreshold] = useState(0.7)
  const [isEvaluating, setIsEvaluating] = useState(false)
  const [result, setResult] = useState<EvalResult | null>(null)
  const [quickResult, setQuickResult] = useState<QuickEvalResult | null>(null)
  const [llmResult, setLlmResult] = useState<LLMJudgeResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [evalMode, setEvalMode] = useState<'full' | 'quick' | 'llm'>('full')

  const toggleEvalType = (typeId: string) => {
    setSelectedTypes(prev =>
      prev.includes(typeId)
        ? prev.filter(t => t !== typeId)
        : [...prev, typeId]
    )
  }

  const runEvaluation = useCallback(async () => {
    if (!output.trim()) {
      setError('Please enter output to evaluate')
      return
    }

    setIsEvaluating(true)
    setError(null)
    setResult(null)
    setQuickResult(null)
    setLlmResult(null)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      if (evalMode === 'quick') {
        const res = await api.quickEval(output, context || undefined)
        setQuickResult(res)
      } else if (evalMode === 'llm') {
        const res = await api.llmJudgeEval(
          output,
          selectedTypes[0] || 'relevance',
          'gpt-4o-mini',
          context || undefined,
          expected || undefined
        )
        setLlmResult(res)
      } else {
        const res = await api.evaluate(
          output,
          selectedTypes,
          context || undefined,
          expected || undefined,
          useLlmJudge,
          threshold
        )
        setResult(res)
      }
    } catch (err) {
      console.error('Evaluation failed:', err)
      setError('Evaluation failed. Please try again.')
    } finally {
      setIsEvaluating(false)
    }
  }, [output, context, expected, selectedTypes, useLlmJudge, threshold, evalMode, getToken, tenantId])

  const clearResults = () => {
    setOutput('')
    setContext('')
    setExpected('')
    setResult(null)
    setQuickResult(null)
    setLlmResult(null)
    setError(null)
  }

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-emerald-400'
    if (score >= 0.6) return 'text-amber-400'
    return 'text-red-400'
  }

  const getScoreBg = (score: number) => {
    if (score >= 0.8) return 'bg-emerald-400/10'
    if (score >= 0.6) return 'bg-amber-400/10'
    return 'bg-red-400/10'
  }

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-emerald-600/20 rounded-lg">
              <CheckSquare className="w-6 h-6 text-emerald-400" />
            </div>
            <h1 className="text-2xl font-bold text-white">Evaluation Framework</h1>
          </div>
          <p className="text-slate-400">
            Evaluate LLM outputs for quality, safety, and relevance
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Input Section */}
          <div className="space-y-4">
            {/* Eval Mode Selection */}
            <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
              <h3 className="text-sm font-medium text-slate-300 mb-3">Evaluation Mode</h3>
              <div className="flex gap-2">
                {[
                  { id: 'full', name: 'Full Eval', desc: 'Multiple criteria' },
                  { id: 'quick', name: 'Quick Eval', desc: 'Fast overview' },
                  { id: 'llm', name: 'LLM Judge', desc: 'AI-powered' },
                ].map((mode) => (
                  <button
                    key={mode.id}
                    onClick={() => setEvalMode(mode.id as typeof evalMode)}
                    className={`flex-1 p-3 rounded-lg border text-left transition-all ${
                      evalMode === mode.id
                        ? 'border-emerald-500 bg-emerald-500/10'
                        : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                    }`}
                  >
                    <span className="text-white text-sm font-medium">{mode.name}</span>
                    <p className="text-slate-500 text-xs mt-0.5">{mode.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Output Input */}
            <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
              <label className="text-sm font-medium text-slate-300 block mb-2">
                Output to Evaluate *
              </label>
              <textarea
                value={output}
                onChange={(e) => setOutput(e.target.value)}
                placeholder="Paste the LLM output you want to evaluate..."
                className="w-full h-32 bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm resize-none focus:border-emerald-500 focus:outline-none"
              />
            </div>

            {/* Context Input */}
            <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
              <label className="text-sm font-medium text-slate-300 block mb-2">
                Context (Optional)
              </label>
              <textarea
                value={context}
                onChange={(e) => setContext(e.target.value)}
                placeholder="Provide context for the evaluation..."
                className="w-full h-24 bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm resize-none focus:border-emerald-500 focus:outline-none"
              />
            </div>

            {/* Expected Output */}
            <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
              <label className="text-sm font-medium text-slate-300 block mb-2">
                Expected Output (Optional)
              </label>
              <textarea
                value={expected}
                onChange={(e) => setExpected(e.target.value)}
                placeholder="What was the expected output?"
                className="w-full h-24 bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm resize-none focus:border-emerald-500 focus:outline-none"
              />
            </div>

            {/* Eval Types Selection (for full mode) */}
            {evalMode === 'full' && (
              <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
                <h3 className="text-sm font-medium text-slate-300 mb-3">Evaluation Criteria</h3>
                <div className="grid grid-cols-2 gap-2">
                  {EVAL_TYPES.map((type) => (
                    <button
                      key={type.id}
                      onClick={() => toggleEvalType(type.id)}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        selectedTypes.includes(type.id)
                          ? 'border-emerald-500 bg-emerald-500/10'
                          : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className={selectedTypes.includes(type.id) ? 'text-emerald-400' : 'text-slate-400'}>
                          {type.icon}
                        </span>
                        <span className="text-white text-sm">{type.name}</span>
                      </div>
                      <p className="text-slate-500 text-xs mt-1">{type.description}</p>
                    </button>
                  ))}
                </div>

                {/* LLM Judge toggle */}
                <div className="mt-4 pt-4 border-t border-slate-700">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={useLlmJudge}
                      onChange={(e) => setUseLlmJudge(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-600 bg-slate-900 text-emerald-500 focus:ring-emerald-500"
                    />
                    <span className="text-sm text-slate-300">Use LLM Judge for enhanced evaluation</span>
                  </label>
                </div>

                {/* Threshold slider */}
                <div className="mt-4">
                  <label className="text-sm text-slate-400 block mb-2">
                    Pass Threshold: {(threshold * 100).toFixed(0)}%
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={threshold * 100}
                    onChange={(e) => setThreshold(Number(e.target.value) / 100)}
                    className="w-full accent-emerald-500"
                  />
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-red-400" />
                <p className="text-red-300 text-sm">{error}</p>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-3">
              <Button
                onClick={runEvaluation}
                disabled={isEvaluating || !output.trim()}
                loading={isEvaluating}
                className="flex-1"
                leftIcon={<Play size={16} />}
              >
                {isEvaluating ? 'Evaluating...' : 'Run Evaluation'}
              </Button>
              {(output || result || quickResult || llmResult) && (
                <Button
                  variant="secondary"
                  onClick={clearResults}
                  disabled={isEvaluating}
                >
                  Clear
                </Button>
              )}
            </div>
          </div>

          {/* Results Section */}
          <div>
            {result && (
              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">Evaluation Results</h2>
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                    result.passed
                      ? 'bg-emerald-400/10 text-emerald-400'
                      : 'bg-red-400/10 text-red-400'
                  }`}>
                    {result.passed ? 'PASSED' : 'FAILED'}
                  </span>
                </div>

                {/* Overall Score */}
                <div className={`p-4 rounded-lg mb-4 ${getScoreBg(result.overall_score)}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-300">Overall Score</span>
                    <span className={`text-2xl font-bold ${getScoreColor(result.overall_score)}`}>
                      {(result.overall_score * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                {/* Individual Scores */}
                <div className="space-y-3">
                  {Object.entries(result.scores).map(([key, score]) => (
                    <div key={key} className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                      <div className="flex items-center gap-2">
                        {EVAL_TYPES.find(t => t.id === key)?.icon}
                        <span className="text-white capitalize">{key}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-24 bg-slate-600 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${score >= 0.8 ? 'bg-emerald-400' : score >= 0.6 ? 'bg-amber-400' : 'bg-red-400'}`}
                            style={{ width: `${score * 100}%` }}
                          />
                        </div>
                        <span className={`font-mono text-sm ${getScoreColor(score)}`}>
                          {(score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {quickResult && (
              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                <h2 className="text-lg font-semibold text-white mb-4">Quick Evaluation</h2>

                <div className={`p-4 rounded-lg mb-4 ${getScoreBg(quickResult.overall)}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-300">Overall Score</span>
                    <span className={`text-2xl font-bold ${getScoreColor(quickResult.overall)}`}>
                      {(quickResult.overall * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {[
                    { key: 'relevance', score: quickResult.relevance },
                    { key: 'coherence', score: quickResult.coherence },
                    { key: 'helpfulness', score: quickResult.helpfulness },
                    { key: 'safety', score: quickResult.safety },
                  ].map(({ key, score }) => (
                    <div key={key} className="p-3 bg-slate-700/50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-slate-400 text-sm capitalize">{key}</span>
                        <span className={`font-mono text-sm ${getScoreColor(score)}`}>
                          {(score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-600 rounded-full h-1.5">
                        <div
                          className={`h-1.5 rounded-full ${score >= 0.8 ? 'bg-emerald-400' : score >= 0.6 ? 'bg-amber-400' : 'bg-red-400'}`}
                          style={{ width: `${score * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {llmResult && (
              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">LLM Judge Result</h2>
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                    llmResult.passed
                      ? 'bg-emerald-400/10 text-emerald-400'
                      : 'bg-red-400/10 text-red-400'
                  }`}>
                    {llmResult.passed ? 'PASSED' : 'FAILED'}
                  </span>
                </div>

                <div className={`p-4 rounded-lg mb-4 ${getScoreBg(llmResult.score)}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-300">Score</span>
                    <span className={`text-2xl font-bold ${getScoreColor(llmResult.score)}`}>
                      {(llmResult.score * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                <div className="p-4 bg-slate-700/50 rounded-lg mb-4">
                  <h4 className="text-sm font-medium text-slate-300 mb-2">Reasoning</h4>
                  <p className="text-slate-400 text-sm">{llmResult.reasoning}</p>
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="p-3 bg-slate-700/50 rounded-lg">
                    <span className="text-slate-500">Confidence</span>
                    <p className={`font-mono ${getScoreColor(llmResult.confidence)}`}>
                      {(llmResult.confidence * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div className="p-3 bg-slate-700/50 rounded-lg">
                    <span className="text-slate-500">Model</span>
                    <p className="text-white font-mono">{llmResult.model_used}</p>
                  </div>
                  <div className="p-3 bg-slate-700/50 rounded-lg col-span-2">
                    <span className="text-slate-500">Tokens Used</span>
                    <p className="text-white font-mono">{llmResult.tokens_used}</p>
                  </div>
                </div>
              </div>
            )}

            {!result && !quickResult && !llmResult && (
              <div className="h-full flex items-center justify-center bg-slate-800/50 rounded-xl border border-slate-700 border-dashed p-8">
                <div className="text-center text-slate-500">
                  <CheckSquare className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium mb-2">No results yet</p>
                  <p className="text-sm">Enter output and run evaluation to see results</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  )
}
