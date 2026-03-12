import { fetchApi } from './client'
import type { FetchOptions } from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CognitiveMemoryItem {
  id: string
  memory_type: string
  domain: string
  content: string
  importance: number
  confidence: number
  access_count: number
  tags: string[]
  framework: string | null
  structured_data: Record<string, unknown>
  source_type: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ScoredMemory {
  memory: CognitiveMemoryItem
  similarity_score: number
  recency_score: number
  importance_score: number
  composite_score: number
  confidence_level: string
}

export interface MemoryTreeNode {
  name: string
  count: number
  avg_importance: number
  children: Record<string, { count: number; avg_importance: number; memories: CognitiveMemoryItem[] }>
}

export interface MemoryStats {
  total: number
  active: number
  by_type: Record<string, number>
  by_domain: Record<string, number>
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createMemoryApi(opts: FetchOptions) {
  return {
    async recallMemories(
      query: string,
      domain?: string,
      k: number = 10,
      weights?: { similarity?: number; recency?: number; importance?: number }
    ) {
      return fetchApi<ScoredMemory[]>(
        `/enterprise/tenants/{tenant_id}/memory/recall`,
        {
          ...opts,
          method: 'POST',
          body: { query, domain, k, weights },
        }
      )
    },

    async rememberMemory(data: {
      content: string
      memory_type: string
      domain: string
      importance?: number
      confidence?: number
      tags?: string[]
      framework?: string
      structured_data?: Record<string, unknown>
      source_type?: string
    }) {
      return fetchApi<CognitiveMemoryItem>(
        `/enterprise/tenants/{tenant_id}/memory/remember`,
        {
          ...opts,
          method: 'POST',
          body: data,
        }
      )
    },

    async getMemoryTree() {
      return fetchApi<Record<string, MemoryTreeNode>>(
        `/enterprise/tenants/{tenant_id}/memory/tree`,
        opts
      )
    },

    async getMemoryStats() {
      return fetchApi<MemoryStats>(
        `/enterprise/tenants/{tenant_id}/memory/stats`,
        opts
      )
    },

    async getMemory(id: string) {
      return fetchApi<CognitiveMemoryItem>(
        `/enterprise/tenants/{tenant_id}/memory/${id}`,
        opts
      )
    },

    async forgetMemory(id: string) {
      return fetchApi<{ success: boolean; message: string }>(
        `/enterprise/tenants/{tenant_id}/memory/${id}`,
        { ...opts, method: 'DELETE' }
      )
    },

    async updateMemory(id: string, data: Partial<{
      content: string
      importance: number
      confidence: number
      tags: string[]
      is_active: boolean
      structured_data: Record<string, unknown>
    }>) {
      return fetchApi<CognitiveMemoryItem>(
        `/enterprise/tenants/{tenant_id}/memory/${id}`,
        {
          ...opts,
          method: 'PATCH',
          body: data,
        }
      )
    },
  }
}
