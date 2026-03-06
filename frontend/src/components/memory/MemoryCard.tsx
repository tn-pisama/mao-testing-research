'use client'

import Link from 'next/link'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Clock, Tag } from 'lucide-react'

interface MemoryCardProps {
  id: string
  content: string
  memory_type: string
  domain: string
  importance: number
  confidence: number
  tags: string[]
  framework?: string | null
  created_at: string
}

function importanceColor(value: number): string {
  if (value < 0.3) return 'bg-red-500'
  if (value < 0.7) return 'bg-amber-500'
  return 'bg-green-500'
}

export function MemoryCard({
  id,
  content,
  memory_type,
  domain,
  importance,
  confidence,
  tags,
  framework,
  created_at,
}: MemoryCardProps) {
  const formattedDate = new Date(created_at).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <Link href={`/memory/${id}`}>
      <Card className="cursor-pointer hover:border-zinc-600 transition-all duration-200">
        <p className="text-sm text-zinc-200 line-clamp-2 mb-3">{content}</p>

        {/* Importance bar */}
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs text-zinc-500 w-20">Importance</span>
          <div className="flex-1 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${importanceColor(importance)}`}
              style={{ width: `${importance * 100}%` }}
            />
          </div>
          <span className="text-xs font-mono text-zinc-400 w-8 text-right">
            {(importance * 100).toFixed(0)}%
          </span>
        </div>

        {/* Badges */}
        <div className="flex items-center flex-wrap gap-1.5 mb-2">
          <Badge variant="info" size="sm">{domain}</Badge>
          <Badge size="sm" className="border-violet-500/50 text-violet-400 bg-violet-500/10">
            {memory_type}
          </Badge>
          {framework && (
            <Badge variant="success" size="sm">{framework}</Badge>
          )}
        </div>

        {/* Tags + date */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1 flex-wrap">
            {tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] text-zinc-500 bg-zinc-800 rounded"
              >
                <Tag size={8} />
                {tag}
              </span>
            ))}
            {tags.length > 3 && (
              <span className="text-[10px] text-zinc-600">+{tags.length - 3}</span>
            )}
          </div>
          <span className="flex items-center gap-1 text-[10px] text-zinc-500">
            <Clock size={10} />
            {formattedDate}
          </span>
        </div>
      </Card>
    </Link>
  )
}
