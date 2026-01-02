'use client'

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useTenant } from '@/hooks/useTenant'
import {
  Upload, Plus, CheckCircle, XCircle, Clock,
  FileJson, Database, Loader2, RefreshCw
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { createApiClient, ImportJob } from '@/lib/api'

interface DisplayImportJob {
  id: string
  sourceType: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  createdAt: string
  startedAt?: string
  completedAt?: string
  recordsProcessed: number
  recordsFailed: number
  errorMessage?: string
}

function mapImportJob(job: ImportJob): DisplayImportJob {
  return {
    id: job.id,
    sourceType: job.source_type,
    status: job.status as DisplayImportJob['status'],
    createdAt: new Date(job.created_at).toLocaleString(),
    startedAt: job.started_at ? new Date(job.started_at).toLocaleString() : undefined,
    completedAt: job.completed_at ? new Date(job.completed_at).toLocaleString() : undefined,
    recordsProcessed: job.records_processed,
    recordsFailed: job.records_failed,
    errorMessage: job.error_message
  }
}

const SOURCE_TYPES = [
  { id: 'langsmith', name: 'LangSmith', description: 'Import traces from LangSmith' },
  { id: 'otel', name: 'OpenTelemetry', description: 'Import from OTEL collector' },
  { id: 'json', name: 'JSON File', description: 'Upload JSON trace file' },
  { id: 'jsonl', name: 'JSONL File', description: 'Upload JSONL trace file' },
]

export default function ImportPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [jobs, setJobs] = useState<DisplayImportJob[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [selectedSource, setSelectedSource] = useState<string>('langsmith')
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Config fields
  const [configUrl, setConfigUrl] = useState('')
  const [configApiKey, setConfigApiKey] = useState('')

  const loadJobs = useCallback(async () => {
    setIsLoading(true)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const data = await api.listImportJobs()
      setJobs(data.map(mapImportJob))
    } catch (err) {
      console.warn('Failed to load import jobs:', err)
      setJobs([])
    }
    setIsLoading(false)
  }, [getToken, tenantId])

  useEffect(() => {
    loadJobs()
  }, [loadJobs])

  const createJob = async () => {
    setIsCreating(true)
    setError(null)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      const config: Record<string, any> = {}
      if (configUrl) config.url = configUrl
      if (configApiKey) config.api_key = configApiKey

      await api.createImportJob(selectedSource, config)
      await loadJobs()
      setShowCreateForm(false)
      setConfigUrl('')
      setConfigApiKey('')
    } catch (err) {
      console.error('Failed to create import job:', err)
      setError('Failed to create import job. Please try again.')
    }
    setIsCreating(false)
  }

  const getStatusIcon = (status: DisplayImportJob['status']) => {
    switch (status) {
      case 'completed': return <CheckCircle className="text-emerald-400" size={18} />
      case 'failed': return <XCircle className="text-red-400" size={18} />
      case 'running': return <Loader2 className="text-amber-400 animate-spin" size={18} />
      default: return <Clock className="text-slate-400" size={18} />
    }
  }

  const getStatusColor = (status: DisplayImportJob['status']) => {
    switch (status) {
      case 'completed': return 'bg-emerald-400/10 text-emerald-400'
      case 'failed': return 'bg-red-400/10 text-red-400'
      case 'running': return 'bg-amber-400/10 text-amber-400'
      default: return 'bg-slate-400/10 text-slate-400'
    }
  }

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-blue-600/20 rounded-lg">
                <Upload className="w-6 h-6 text-blue-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">Import Jobs</h1>
            </div>
            <p className="text-slate-400">
              Import traces from external sources
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={loadJobs}
              leftIcon={<RefreshCw size={16} />}
            >
              Refresh
            </Button>
            <Button
              onClick={() => setShowCreateForm(true)}
              leftIcon={<Plus size={16} />}
            >
              New Import
            </Button>
          </div>
        </div>

        {/* Create Form Modal */}
        {showCreateForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 w-full max-w-md">
              <h2 className="text-lg font-semibold text-white mb-4">Create Import Job</h2>

              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">
                    Source Type
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {SOURCE_TYPES.map((source) => (
                      <button
                        key={source.id}
                        onClick={() => setSelectedSource(source.id)}
                        className={`p-3 rounded-lg border text-left transition-all ${
                          selectedSource === source.id
                            ? 'border-blue-500 bg-blue-500/10'
                            : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                        }`}
                      >
                        <span className="text-white text-sm font-medium">{source.name}</span>
                        <p className="text-slate-500 text-xs mt-0.5">{source.description}</p>
                      </button>
                    ))}
                  </div>
                </div>

                {(selectedSource === 'langsmith' || selectedSource === 'otel') && (
                  <>
                    <div>
                      <label className="text-sm font-medium text-slate-300 block mb-2">
                        Endpoint URL
                      </label>
                      <input
                        type="text"
                        value={configUrl}
                        onChange={(e) => setConfigUrl(e.target.value)}
                        placeholder={selectedSource === 'langsmith' ? 'https://api.smith.langchain.com' : 'http://localhost:4318'}
                        className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-blue-500 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="text-sm font-medium text-slate-300 block mb-2">
                        API Key (if required)
                      </label>
                      <input
                        type="password"
                        value={configApiKey}
                        onChange={(e) => setConfigApiKey(e.target.value)}
                        placeholder="Enter API key..."
                        className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-blue-500 focus:outline-none"
                      />
                    </div>
                  </>
                )}

                {(selectedSource === 'json' || selectedSource === 'jsonl') && (
                  <div className="p-4 border-2 border-dashed border-slate-600 rounded-lg text-center">
                    <FileJson className="w-12 h-12 text-slate-500 mx-auto mb-2" />
                    <p className="text-slate-400 text-sm">
                      Drag and drop a {selectedSource.toUpperCase()} file here, or click to browse
                    </p>
                    <p className="text-slate-500 text-xs mt-1">
                      File upload coming soon
                    </p>
                  </div>
                )}

                {error && (
                  <p className="text-red-400 text-sm">{error}</p>
                )}

                <div className="flex gap-3 pt-2">
                  <Button
                    onClick={createJob}
                    disabled={isCreating}
                    loading={isCreating}
                    className="flex-1"
                  >
                    Start Import
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setShowCreateForm(false)
                      setError(null)
                    }}
                    disabled={isCreating}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Jobs List */}
        <div className="bg-slate-800 rounded-xl border border-slate-700">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
            </div>
          ) : jobs.length === 0 ? (
            <div className="text-center py-12 px-4">
              <Database className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400 mb-2">No import jobs yet</p>
              <p className="text-slate-500 text-sm">
                Create an import job to bring traces into the platform
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-700">
              {jobs.map((job) => (
                <div key={job.id} className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      {getStatusIcon(job.status)}
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-white font-medium capitalize">
                            {job.sourceType} Import
                          </span>
                          <span className={`px-2 py-0.5 rounded-full text-xs ${getStatusColor(job.status)}`}>
                            {job.status}
                          </span>
                        </div>
                        <p className="text-slate-500 text-sm mt-1">
                          Created: {job.createdAt}
                        </p>
                        {job.completedAt && (
                          <p className="text-slate-500 text-sm">
                            Completed: {job.completedAt}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-white font-mono">
                        {job.recordsProcessed.toLocaleString()} records
                      </p>
                      {job.recordsFailed > 0 && (
                        <p className="text-red-400 text-sm">
                          {job.recordsFailed} failed
                        </p>
                      )}
                    </div>
                  </div>

                  {job.errorMessage && (
                    <div className="mt-3 p-3 bg-red-500/10 rounded-lg">
                      <p className="text-red-400 text-sm">{job.errorMessage}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Supported Formats */}
        <div className="mt-6 p-6 bg-slate-800/50 rounded-xl border border-slate-700">
          <h3 className="text-lg font-semibold text-white mb-4">Supported Import Sources</h3>
          <div className="grid md:grid-cols-2 gap-4">
            {SOURCE_TYPES.map((source) => (
              <div key={source.id} className="p-4 bg-slate-900/50 rounded-lg">
                <h4 className="font-medium text-white mb-1">{source.name}</h4>
                <p className="text-sm text-slate-400">{source.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  )
}
