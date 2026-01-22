'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  Workflow, Plus, Link, Copy, CheckCircle, ExternalLink, Loader2, RefreshCw
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { QualityGradeBadge } from '@/components/quality/QualityGradeBadge'
import { createApiClient, N8nWorkflow, QualityAssessment } from '@/lib/api'

interface DisplayWorkflow {
  id: string
  workflowId: string
  workflowName: string
  webhookUrl: string
  registeredAt: string
  qualityGrade?: string
  qualityScore?: number
  qualityAssessmentId?: string
}

function mapWorkflow(w: N8nWorkflow, assessments: QualityAssessment[]): DisplayWorkflow {
  // Find the most recent quality assessment for this workflow
  const assessment = assessments.find(a => a.workflow_name === (w.workflow_name || `Workflow ${w.workflow_id}`))

  return {
    id: w.id,
    workflowId: w.workflow_id,
    workflowName: w.workflow_name || `Workflow ${w.workflow_id}`,
    webhookUrl: w.webhook_url,
    registeredAt: new Date(w.registered_at).toLocaleString(),
    qualityGrade: assessment?.overall_grade,
    qualityScore: assessment?.overall_score,
    qualityAssessmentId: assessment?.id,
  }
}

export default function N8nPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [workflows, setWorkflows] = useState<DisplayWorkflow[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isRegistering, setIsRegistering] = useState(false)
  const [showRegisterForm, setShowRegisterForm] = useState(false)
  const [newWorkflowId, setNewWorkflowId] = useState('')
  const [newWorkflowName, setNewWorkflowName] = useState('')
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<{ synced: number; errors: string[] } | null>(null)

  const loadWorkflows = useCallback(async () => {
    setIsLoading(true)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      // Load both workflows and quality assessments
      const [workflowsData, qualityRes] = await Promise.all([
        api.listN8nWorkflows(),
        api.listQualityAssessments({ pageSize: 100 }).catch(() => ({ assessments: [] })),
      ])

      setWorkflows(workflowsData.map(w => mapWorkflow(w, qualityRes.assessments)))
    } catch (err) {
      console.warn('Failed to load n8n workflows:', err)
      setWorkflows([])
    }
    setIsLoading(false)
  }, [getToken, tenantId])

  useEffect(() => {
    loadWorkflows()
  }, [loadWorkflows])

  const registerWorkflow = async () => {
    if (!newWorkflowId.trim()) {
      setError('Workflow ID is required')
      return
    }

    setIsRegistering(true)
    setError(null)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.registerN8nWorkflow(newWorkflowId, newWorkflowName || undefined)

      // Refresh list
      await loadWorkflows()
      setShowRegisterForm(false)
      setNewWorkflowId('')
      setNewWorkflowName('')
    } catch (err) {
      console.error('Failed to register workflow:', err)
      setError('Failed to register workflow. Please try again.')
    }
    setIsRegistering(false)
  }

  const copyWebhookUrl = (url: string) => {
    navigator.clipboard.writeText(url)
    setCopiedUrl(url)
    setTimeout(() => setCopiedUrl(null), 2000)
  }

  const syncFromN8n = async () => {
    setIsSyncing(true)
    setSyncResult(null)
    setError(null)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const result = await api.syncN8nExecutions(undefined, 50)

      setSyncResult({
        synced: result.synced_count,
        errors: result.errors,
      })

      // Refresh workflows list after sync
      await loadWorkflows()
    } catch (err) {
      console.error('Failed to sync from n8n:', err)
      setError('Failed to sync executions from n8n. Check backend logs.')
    }
    setIsSyncing(false)
  }

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-orange-600/20 rounded-lg">
                <Workflow className="w-6 h-6 text-orange-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">n8n Workflows</h1>
            </div>
            <p className="text-slate-400">
              Connect n8n workflows for automated trace ingestion
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              onClick={syncFromN8n}
              variant="secondary"
              leftIcon={<RefreshCw size={16} className={isSyncing ? 'animate-spin' : ''} />}
              disabled={isSyncing}
            >
              {isSyncing ? 'Syncing...' : 'Sync from n8n'}
            </Button>
            <Button
              onClick={() => setShowRegisterForm(true)}
              leftIcon={<Plus size={16} />}
            >
              Register Workflow
            </Button>
          </div>
        </div>

        {/* Sync Result Notification */}
        {syncResult && (
          <div className={`mb-4 p-4 rounded-lg border ${syncResult.errors.length > 0 ? 'bg-yellow-900/20 border-yellow-600' : 'bg-emerald-900/20 border-emerald-600'}`}>
            <div className="flex items-center gap-2">
              <CheckCircle className={`w-5 h-5 ${syncResult.errors.length > 0 ? 'text-yellow-400' : 'text-emerald-400'}`} />
              <span className="text-white font-medium">
                Synced {syncResult.synced} execution{syncResult.synced !== 1 ? 's' : ''} from n8n Cloud
              </span>
            </div>
            {syncResult.errors.length > 0 && (
              <div className="mt-2 text-sm text-yellow-400">
                {syncResult.errors.length} error{syncResult.errors.length !== 1 ? 's' : ''} occurred during sync
              </div>
            )}
          </div>
        )}

        {/* Register Form Modal */}
        {showRegisterForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 w-full max-w-md">
              <h2 className="text-lg font-semibold text-white mb-4">Register n8n Workflow</h2>

              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">
                    Workflow ID *
                  </label>
                  <input
                    type="text"
                    value={newWorkflowId}
                    onChange={(e) => setNewWorkflowId(e.target.value)}
                    placeholder="e.g., abc123..."
                    className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-orange-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-slate-300 block mb-2">
                    Workflow Name (Optional)
                  </label>
                  <input
                    type="text"
                    value={newWorkflowName}
                    onChange={(e) => setNewWorkflowName(e.target.value)}
                    placeholder="e.g., Customer Support Agent"
                    className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white text-sm focus:border-orange-500 focus:outline-none"
                  />
                </div>

                {error && (
                  <p className="text-red-400 text-sm">{error}</p>
                )}

                <div className="flex gap-3 pt-2">
                  <Button
                    onClick={registerWorkflow}
                    disabled={isRegistering}
                    loading={isRegistering}
                    className="flex-1"
                  >
                    Register
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setShowRegisterForm(false)
                      setError(null)
                    }}
                    disabled={isRegistering}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Workflow List */}
        <div className="bg-slate-800 rounded-xl border border-slate-700">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-orange-400 animate-spin" />
            </div>
          ) : workflows.length === 0 ? (
            <div className="text-center py-12 px-4">
              <Workflow className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400 mb-2">No workflows registered</p>
              <p className="text-slate-500 text-sm">
                Register an n8n workflow to start ingesting traces automatically
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-700">
              {workflows.map((workflow) => (
                <div key={workflow.id} className="p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-white font-medium">{workflow.workflowName}</span>
                        <span className="text-slate-500 text-xs font-mono bg-slate-700 px-2 py-0.5 rounded">
                          {workflow.workflowId}
                        </span>
                        {workflow.qualityGrade && (
                          <QualityGradeBadge grade={workflow.qualityGrade} size="sm" />
                        )}
                      </div>
                      <p className="text-slate-500 text-sm">
                        Registered: {workflow.registeredAt}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {workflow.qualityAssessmentId && (
                        <a
                          href={`/quality/${workflow.qualityAssessmentId}`}
                          className="text-sm text-blue-400 hover:text-blue-300"
                        >
                          View Quality
                        </a>
                      )}
                      <a
                        href={`https://pisama.app.n8n.cloud`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-slate-400 hover:text-white transition-colors"
                        title="Open in n8n Cloud"
                      >
                        <ExternalLink size={18} />
                      </a>
                    </div>
                  </div>

                  {/* Webhook URL */}
                  <div className="mt-3 p-3 bg-slate-900 rounded-lg">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <Link size={14} className="text-slate-500 flex-shrink-0" />
                        <code className="text-sm text-slate-400 truncate">
                          {workflow.webhookUrl}
                        </code>
                      </div>
                      <button
                        onClick={() => copyWebhookUrl(workflow.webhookUrl)}
                        className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors flex-shrink-0"
                      >
                        {copiedUrl === workflow.webhookUrl ? (
                          <CheckCircle size={16} className="text-emerald-400" />
                        ) : (
                          <Copy size={16} />
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Instructions */}
        <div className="mt-6 p-6 bg-slate-800/50 rounded-xl border border-slate-700">
          <h3 className="text-lg font-semibold text-white mb-4">Setup Instructions</h3>
          <ol className="space-y-3 text-sm text-slate-400">
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-orange-500/20 text-orange-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">1</span>
              <span>Register your n8n workflow ID above to get a webhook URL</span>
            </li>
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-orange-500/20 text-orange-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">2</span>
              <span>In your n8n workflow, add an HTTP Request node at the end</span>
            </li>
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-orange-500/20 text-orange-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">3</span>
              <span>Configure it to POST to the webhook URL with your workflow execution data</span>
            </li>
            <li className="flex gap-3">
              <span className="w-6 h-6 bg-orange-500/20 text-orange-400 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0">4</span>
              <span>Traces will automatically appear in your dashboard</span>
            </li>
          </ol>

          <div className="mt-4 p-4 bg-slate-900 rounded-lg">
            <p className="text-sm text-slate-500 mb-2">Example payload structure:</p>
            <pre className="text-xs text-slate-400 overflow-x-auto">
{`{
  "workflow_id": "your-workflow-id",
  "execution_id": "execution-123",
  "nodes": [...],
  "status": "success",
  "started_at": "2024-01-01T00:00:00Z"
}`}
            </pre>
          </div>
        </div>
      </div>
    </Layout>
  )
}
