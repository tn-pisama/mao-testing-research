import { fetchApi } from './client'
import type { FetchOptions } from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DiagnoseDetection {
  category: string
  detected: boolean
  confidence: number
  severity: string
  title: string
  description: string
  evidence: Record<string, unknown>[]
  affected_spans: string[]
  suggested_fix?: string
}

export interface DiagnoseAutoFix {
  description: string
  confidence: number
  action: string
}

export interface DiagnoseResult {
  trace_id: string
  analyzed_at: string
  has_failures: boolean
  failure_count: number
  primary_failure?: DiagnoseDetection
  all_detections: DiagnoseDetection[]
  total_spans: number
  error_spans: number
  total_tokens: number
  duration_ms: number
  root_cause_explanation?: string
  self_healing_available: boolean
  auto_fix_preview?: DiagnoseAutoFix
  detection_time_ms: number
  detectors_run: string[]
}

export interface DiagnoseQuickCheckResult {
  has_failures: boolean
  failure_count: number
  primary_category?: string
  primary_severity?: string
  message: string
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createDiagnoseApi(opts: FetchOptions) {
  const token = opts.token

  return {
    async diagnoseTrace(content: string, format: string = 'auto', includeFixes: boolean = true) {
      return fetchApi<DiagnoseResult>('/diagnose/why-failed', {
        method: 'POST',
        body: { content, format, include_fixes: includeFixes, run_all_detections: true },
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      })
    },

    async diagnoseQuickCheck(content: string, format: string = 'auto') {
      return fetchApi<DiagnoseQuickCheckResult>('/diagnose/quick-check', {
        method: 'POST',
        body: { content, format },
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      })
    },

    async getDiagnoseFormats() {
      return fetchApi<{ formats: Array<{ name: string; description: string; default?: boolean; example_marker?: string }> }>(
        '/diagnose/formats',
        {}
      )
    },
  }
}
