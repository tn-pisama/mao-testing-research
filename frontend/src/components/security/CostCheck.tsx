import type { CostCalculation } from '@/lib/api'

interface CostCheckFormProps {
  model: string
  setModel: (model: string) => void
  inputTokens: number
  setInputTokens: (tokens: number) => void
  outputTokens: number
  setOutputTokens: (tokens: number) => void
}

export function CostCheckForm({ model, setModel, inputTokens, setInputTokens, outputTokens, setOutputTokens }: CostCheckFormProps) {
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
          Input Tokens: {inputTokens.toLocaleString()}
        </label>
        <input
          type="range"
          min="0"
          max="100000"
          step="100"
          value={inputTokens}
          onChange={(e) => setInputTokens(Number(e.target.value))}
          className="w-full accent-red-500"
        />
      </div>
      <div>
        <label className="text-sm font-medium text-zinc-300 block mb-2">
          Output Tokens: {outputTokens.toLocaleString()}
        </label>
        <input
          type="range"
          min="0"
          max="50000"
          step="100"
          value={outputTokens}
          onChange={(e) => setOutputTokens(Number(e.target.value))}
          className="w-full accent-red-500"
        />
      </div>
    </div>
  )
}

interface CostCheckResultProps {
  result: CostCalculation | null
}

export function CostCheckResult({ result }: CostCheckResultProps) {
  if (!result) return null

  return (
    <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700">
      <h2 className="text-lg font-semibold text-white mb-4">Cost Calculation</h2>

      <div className="p-4 bg-emerald-500/10 rounded-lg mb-4">
        <div className="flex items-center justify-between">
          <span className="text-zinc-300">Total Cost</span>
          <span className="text-2xl font-bold text-emerald-400">
            ${result.total_cost_usd.toFixed(4)}
          </span>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
          <span className="text-zinc-400">Model</span>
          <span className="text-white">{result.model}</span>
        </div>
        <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
          <span className="text-zinc-400">Provider</span>
          <span className="text-white">{result.provider}</span>
        </div>
        <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
          <span className="text-zinc-400">Input Cost</span>
          <span className="text-white">${result.input_cost_usd.toFixed(4)}</span>
        </div>
        <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
          <span className="text-zinc-400">Output Cost</span>
          <span className="text-white">${result.output_cost_usd.toFixed(4)}</span>
        </div>
        <div className="flex justify-between p-3 bg-zinc-700/50 rounded-lg">
          <span className="text-zinc-400">Total Tokens</span>
          <span className="text-white">{result.total_tokens.toLocaleString()}</span>
        </div>
      </div>
    </div>
  )
}
