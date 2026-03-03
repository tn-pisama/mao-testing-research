'use client'

export const dynamic = 'force-dynamic'

import { useState, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  BarChart3, Download, Copy, CheckCircle, Loader2,
  Activity, TrendingUp, Clock
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { createApiClient, MetricsExport } from '@/lib/api'

type ExportFormat = 'prometheus' | 'json' | 'csv' | 'openmetrics'

interface FormatInfo {
  id: ExportFormat
  name: string
  description: string
  extension: string
}

const EXPORT_FORMATS: FormatInfo[] = [
  { id: 'prometheus', name: 'Prometheus', description: 'Prometheus text exposition format', extension: 'txt' },
  { id: 'openmetrics', name: 'OpenMetrics', description: 'OpenMetrics standard format', extension: 'txt' },
  { id: 'json', name: 'JSON', description: 'Structured JSON format', extension: 'json' },
  { id: 'csv', name: 'CSV', description: 'Comma-separated values', extension: 'csv' },
]

export default function MetricsPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('prometheus')
  const [isExporting, setIsExporting] = useState(false)
  const [exportResult, setExportResult] = useState<MetricsExport | null>(null)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runExport = useCallback(async () => {
    setIsExporting(true)
    setError(null)
    setExportResult(null)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const result = await api.exportMetrics(selectedFormat)
      setExportResult(result)
    } catch (err) {
      console.error('Export failed:', err)
      setError('Failed to export metrics. Please try again.')
    }
    setIsExporting(false)
  }, [selectedFormat, getToken, tenantId])

  const copyToClipboard = () => {
    if (exportResult?.data) {
      navigator.clipboard.writeText(exportResult.data)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const downloadFile = () => {
    if (!exportResult?.data) return

    const format = EXPORT_FORMATS.find(f => f.id === selectedFormat)
    const blob = new Blob([exportResult.data], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `metrics-${new Date().toISOString().split('T')[0]}.${format?.extension || 'txt'}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-indigo-600/20 rounded-lg">
              <BarChart3 className="w-6 h-6 text-indigo-400" />
            </div>
            <h1 className="text-2xl font-bold text-white">Metrics Export</h1>
          </div>
          <p className="text-zinc-400">
            Export platform metrics for monitoring and alerting
          </p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Format Selection */}
          <div className="space-y-4">
            <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
              <h3 className="text-sm font-medium text-zinc-300 mb-3">Export Format</h3>
              <div className="space-y-2">
                {EXPORT_FORMATS.map((format) => (
                  <button
                    key={format.id}
                    onClick={() => {
                      setSelectedFormat(format.id)
                      setExportResult(null)
                    }}
                    className={`w-full p-3 rounded-lg border text-left transition-all ${
                      selectedFormat === format.id
                        ? 'border-indigo-500 bg-indigo-500/10'
                        : 'border-zinc-600 bg-zinc-700/50 hover:border-zinc-500'
                    }`}
                  >
                    <span className="text-white text-sm font-medium">{format.name}</span>
                    <p className="text-zinc-500 text-xs mt-0.5">{format.description}</p>
                  </button>
                ))}
              </div>
            </div>

            <Button
              onClick={runExport}
              disabled={isExporting}
              loading={isExporting}
              className="w-full"
              leftIcon={<Download size={16} />}
            >
              {isExporting ? 'Exporting...' : 'Export Metrics'}
            </Button>
          </div>

          {/* Results */}
          <div className="lg:col-span-2">
            {error && (
              <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg mb-4">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            {exportResult ? (
              <div className="bg-zinc-800 rounded-xl border border-zinc-700">
                <div className="flex items-center justify-between p-4 border-b border-zinc-700">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="text-emerald-400" size={18} />
                    <span className="text-white font-medium">Export Complete</span>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={copyToClipboard}
                      leftIcon={copied ? <CheckCircle size={14} /> : <Copy size={14} />}
                    >
                      {copied ? 'Copied!' : 'Copy'}
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={downloadFile}
                      leftIcon={<Download size={14} />}
                    >
                      Download
                    </Button>
                  </div>
                </div>

                <div className="p-4">
                  <div className="flex items-center gap-4 text-sm text-zinc-400 mb-4">
                    <span>Format: {exportResult.format}</span>
                    <span>Generated: {new Date(exportResult.timestamp).toLocaleString()}</span>
                  </div>

                  <pre className="bg-zinc-900 rounded-lg p-4 text-sm text-zinc-300 overflow-x-auto max-h-96 overflow-y-auto font-mono">
                    {exportResult.data}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center bg-zinc-800/50 rounded-xl border border-zinc-700 border-dashed p-8">
                <div className="text-center text-zinc-500">
                  <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium mb-2">No export yet</p>
                  <p className="text-sm">Select a format and click Export to generate metrics</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Available Metrics */}
        <div className="mt-6 p-6 bg-zinc-800/50 rounded-xl border border-zinc-700">
          <h3 className="text-lg font-semibold text-white mb-4">Available Metrics</h3>
          <div className="grid md:grid-cols-3 gap-4">
            <div className="p-4 bg-zinc-900/50 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="text-indigo-400" size={18} />
                <h4 className="font-medium text-white">Trace Metrics</h4>
              </div>
              <ul className="text-sm text-zinc-400 space-y-1">
                <li>mao_traces_total</li>
                <li>mao_traces_by_status</li>
                <li>mao_trace_duration_seconds</li>
                <li>mao_trace_tokens_total</li>
              </ul>
            </div>
            <div className="p-4 bg-zinc-900/50 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="text-emerald-400" size={18} />
                <h4 className="font-medium text-white">Detection Metrics</h4>
              </div>
              <ul className="text-sm text-zinc-400 space-y-1">
                <li>mao_detections_total</li>
                <li>mao_detections_by_type</li>
                <li>mao_detection_confidence</li>
                <li>mao_false_positives_total</li>
              </ul>
            </div>
            <div className="p-4 bg-zinc-900/50 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="text-amber-400" size={18} />
                <h4 className="font-medium text-white">Performance Metrics</h4>
              </div>
              <ul className="text-sm text-zinc-400 space-y-1">
                <li>mao_api_latency_seconds</li>
                <li>mao_ingestion_rate</li>
                <li>mao_detection_latency_ms</li>
                <li>mao_cost_cents_total</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Integration Instructions */}
        <div className="mt-6 p-6 bg-zinc-800/50 rounded-xl border border-zinc-700">
          <h3 className="text-lg font-semibold text-white mb-4">Integration Examples</h3>
          <div className="space-y-4">
            <div>
              <h4 className="text-sm font-medium text-zinc-300 mb-2">Prometheus</h4>
              <pre className="bg-zinc-900 rounded-lg p-3 text-sm text-zinc-400 overflow-x-auto">
{`# prometheus.yml
scrape_configs:
  - job_name: 'mao-testing'
    static_configs:
      - targets: ['your-api-url/metrics']
    bearer_token: 'your-api-key'`}
              </pre>
            </div>
            <div>
              <h4 className="text-sm font-medium text-zinc-300 mb-2">Grafana</h4>
              <p className="text-sm text-zinc-400">
                Use the Prometheus data source with the scraped metrics to create custom dashboards.
              </p>
            </div>
            <div>
              <h4 className="text-sm font-medium text-zinc-300 mb-2">Datadog</h4>
              <pre className="bg-zinc-900 rounded-lg p-3 text-sm text-zinc-400 overflow-x-auto">
{`# datadog.yaml
instances:
  - openmetrics_endpoint: 'https://your-api-url/metrics'
    headers:
      Authorization: 'Bearer your-api-key'`}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}
