import { CheckCircle, XCircle } from 'lucide-react'
import type { InjectionCheckResult } from '@/lib/api'

function getSeverityColor(severity: string) {
  switch (severity) {
    case 'critical': return 'text-red-400 bg-red-400/10'
    case 'high': return 'text-orange-400 bg-orange-400/10'
    case 'medium': return 'text-amber-400 bg-amber-400/10'
    case 'low': return 'text-emerald-400 bg-emerald-400/10'
    default: return 'text-zinc-400 bg-zinc-400/10'
  }
}

interface InjectionCheckFormProps {
  text: string
  setText: (text: string) => void
  context: string
  setContext: (context: string) => void
}

export function InjectionCheckForm({ text, setText, context, setContext }: InjectionCheckFormProps) {
  return (
    <>
      <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
        <label className="text-sm font-medium text-zinc-300 block mb-2">
          Text to Check *
        </label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Enter user input or prompt to check for injection attacks..."
          className="w-full h-32 bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm resize-none focus:border-red-500 focus:outline-none"
        />
      </div>
      <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
        <label className="text-sm font-medium text-zinc-300 block mb-2">
          Context (Optional)
        </label>
        <textarea
          value={context}
          onChange={(e) => setContext(e.target.value)}
          placeholder="Provide additional context..."
          className="w-full h-20 bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm resize-none focus:border-red-500 focus:outline-none"
        />
      </div>
    </>
  )
}

interface InjectionCheckResultProps {
  result: InjectionCheckResult | null
}

export function InjectionCheckResult({ result }: InjectionCheckResultProps) {
  if (!result) return null

  return (
    <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Injection Check</h2>
        {result.detected ? (
          <XCircle className="text-red-400" size={24} />
        ) : (
          <CheckCircle className="text-emerald-400" size={24} />
        )}
      </div>

      <div className={`p-4 rounded-lg mb-4 ${result.detected ? 'bg-red-500/10' : 'bg-emerald-500/10'}`}>
        <span className={result.detected ? 'text-red-400' : 'text-emerald-400'}>
          {result.detected ? 'Injection Detected!' : 'No Injection Detected'}
        </span>
      </div>

      {result.detected && (
        <>
          <div className="space-y-3">
            <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
              <span className="text-zinc-400">Attack Type</span>
              <span className="text-white">{result.attack_type || 'Unknown'}</span>
            </div>
            <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
              <span className="text-zinc-400">Confidence</span>
              <span className="text-white">{(result.confidence * 100).toFixed(1)}%</span>
            </div>
            <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
              <span className="text-zinc-400">Severity</span>
              <span className={`px-2 py-0.5 rounded-full text-xs ${getSeverityColor(result.severity)}`}>
                {result.severity}
              </span>
            </div>
          </div>
          {result.matched_patterns.length > 0 && (
            <div className="mt-4 p-3 bg-zinc-900 rounded-lg">
              <span className="text-zinc-500 text-sm">Matched Patterns:</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {result.matched_patterns.map((p, i) => (
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
  )
}
