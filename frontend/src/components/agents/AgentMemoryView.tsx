'use client'

import { useState, useMemo } from 'react'
import { clsx } from 'clsx'
import { Brain, Database, Clock, Trash2, Search, ChevronRight, Layers } from 'lucide-react'
import { AgentInfo } from './AgentCard'

interface MemoryEntry {
  id: string
  type: 'short_term' | 'long_term' | 'working'
  key: string
  value: string
  timestamp: string
  accessCount: number
  size: number
}

interface AgentMemoryViewProps {
  agent: AgentInfo
}

function generateMemoryData(): MemoryEntry[] {
  return [
    { id: '1', type: 'working', key: 'current_task', value: 'Analyzing user query for intent classification', timestamp: '2024-01-15T10:30:00Z', accessCount: 45, size: 128 },
    { id: '2', type: 'working', key: 'context_window', value: '[Previous 5 conversation turns...]', timestamp: '2024-01-15T10:29:00Z', accessCount: 23, size: 4096 },
    { id: '3', type: 'short_term', key: 'user_preferences', value: '{"language": "en", "verbosity": "concise"}', timestamp: '2024-01-15T10:25:00Z', accessCount: 12, size: 256 },
    { id: '4', type: 'short_term', key: 'session_context', value: 'User researching AI agent testing frameworks', timestamp: '2024-01-15T10:20:00Z', accessCount: 8, size: 512 },
    { id: '5', type: 'long_term', key: 'agent_persona', value: 'Research assistant specialized in technical documentation', timestamp: '2024-01-14T09:00:00Z', accessCount: 156, size: 1024 },
    { id: '6', type: 'long_term', key: 'knowledge_base_ref', value: 'kb://technical-docs/v2.3', timestamp: '2024-01-10T12:00:00Z', accessCount: 89, size: 64 },
  ]
}

const typeConfig = {
  working: { color: 'text-amber-400', bgColor: 'bg-amber-500/20', label: 'Working Memory' },
  short_term: { color: 'text-blue-400', bgColor: 'bg-blue-500/20', label: 'Short-term' },
  long_term: { color: 'text-purple-400', bgColor: 'bg-purple-500/20', label: 'Long-term' },
}

export function AgentMemoryView({ agent }: AgentMemoryViewProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedType, setSelectedType] = useState<MemoryEntry['type'] | 'all'>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const memories = useMemo(() => generateMemoryData(), [])

  const filteredMemories = useMemo(() => {
    return memories.filter((m) => {
      const matchesType = selectedType === 'all' || m.type === selectedType
      const matchesSearch = !searchQuery || 
        m.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.value.toLowerCase().includes(searchQuery.toLowerCase())
      return matchesType && matchesSearch
    })
  }, [memories, selectedType, searchQuery])

  const stats = useMemo(() => {
    const totalSize = memories.reduce((sum, m) => sum + m.size, 0)
    const working = memories.filter((m) => m.type === 'working').length
    const shortTerm = memories.filter((m) => m.type === 'short_term').length
    const longTerm = memories.filter((m) => m.type === 'long_term').length
    return { totalSize, working, shortTerm, longTerm, total: memories.length }
  }, [memories])

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
          <div className="flex items-center gap-2 mb-2">
            <Database size={14} className="text-slate-400" />
            <span className="text-xs text-slate-400">Total Size</span>
          </div>
          <div className="text-xl font-bold text-white">{(stats.totalSize / 1024).toFixed(1)} KB</div>
        </div>
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
          <div className="flex items-center gap-2 mb-2">
            <Brain size={14} className="text-amber-400" />
            <span className="text-xs text-amber-400">Working</span>
          </div>
          <div className="text-xl font-bold text-white">{stats.working}</div>
        </div>
        <div className="p-4 rounded-xl bg-blue-500/10 border border-blue-500/30">
          <div className="flex items-center gap-2 mb-2">
            <Clock size={14} className="text-blue-400" />
            <span className="text-xs text-blue-400">Short-term</span>
          </div>
          <div className="text-xl font-bold text-white">{stats.shortTerm}</div>
        </div>
        <div className="p-4 rounded-xl bg-purple-500/10 border border-purple-500/30">
          <div className="flex items-center gap-2 mb-2">
            <Layers size={14} className="text-purple-400" />
            <span className="text-xs text-purple-400">Long-term</span>
          </div>
          <div className="text-xl font-bold text-white">{stats.longTerm}</div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search memory..."
            className="w-full pl-10 pr-4 py-2 rounded-lg bg-slate-800/50 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-primary-500"
          />
        </div>
        <div className="flex gap-2">
          {(['all', 'working', 'short_term', 'long_term'] as const).map((type) => (
            <button
              key={type}
              onClick={() => setSelectedType(type)}
              className={clsx(
                'px-3 py-2 rounded-lg text-xs font-medium transition-all',
                selectedType === type
                  ? 'bg-primary-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              )}
            >
              {type === 'all' ? 'All' : typeConfig[type].label}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        {filteredMemories.map((memory) => {
          const config = typeConfig[memory.type]
          const isExpanded = expandedId === memory.id

          return (
            <div
              key={memory.id}
              className={clsx(
                'rounded-xl border transition-all',
                'bg-slate-800/50 hover:bg-slate-800',
                isExpanded ? 'border-primary-500/50' : 'border-slate-700'
              )}
            >
              <button
                onClick={() => setExpandedId(isExpanded ? null : memory.id)}
                className="w-full p-4 text-left"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={clsx('p-2 rounded-lg', config.bgColor)}>
                      <Brain size={14} className={config.color} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm text-white">{memory.key}</span>
                        <span className={clsx('px-1.5 py-0.5 rounded text-[10px]', config.bgColor, config.color)}>
                          {config.label}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-1 truncate max-w-md">{memory.value}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="text-xs text-slate-400">{memory.accessCount} reads</div>
                      <div className="text-xs text-slate-500">{memory.size} bytes</div>
                    </div>
                    <ChevronRight
                      size={16}
                      className={clsx('text-slate-500 transition-transform', isExpanded && 'rotate-90')}
                    />
                  </div>
                </div>
              </button>

              {isExpanded && (
                <div className="px-4 pb-4 animate-fade-in">
                  <div className="p-3 rounded-lg bg-slate-900/50 border border-slate-700">
                    <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono">
                      {memory.value}
                    </pre>
                  </div>
                  <div className="flex items-center justify-between mt-3 text-xs text-slate-500">
                    <span>Last updated: {new Date(memory.timestamp).toLocaleString()}</span>
                    <button className="flex items-center gap-1 text-red-400 hover:text-red-300 transition-colors">
                      <Trash2 size={12} />
                      <span>Clear</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
