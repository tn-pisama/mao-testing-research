import { CheckCircle, XCircle } from 'lucide-react'
import type { HallucinationCheckResult } from '@/lib/api'

interface HallucinationCheckFormProps {
  output: string
  setOutput: (output: string) => void
  sources: string
  setSources: (sources: string) => void
}

export function HallucinationCheckForm({ output, setOutput, sources, setSources }: HallucinationCheckFormProps) {
  return (
    <>
      <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
        <label className="text-sm font-medium text-zinc-300 block mb-2">
          LLM Output to Check *
        </label>
        <textarea
          value={output}
          onChange={(e) => setOutput(e.target.value)}
          placeholder="Enter the LLM output to check for hallucinations..."
          className="w-full h-32 bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm resize-none focus:border-red-500 focus:outline-none"
        />
      </div>
      <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
        <label className="text-sm font-medium text-zinc-300 block mb-2">
          Sources (One per line)
        </label>
        <textarea
          value={sources}
          onChange={(e) => setSources(e.target.value)}
          placeholder="Enter source documents/facts for grounding..."
          className="w-full h-24 bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm resize-none focus:border-red-500 focus:outline-none"
        />
      </div>
    </>
  )
}

interface HallucinationCheckResultProps {
  result: HallucinationCheckResult | null
}

export function HallucinationCheckResult({ result }: HallucinationCheckResultProps) {
  if (!result) return null

  return (
    <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Hallucination Check</h2>
        {result.detected ? (
          <XCircle className="text-red-400" size={24} />
        ) : (
          <CheckCircle className="text-emerald-400" size={24} />
        )}
      </div>

      <div className={`p-4 rounded-lg mb-4 ${result.detected ? 'bg-amber-500/10' : 'bg-emerald-500/10'}`}>
        <span className={result.detected ? 'text-amber-400' : 'text-emerald-400'}>
          {result.detected ? 'Potential Hallucination' : 'Output is Grounded'}
        </span>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
          <span className="text-zinc-400">Grounding Score</span>
          <span className={`${result.grounding_score >= 0.8 ? 'text-emerald-400' : result.grounding_score >= 0.6 ? 'text-amber-400' : 'text-red-400'}`}>
            {(result.grounding_score * 100).toFixed(1)}%
          </span>
        </div>
        <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
          <span className="text-zinc-400">Confidence</span>
          <span className="text-white">{(result.confidence * 100).toFixed(1)}%</span>
        </div>
        {result.hallucination_type && (
          <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
            <span className="text-zinc-400">Type</span>
            <span className="text-white">{result.hallucination_type}</span>
          </div>
        )}
      </div>
    </div>
  )
}
