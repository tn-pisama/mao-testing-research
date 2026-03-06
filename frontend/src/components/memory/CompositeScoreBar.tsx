'use client'

interface CompositeScoreBarProps {
  similarity: number
  recency: number
  importance: number
  total: number
}

export function CompositeScoreBar({ similarity, recency, importance, total }: CompositeScoreBarProps) {
  const sum = similarity + recency + importance
  if (sum === 0) return null

  const simPct = (similarity / sum) * 100
  const recPct = (recency / sum) * 100
  const impPct = (importance / sum) * 100

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-3 rounded-full overflow-hidden bg-zinc-800 flex">
        {simPct > 0 && (
          <div
            className="bg-blue-500 h-full transition-all duration-300"
            style={{ width: `${simPct}%` }}
            title={`Similarity: ${(similarity * 100).toFixed(0)}%`}
          />
        )}
        {recPct > 0 && (
          <div
            className="bg-green-500 h-full transition-all duration-300"
            style={{ width: `${recPct}%` }}
            title={`Recency: ${(recency * 100).toFixed(0)}%`}
          />
        )}
        {impPct > 0 && (
          <div
            className="bg-violet-500 h-full transition-all duration-300"
            style={{ width: `${impPct}%` }}
            title={`Importance: ${(importance * 100).toFixed(0)}%`}
          />
        )}
      </div>
      <span className="text-xs font-mono text-zinc-300 w-12 text-right">
        {total.toFixed(2)}
      </span>
    </div>
  )
}
