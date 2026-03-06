'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { Layout } from '@/components/common/Layout'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { createApiClient, CognitiveMemoryItem } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import {
  Brain,
  ArrowLeft,
  Clock,
  Eye,
  Trash2,
  AlertTriangle,
  Link as LinkIcon,
  Loader2,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Demo fallback
// ---------------------------------------------------------------------------
const DEMO_MEMORY: CognitiveMemoryItem & {
  last_accessed_at?: string
  supersedes?: string | null
  superseded_by?: string | null
} = {
  id: 'demo-1',
  content: 'LangGraph loop detection requires hash threshold of 3 for reliable detection',
  memory_type: 'detection_pattern',
  domain: 'loop',
  importance: 0.85,
  confidence: 0.9,
  access_count: 12,
  tags: ['langgraph', 'loop'],
  framework: 'langgraph',
  structured_data: {
    threshold: 3,
    method: 'hash',
    sample_size: 150,
    f1_score: 0.91,
  },
  source_type: 'detection',
  is_active: true,
  created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
  updated_at: new Date().toISOString(),
  last_accessed_at: new Date().toISOString(),
  supersedes: null,
  superseded_by: null,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function importanceColor(value: number): string {
  if (value < 0.3) return 'bg-red-500'
  if (value < 0.7) return 'bg-amber-500'
  return 'bg-green-500'
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function MemoryDetailPage() {
  const params = useParams()
  const memoryId = params?.id as string
  const { getToken } = useAuth()
  const { tenantId } = useTenant()

  const [memory, setMemory] = useState<(CognitiveMemoryItem & {
    last_accessed_at?: string
    supersedes?: string | null
    superseded_by?: string | null
  }) | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const fetchMemory = useCallback(async () => {
    if (!tenantId || !memoryId) return
    setIsLoading(true)
    setError(null)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const data = await api.getMemory(memoryId)
      setMemory(data as any)
    } catch (err) {
      console.error('Failed to fetch memory, using demo:', err)
      setMemory({ ...DEMO_MEMORY, id: memoryId })
    } finally {
      setIsLoading(false)
    }
  }, [tenantId, memoryId, getToken])

  useEffect(() => {
    fetchMemory()
  }, [fetchMemory])

  const handleDelete = async () => {
    if (!tenantId || !memoryId) return
    if (!window.confirm('Delete this memory? This cannot be undone.')) return

    setIsDeleting(true)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.forgetMemory(memoryId)
      window.location.href = '/memory'
    } catch (err: any) {
      setError(err.message || 'Failed to delete memory')
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto space-y-6">
        {/* Back link */}
        <Link
          href="/memory"
          className="inline-flex items-center gap-1.5 text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ArrowLeft size={14} />
          Back to Memory
        </Link>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={24} className="text-zinc-500 animate-spin" />
          </div>
        ) : !memory ? (
          <Card>
            <CardContent className="p-8 text-center text-zinc-400">
              <AlertTriangle size={32} className="mx-auto mb-3 opacity-50" />
              <p className="text-sm">Memory not found</p>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Error banner */}
            {error && (
              <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
                <AlertTriangle size={20} className="text-red-400" />
                <p className="text-sm text-red-300">{error}</p>
              </div>
            )}

            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-violet-500/20 rounded-lg">
                  <Brain size={24} className="text-violet-400" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-white">Memory Detail</h1>
                  <p className="text-xs text-zinc-500 font-mono">{memory.id}</p>
                </div>
              </div>
              <Button
                variant="danger"
                size="sm"
                onClick={handleDelete}
                isLoading={isDeleting}
                leftIcon={<Trash2 size={14} />}
              >
                Delete
              </Button>
            </div>

            {/* Content card */}
            <Card className="border-violet-500/20 bg-violet-500/5">
              <p className="text-sm text-zinc-100 leading-relaxed">{memory.content}</p>
            </Card>

            {/* Metadata */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Left column */}
              <Card>
                <h3 className="text-sm font-medium text-zinc-300 mb-3">Classification</h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-zinc-500">Type</span>
                    <Badge size="sm" className="border-violet-500/50 text-violet-400 bg-violet-500/10">
                      {memory.memory_type}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-zinc-500">Domain</span>
                    <Badge variant="info" size="sm">{memory.domain}</Badge>
                  </div>
                  {memory.framework && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-zinc-500">Framework</span>
                      <Badge variant="success" size="sm">{memory.framework}</Badge>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-zinc-500">Source</span>
                    <Badge size="sm">{memory.source_type}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-zinc-500">Status</span>
                    <Badge variant={memory.is_active ? 'success' : 'default'} size="sm">
                      {memory.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>
                </div>
              </Card>

              {/* Right column */}
              <Card>
                <h3 className="text-sm font-medium text-zinc-300 mb-3">Scores</h3>
                <div className="space-y-3">
                  {/* Importance */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-zinc-500">Importance</span>
                      <span className="text-xs font-mono text-zinc-300">
                        {(memory.importance * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${importanceColor(memory.importance)}`}
                        style={{ width: `${memory.importance * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Confidence */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-zinc-500">Confidence</span>
                      <span className="text-xs font-mono text-zinc-300">
                        {(memory.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-blue-500"
                        style={{ width: `${memory.confidence * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Access stats */}
                  <div className="flex items-center justify-between pt-2 border-t border-zinc-800">
                    <span className="flex items-center gap-1.5 text-xs text-zinc-500">
                      <Eye size={12} /> Access Count
                    </span>
                    <span className="text-xs font-mono text-zinc-300">
                      {memory.access_count}
                    </span>
                  </div>
                  {memory.last_accessed_at && (
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-xs text-zinc-500">
                        <Clock size={12} /> Last Accessed
                      </span>
                      <span className="text-xs text-zinc-400">
                        {formatDate(memory.last_accessed_at)}
                      </span>
                    </div>
                  )}
                </div>
              </Card>
            </div>

            {/* Tags */}
            {memory.tags.length > 0 && (
              <Card>
                <h3 className="text-sm font-medium text-zinc-300 mb-3">Tags</h3>
                <div className="flex flex-wrap gap-2">
                  {memory.tags.map((tag) => (
                    <Badge key={tag} size="sm">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </Card>
            )}

            {/* Structured data */}
            {memory.structured_data && Object.keys(memory.structured_data).length > 0 && (
              <Card>
                <h3 className="text-sm font-medium text-zinc-300 mb-3">Structured Data</h3>
                <pre className="text-xs text-zinc-400 bg-zinc-800 rounded-lg p-4 overflow-x-auto font-mono">
                  {JSON.stringify(memory.structured_data, null, 2)}
                </pre>
              </Card>
            )}

            {/* Contradiction chain */}
            {(memory.supersedes || memory.superseded_by) && (
              <Card>
                <h3 className="text-sm font-medium text-zinc-300 mb-3">Contradiction Chain</h3>
                <div className="space-y-2">
                  {memory.supersedes && (
                    <div className="flex items-center gap-2">
                      <LinkIcon size={12} className="text-zinc-500" />
                      <span className="text-xs text-zinc-500">Supersedes:</span>
                      <Link
                        href={`/memory/${memory.supersedes}`}
                        className="text-xs text-blue-400 hover:underline font-mono"
                      >
                        {memory.supersedes}
                      </Link>
                    </div>
                  )}
                  {memory.superseded_by && (
                    <div className="flex items-center gap-2">
                      <LinkIcon size={12} className="text-zinc-500" />
                      <span className="text-xs text-zinc-500">Superseded by:</span>
                      <Link
                        href={`/memory/${memory.superseded_by}`}
                        className="text-xs text-blue-400 hover:underline font-mono"
                      >
                        {memory.superseded_by}
                      </Link>
                    </div>
                  )}
                </div>
              </Card>
            )}

            {/* Timestamps */}
            <Card>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-xs text-zinc-500 block mb-1">Created</span>
                  <span className="text-sm text-zinc-300">{formatDate(memory.created_at)}</span>
                </div>
                <div>
                  <span className="text-xs text-zinc-500 block mb-1">Last Updated</span>
                  <span className="text-sm text-zinc-300">{formatDate(memory.updated_at)}</span>
                </div>
              </div>
            </Card>
          </>
        )}
      </div>
    </Layout>
  )
}
