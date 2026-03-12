import type { OverflowCheckResult } from '@/lib/api'

function getSeverityColor(severity: string) {
  switch (severity) {
    case 'critical': return 'text-red-400 bg-red-400/10'
    case 'high': return 'text-orange-400 bg-orange-400/10'
    case 'medium': return 'text-amber-400 bg-amber-400/10'
    case 'low': return 'text-emerald-400 bg-emerald-400/10'
    default: return 'text-zinc-400 bg-zinc-400/10'
  }
}

interface OverflowCheckFormProps {
  model: string
  setModel: (model: string) => void
  tokens: number
  setTokens: (tokens: number) => void
}

export function OverflowCheckForm({ model, setModel, tokens, setTokens }: OverflowCheckFormProps) {
  return (
    <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700 space-y-4">
      <div>
        <label className="text-sm font-medium text-zinc-300 block mb-2">
          Model
        </label>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
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
          Current Token Count: {tokens.toLocaleString()}
        </label>
        <input
          type="range"
          min="0"
          max="200000"
          step="1000"
          value={tokens}
          onChange={(e) => setTokens(Number(e.target.value))}
          className="w-full accent-red-500"
        />
      </div>
    </div>
  )
}

interface OverflowCheckResultProps {
  result: OverflowCheckResult | null
}

export function OverflowCheckResult({ result }: OverflowCheckResultProps) {
  if (!result) return null

  return (
    <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Context Overflow</h2>
        <span className={`px-2 py-0.5 rounded-full text-xs ${getSeverityColor(result.severity)}`}>
          {result.severity}
        </span>
      </div>

      <div className="mb-4">
        <div className="flex justify-between text-sm mb-2">
          <span className="text-zinc-400">Usage</span>
          <span className={`${result.usage_percent >= 90 ? 'text-red-400' : result.usage_percent >= 70 ? 'text-amber-400' : 'text-emerald-400'}`}>
            {result.usage_percent.toFixed(1)}%
          </span>
        </div>
        <div className="w-full bg-zinc-600 rounded-full h-3">
          <div
            className={`h-3 rounded-full ${result.usage_percent >= 90 ? 'bg-red-400' : result.usage_percent >= 70 ? 'bg-amber-400' : 'bg-emerald-400'}`}
            style={{ width: `${Math.min(result.usage_percent, 100)}%` }}
          />
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
          <span className="text-zinc-400">Current Tokens</span>
          <span className="text-white">{result.current_tokens.toLocaleString()}</span>
        </div>
        <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
          <span className="text-zinc-400">Context Window</span>
          <span className="text-white">{result.context_window.toLocaleString()}</span>
        </div>
        <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
          <span className="text-zinc-400">Remaining</span>
          <span className="text-white">{result.remaining_tokens.toLocaleString()}</span>
        </div>
      </div>

      {result.warnings.length > 0 && (
        <div className="mt-4 p-3 bg-amber-500/10 rounded-lg">
          <span className="text-amber-400 text-sm font-medium">Warnings:</span>
          <ul className="mt-2 space-y-1">
            {result.warnings.map((w, i) => (
              <li key={i} className="text-amber-300 text-sm">{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
