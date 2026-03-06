'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { Layout } from '@/components/common/Layout'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { createApiClient, CognitiveMemoryItem, ScoredMemory, MemoryTreeNode, MemoryStats } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { MemoryCard } from '@/components/memory/MemoryCard'
import { CompositeScoreBar } from '@/components/memory/CompositeScoreBar'
import {
  Brain,
  Search,
  RefreshCw,
  ChevronRight,
  ChevronDown,
  Database,
  Activity,
  Layers,
  Globe,
  Loader2,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Demo data fallback
// ---------------------------------------------------------------------------
const DEMO_MEMORIES: CognitiveMemoryItem[] = [
  {
    id: '1',
    content: 'LangGraph loop detection requires hash threshold of 3 for reliable detection',
    memory_type: 'detection_pattern',
    domain: 'loop',
    importance: 0.85,
    confidence: 0.9,
    access_count: 12,
    tags: ['langgraph', 'loop'],
    framework: 'langgraph',
    structured_data: {},
    source_type: 'detection',
    is_active: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: '2',
    content: 'False positive rate for hallucination detection drops 40% with source document comparison',
    memory_type: 'false_positive_pattern',
    domain: 'hallucination',
    importance: 0.92,
    confidence: 0.8,
    access_count: 8,
    tags: ['hallucination', 'fp_reduction'],
    framework: null,
    structured_data: {},
    source_type: 'calibration',
    is_active: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: '3',
    content: 'CrewAI coordination failures often manifest as duplicate task assignments',
    memory_type: 'framework_pattern',
    domain: 'coordination',
    importance: 0.7,
    confidence: 0.75,
    access_count: 5,
    tags: ['crewai', 'coordination'],
    framework: 'crewai',
    structured_data: {},
    source_type: 'detection',
    is_active: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: '4',
    content: 'Increasing semantic similarity threshold from 0.7 to 0.8 reduced FP by 25% for context detection',
    memory_type: 'threshold_learning',
    domain: 'context',
    importance: 0.88,
    confidence: 0.85,
    access_count: 15,
    tags: ['context', 'threshold'],
    framework: null,
    structured_data: {},
    source_type: 'calibration',
    is_active: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
]

const DEMO_STATS: MemoryStats = {
  total: 4,
  active: 4,
  by_type: { detection_pattern: 1, false_positive_pattern: 1, framework_pattern: 1, threshold_learning: 1 },
  by_domain: { loop: 1, hallucination: 1, coordination: 1, context: 1 },
}

const DEMO_TREE: Record<string, MemoryTreeNode> = {
  detection_pattern: {
    name: 'detection_pattern',
    count: 1,
    avg_importance: 0.85,
    children: { loop: { count: 1, avg_importance: 0.85, memories: [DEMO_MEMORIES[0]] } },
  },
  false_positive_pattern: {
    name: 'false_positive_pattern',
    count: 1,
    avg_importance: 0.92,
    children: { hallucination: { count: 1, avg_importance: 0.92, memories: [DEMO_MEMORIES[1]] } },
  },
  framework_pattern: {
    name: 'framework_pattern',
    count: 1,
    avg_importance: 0.7,
    children: { coordination: { count: 1, avg_importance: 0.7, memories: [DEMO_MEMORIES[2]] } },
  },
  threshold_learning: {
    name: 'threshold_learning',
    count: 1,
    avg_importance: 0.88,
    children: { context: { count: 1, avg_importance: 0.88, memories: [DEMO_MEMORIES[3]] } },
  },
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------
export default function MemoryPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()

  const [isLoading, setIsLoading] = useState(true)
  const [memories, setMemories] = useState<CognitiveMemoryItem[]>([])
  const [stats, setStats] = useState<MemoryStats | null>(null)
  const [tree, setTree] = useState<Record<string, MemoryTreeNode>>({})

  // Search state
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ScoredMemory[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [weights, setWeights] = useState({ similarity: 0.5, recency: 0.3, importance: 0.2 })

  // Tree expand state
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set())
  const [expandedDomains, setExpandedDomains] = useState<Set<string>>(new Set())

  const useDemoMode = useCallback(() => {
    setMemories(DEMO_MEMORIES)
    setStats(DEMO_STATS)
    setTree(DEMO_TREE)
  }, [])

  const fetchData = useCallback(async () => {
    if (!tenantId) return
    setIsLoading(true)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      const [statsRes, treeRes] = await Promise.all([
        api.getMemoryStats().catch(() => null),
        api.getMemoryTree().catch(() => null),
      ])

      if (!statsRes && !treeRes) {
        useDemoMode()
      } else {
        setStats(statsRes || DEMO_STATS)
        setTree(treeRes || DEMO_TREE)
        // Flatten tree into list for recent memories
        const allMems: CognitiveMemoryItem[] = []
        const treeData = treeRes || DEMO_TREE
        Object.values(treeData).forEach((node: MemoryTreeNode) => {
          Object.values(node.children).forEach((child) => {
            allMems.push(...child.memories)
          })
        })
        setMemories(allMems.length > 0 ? allMems : DEMO_MEMORIES)
      }
    } catch (err) {
      console.error('Failed to fetch memory data:', err)
      useDemoMode()
    } finally {
      setIsLoading(false)
    }
  }, [tenantId, getToken, useDemoMode])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleSearch = async () => {
    if (!query.trim()) return
    setIsSearching(true)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const results = await api.recallMemories(query, undefined, 10, weights)
      setSearchResults(results)
    } catch (err) {
      console.error('Recall failed, using demo fallback:', err)
      // Build demo scored results
      setSearchResults(
        DEMO_MEMORIES.filter((m) =>
          m.content.toLowerCase().includes(query.toLowerCase()) ||
          m.domain.toLowerCase().includes(query.toLowerCase())
        ).map((m) => ({
          memory: m,
          similarity_score: 0.8,
          recency_score: 0.6,
          importance_score: m.importance,
          composite_score: 0.75,
          confidence_level: 'HIGH',
        }))
      )
    } finally {
      setIsSearching(false)
    }
  }

  const toggleType = (type: string) => {
    setExpandedTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  const toggleDomain = (key: string) => {
    setExpandedDomains((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // Sort recent memories by importance descending
  const recentMemories = [...memories].sort((a, b) => b.importance - a.importance).slice(0, 12)

  return (
    <Layout>
      <div className="p-6 space-y-8">
        {/* ---- Header ---- */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-500/20 rounded-lg">
              <Brain size={24} className="text-violet-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Cognitive Memory</h1>
              <p className="text-sm text-zinc-400">
                Persistent learning from detections, calibration, and feedback
              </p>
            </div>
          </div>
          <Button variant="ghost" onClick={fetchData} leftIcon={<RefreshCw size={16} />}>
            Refresh
          </Button>
        </div>

        {/* ---- Stats Row ---- */}
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i}>
                <div className="animate-pulse h-20 bg-zinc-800 rounded" />
              </Card>
            ))}
          </div>
        ) : stats ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-500/20 rounded-lg">
                  <Database size={18} className="text-blue-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">{stats.total}</p>
                  <p className="text-xs text-zinc-400">Total Memories</p>
                </div>
              </div>
            </Card>
            <Card>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-500/20 rounded-lg">
                  <Activity size={18} className="text-green-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">{stats.active}</p>
                  <p className="text-xs text-zinc-400">Active</p>
                </div>
              </div>
            </Card>
            <Card>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-violet-500/20 rounded-lg">
                  <Layers size={18} className="text-violet-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">
                    {Object.keys(stats.by_type).length}
                  </p>
                  <p className="text-xs text-zinc-400">Memory Types</p>
                </div>
              </div>
            </Card>
            <Card>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-amber-500/20 rounded-lg">
                  <Globe size={18} className="text-amber-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">
                    {Object.keys(stats.by_domain).length}
                  </p>
                  <p className="text-xs text-zinc-400">Domains</p>
                </div>
              </div>
            </Card>
          </div>
        ) : null}

        {/* ---- Search / Recall ---- */}
        <Card padding="lg">
          <h2 className="text-lg font-semibold text-white mb-4">Recall Memories</h2>

          <div className="flex gap-3 mb-4">
            <div className="flex-1 relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search memories... (e.g. 'loop detection threshold')"
                className="w-full pl-10 pr-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <Button
              variant="primary"
              onClick={handleSearch}
              isLoading={isSearching}
              leftIcon={<Search size={14} />}
            >
              Recall
            </Button>
          </div>

          {/* Weight sliders */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
            {([
              { key: 'similarity' as const, label: 'Similarity', color: 'blue' },
              { key: 'recency' as const, label: 'Recency', color: 'green' },
              { key: 'importance' as const, label: 'Importance', color: 'violet' },
            ] as const).map(({ key, label, color }) => (
              <div key={key}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-zinc-400">{label}</span>
                  <span className={`text-xs font-mono text-${color}-400`}>
                    {weights[key].toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={weights[key]}
                  onChange={(e) =>
                    setWeights((prev) => ({ ...prev, [key]: parseFloat(e.target.value) }))
                  }
                  className="w-full h-1.5 rounded-full appearance-none bg-zinc-700 accent-blue-500"
                />
              </div>
            ))}
          </div>

          {/* Legend */}
          <div className="flex items-center gap-4 mb-4 text-[10px] text-zinc-500">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-500" /> Similarity
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-500" /> Recency
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-violet-500" /> Importance
            </span>
          </div>

          {/* Search results */}
          {searchResults.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-zinc-300">
                {searchResults.length} result{searchResults.length !== 1 ? 's' : ''}
              </h3>
              {searchResults.map((sr) => (
                <Card key={sr.memory.id} variant="bordered" padding="sm">
                  <div className="space-y-2">
                    <p className="text-sm text-zinc-200">{sr.memory.content}</p>
                    <CompositeScoreBar
                      similarity={sr.similarity_score}
                      recency={sr.recency_score}
                      importance={sr.importance_score}
                      total={sr.composite_score}
                    />
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge
                        size="sm"
                        variant={
                          sr.confidence_level === 'HIGH'
                            ? 'success'
                            : sr.confidence_level === 'MEDIUM'
                            ? 'warning'
                            : 'default'
                        }
                      >
                        {sr.confidence_level}
                      </Badge>
                      <Badge variant="info" size="sm">{sr.memory.domain}</Badge>
                      {sr.memory.tags.map((t) => (
                        <span
                          key={t}
                          className="px-1.5 py-0.5 text-[10px] text-zinc-500 bg-zinc-800 rounded"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </Card>

        {/* ---- Memory Tree ---- */}
        <Card padding="lg">
          <h2 className="text-lg font-semibold text-white mb-4">Memory Tree</h2>

          {isLoading ? (
            <div className="animate-pulse space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 bg-zinc-800 rounded-lg" />
              ))}
            </div>
          ) : Object.keys(tree).length === 0 ? (
            <p className="text-sm text-zinc-500 text-center py-6">No memories yet</p>
          ) : (
            <div className="space-y-1">
              {Object.entries(tree).map(([type, node]) => {
                const isTypeExpanded = expandedTypes.has(type)
                return (
                  <div key={type}>
                    {/* Type row */}
                    <button
                      onClick={() => toggleType(type)}
                      className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-zinc-800 transition-colors text-left"
                    >
                      {isTypeExpanded ? (
                        <ChevronDown size={14} className="text-zinc-500" />
                      ) : (
                        <ChevronRight size={14} className="text-zinc-500" />
                      )}
                      <Badge size="sm" className="border-violet-500/50 text-violet-400 bg-violet-500/10">
                        {type}
                      </Badge>
                      <span className="text-xs text-zinc-500 ml-auto">
                        {node.count} memor{node.count === 1 ? 'y' : 'ies'} &middot; avg{' '}
                        {(node.avg_importance * 100).toFixed(0)}%
                      </span>
                    </button>

                    {/* Domain children */}
                    {isTypeExpanded && (
                      <div className="ml-6 space-y-0.5">
                        {Object.entries(node.children).map(([domain, child]) => {
                          const domainKey = `${type}:${domain}`
                          const isDomainExpanded = expandedDomains.has(domainKey)
                          return (
                            <div key={domainKey}>
                              <button
                                onClick={() => toggleDomain(domainKey)}
                                className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-zinc-800 transition-colors text-left"
                              >
                                {isDomainExpanded ? (
                                  <ChevronDown size={12} className="text-zinc-600" />
                                ) : (
                                  <ChevronRight size={12} className="text-zinc-600" />
                                )}
                                <Badge variant="info" size="sm">{domain}</Badge>
                                <span className="text-xs text-zinc-500 ml-auto">
                                  {child.count} &middot; avg{' '}
                                  {(child.avg_importance * 100).toFixed(0)}%
                                </span>
                              </button>

                              {isDomainExpanded && child.memories.length > 0 && (
                                <div className="ml-7 space-y-1 py-1">
                                  {child.memories.map((mem) => (
                                    <a
                                      key={mem.id}
                                      href={`/memory/${mem.id}`}
                                      className="block px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60 transition-colors truncate"
                                    >
                                      {mem.content}
                                    </a>
                                  ))}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </Card>

        {/* ---- Recent Memories ---- */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">Recent Memories</h2>

          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <Card key={i}>
                  <div className="animate-pulse space-y-3">
                    <div className="h-4 bg-zinc-800 rounded w-3/4" />
                    <div className="h-4 bg-zinc-800 rounded w-1/2" />
                    <div className="h-2 bg-zinc-800 rounded" />
                  </div>
                </Card>
              ))}
            </div>
          ) : recentMemories.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-zinc-400">
                <Brain size={32} className="mx-auto mb-3 opacity-50" />
                <p className="text-sm">No memories stored yet</p>
                <p className="text-xs text-zinc-500 mt-1">
                  Memories are automatically created from detections and calibration runs
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {recentMemories.map((mem) => (
                <MemoryCard
                  key={mem.id}
                  id={mem.id}
                  content={mem.content}
                  memory_type={mem.memory_type}
                  domain={mem.domain}
                  importance={mem.importance}
                  confidence={mem.confidence}
                  tags={mem.tags}
                  framework={mem.framework}
                  created_at={mem.created_at}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
