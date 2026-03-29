import { fetchApi } from './client'
import type { FetchOptions } from './client'

export interface ReviewQueueItem {
  id: string
  trace_id: string
  detection_type: string
  confidence: number
  method: string
  review_status: string
  details: Record<string, unknown>
  created_at: string
  explanation?: string
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[]
  total: number
  pending: number
  page: number
  per_page: number
}

export interface ReviewVerdict {
  detection_id: string
  verdict: 'confirmed' | 'false_positive' | 'disputed'
  notes?: string
  promote_to_golden?: boolean
}

export interface BatchReviewResponse {
  reviewed: number
  promoted: number
  errors: string[]
}

export interface ReviewStatsResponse {
  total_detections: number
  pending_review: number
  confirmed: number
  false_positives: number
  disputed: number
  promoted_to_golden: number
  agreement_rate: number
  by_type: Record<string, { pending: number; confirmed: number; false_positive: number; disputed: number }>
}

export function createReviewApi(opts: FetchOptions) {
  return {
    async getReviewQueue(params: {
      page?: number
      perPage?: number
      status?: string
      detectionType?: string
      confidenceMin?: number
      confidenceMax?: number
      sort?: string
    } = {}) {
      const query = new URLSearchParams()
      if (params.page) query.set('page', String(params.page))
      if (params.perPage) query.set('per_page', String(params.perPage))
      if (params.status) query.set('status', params.status)
      if (params.detectionType) query.set('detection_type', params.detectionType)
      if (params.confidenceMin !== undefined) query.set('confidence_min', String(params.confidenceMin))
      if (params.confidenceMax !== undefined) query.set('confidence_max', String(params.confidenceMax))
      if (params.sort) query.set('sort', params.sort)
      return fetchApi<ReviewQueueResponse>(
        `/tenants/{tenant_id}/review/queue?${query}`, opts
      )
    },

    async submitBatchReview(reviews: ReviewVerdict[], reviewerId?: string) {
      return fetchApi<BatchReviewResponse>(
        `/tenants/{tenant_id}/review/batch`,
        { ...opts, method: 'POST', body: { reviews, reviewer_id: reviewerId } }
      )
    },

    async promoteToGolden(detectionId: string) {
      return fetchApi<{ detection_id: string; golden_entry_created: boolean; message: string }>(
        `/tenants/{tenant_id}/review/promote/${detectionId}`,
        { ...opts, method: 'POST' }
      )
    },

    async getReviewStats() {
      return fetchApi<ReviewStatsResponse>(
        `/tenants/{tenant_id}/review/stats`, opts
      )
    },
  }
}
