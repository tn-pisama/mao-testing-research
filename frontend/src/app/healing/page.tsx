'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { Layout } from '@/components/common/Layout'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs'
import { HealingDashboard } from '@/components/healing/HealingDashboard'
import { ApprovalQueue } from '@/components/healing/ApprovalQueue'
import { VersionHistory } from '@/components/healing/VersionHistory'
import { RollbackConfirmModal } from '@/components/healing/RollbackConfirmModal'
import {
  createApiClient,
  HealingRecord,
  N8nConnection,
  WorkflowVersion,
  VerificationMetrics
} from '@/lib/api'
import { toast } from 'sonner'
import {
  Sparkles,
  Settings,
  GitBranch,
  AlertTriangle,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  Loader2,
  RefreshCw,
  ExternalLink,
  Wrench,
  ShieldCheck
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { useUserPreferences } from '@/lib/user-preferences'

export default function HealingPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const { isN8nUser, showAdvancedFeatures } = useUserPreferences()

  // n8n users see simplified view with friendly terminology
  const showSimplifiedView = isN8nUser && !showAdvancedFeatures

  const [activeTab, setActiveTab] = useState('healings')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Data
  const [healings, setHealings] = useState<HealingRecord[]>([])
  const [connections, setConnections] = useState<N8nConnection[]>([])
  const [versions, setVersions] = useState<WorkflowVersion[]>([])
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>('')
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>('')
  const [verificationMetrics, setVerificationMetrics] = useState<VerificationMetrics | null>(null)

  // Modals
  const [showAddConnection, setShowAddConnection] = useState(false)
  const [rollbackModal, setRollbackModal] = useState<{
    isOpen: boolean
    healingId: string
    workflowId?: string
    fixType?: string
  }>({ isOpen: false, healingId: '' })

  // Form state for add connection
  const [newConnection, setNewConnection] = useState({
    name: '',
    instance_url: '',
    api_key: ''
  })
  const [isAddingConnection, setIsAddingConnection] = useState(false)
  const [testingConnection, setTestingConnection] = useState<string | null>(null)
  const [deletingConnection, setDeletingConnection] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    if (!tenantId) return

    setIsLoading(true)
    setError(null)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      const [healingsRes, connectionsRes, metricsRes] = await Promise.all([
        api.listHealingRecords({ perPage: 50 }).catch((err) => {
          console.error('Failed to fetch healings:', err)
          toast.error('Could not load healing records')
          return { items: [], total: 0, page: 1, per_page: 50 }
        }),
        api.listN8nConnections().catch((err) => {
          console.error('Failed to fetch connections:', err)
          toast.error('Could not load n8n connections')
          return { items: [], total: 0 }
        }),
        api.getVerificationMetrics().catch(() => null),
      ])

      setHealings(healingsRes.items || [])
      setConnections(connectionsRes.items || [])
      setVerificationMetrics(metricsRes)
    } catch (err) {
      console.error('Failed to fetch healing data:', err)
      setError('Failed to load healing data')
    } finally {
      setIsLoading(false)
    }
  }, [tenantId, getToken])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Auto-poll every 15s when there are active healings
  useEffect(() => {
    const hasActive = healings.some(
      h => h.status === 'in_progress' || h.deployment_stage === 'staged'
    )
    if (!hasActive) return
    const interval = setInterval(fetchData, 15_000)
    return () => clearInterval(interval)
  }, [healings, fetchData])

  const fetchVersions = useCallback(async () => {
    if (!tenantId || !selectedWorkflowId || !selectedConnectionId) {
      setVersions([])
      return
    }

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const res = await api.getWorkflowVersions(selectedWorkflowId, selectedConnectionId)
      setVersions(res.versions || [])
    } catch (err) {
      console.error('Failed to fetch versions:', err)
      setVersions([])
    }
  }, [tenantId, selectedWorkflowId, selectedConnectionId, getToken])

  useEffect(() => {
    if (activeTab === 'history') {
      fetchVersions()
    }
  }, [activeTab, fetchVersions])

  // Healing actions
  const handlePromote = async (healingId: string) => {
    if (!tenantId) return
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.promoteHealing(healingId)
      toast.success('Fix promoted', {
        description: 'The fix is now live in your workflow.',
      })
      await fetchData()
    } catch (err: any) {
      if (err.status === 400 && err.message?.includes('erification')) {
        toast.warning('Verification required', {
          description: 'Please verify the fix before promoting it to production.',
        })
      } else {
        toast.error('Promotion failed', {
          description: err.message || 'Failed to promote the fix.',
        })
      }
    }
  }

  const handleReject = async (healingId: string) => {
    if (!tenantId) return
    if (!window.confirm('Reject this fix? The original workflow will be restored.')) return
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.rejectHealing(healingId)
      toast.success('Fix rejected', {
        description: 'The staged fix has been rejected.',
      })
      await fetchData()
    } catch (err: any) {
      toast.error('Rejection failed', {
        description: err.message || 'Failed to reject the fix.',
      })
    }
  }

  const handleVerify = async (healingId: string, level: number = 1) => {
    if (!tenantId) return
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const result = await api.verifyHealing(healingId, level)
      if (result.passed) {
        toast.success('Verification passed', {
          description: `Level ${result.level} checks passed. Confidence reduced by ${(result.confidence_reduction * 100).toFixed(0)}%.`,
        })
      } else {
        toast.error('Verification failed', {
          description: result.error || `${result.config_checks.filter((c: any) => !c.success).length} check(s) did not pass.`,
        })
      }
      await fetchData()
    } catch (err: any) {
      toast.error('Verification error', {
        description: err.message || 'Failed to verify the fix.',
      })
    }
  }

  const handleRollback = async (healingId: string) => {
    const healing = healings.find(h => h.id === healingId)
    setRollbackModal({
      isOpen: true,
      healingId,
      workflowId: healing?.workflow_id,
      fixType: healing?.fix_type
    })
  }

  const confirmRollback = async () => {
    if (!tenantId) return
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.rollbackHealing(rollbackModal.healingId)
      toast.success('Fix rolled back', {
        description: 'The original workflow has been restored.',
      })
      setRollbackModal({ isOpen: false, healingId: '' })
      await fetchData()
    } catch (err: any) {
      toast.error('Rollback failed', {
        description: err.message || 'Failed to roll back the fix.',
      })
    }
  }

  // Approval actions
  const handleApproveHealing = async (healingId: string, notes: string) => {
    if (!tenantId) return
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.approveHealing(healingId, { approved: true, notes: notes || undefined })
      toast.success('Healing approved', {
        description: 'The fix has been approved and healing has started.',
      })
      await fetchData()
    } catch (err: any) {
      toast.error('Approval failed', {
        description: err.message || 'Failed to approve healing.',
      })
    }
  }

  const handleRejectHealing = async (healingId: string, notes: string) => {
    if (!tenantId) return
    if (!window.confirm('Reject this healing request?')) return
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.approveHealing(healingId, { approved: false, notes: notes || undefined })
      toast.success('Healing rejected', {
        description: 'The healing request has been rejected.',
      })
      await fetchData()
    } catch (err: any) {
      toast.error('Rejection failed', {
        description: err.message || 'Failed to reject healing.',
      })
    }
  }

  const pendingApprovalCount = healings.filter(
    h => h.approval_required && h.status === 'pending'
  ).length

  const handleRestoreVersion = async (versionId: string) => {
    if (!tenantId) return
    if (!window.confirm('Restore this version? The current workflow will be overwritten.')) return
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.restoreVersion(versionId)
      toast.success('Version restored', {
        description: 'Workflow has been restored to the selected version.',
      })
      await fetchVersions()
      await fetchData()
    } catch (err: any) {
      toast.error('Restore failed', {
        description: err.message || 'Failed to restore version.',
      })
    }
  }

  // Connection actions
  const handleAddConnection = async () => {
    if (!tenantId || !newConnection.name || !newConnection.instance_url || !newConnection.api_key) return

    setIsAddingConnection(true)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.createN8nConnection(newConnection)
      toast.success('Connection added', {
        description: `${newConnection.name} has been configured.`,
      })
      setNewConnection({ name: '', instance_url: '', api_key: '' })
      setShowAddConnection(false)
      await fetchData()
    } catch (err: any) {
      toast.error('Failed to add connection', {
        description: err.message || 'Check the URL and API key.',
      })
    } finally {
      setIsAddingConnection(false)
    }
  }

  const handleTestConnection = async (connectionId: string) => {
    if (!tenantId) return
    setTestingConnection(connectionId)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.testN8nConnection(connectionId)
      toast.success('Connection verified', {
        description: 'Your n8n instance is reachable.',
      })
      await fetchData()
    } catch (err: any) {
      toast.error('Connection test failed', {
        description: err.message || 'Unable to connect to n8n instance.',
      })
    } finally {
      setTestingConnection(null)
    }
  }

  const handleDeleteConnection = async (connectionId: string) => {
    if (!tenantId) return
    if (!window.confirm('Delete this connection?')) return
    setDeletingConnection(connectionId)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.deleteN8nConnection(connectionId)
      toast.success('Connection deleted')
      await fetchData()
    } catch (err: any) {
      toast.error('Failed to delete connection', {
        description: err.message || 'Could not delete the connection.',
      })
    } finally {
      setDeletingConnection(null)
    }
  }

  // Get unique workflow IDs from healings for version history
  const workflowIds = [...new Set(healings.filter(h => h.workflow_id).map(h => h.workflow_id!))]

  return (
    <Layout>
      <div className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              {showSimplifiedView ? (
                <Wrench size={24} className="text-purple-400" />
              ) : (
                <Sparkles size={24} className="text-purple-400" />
              )}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">
                {showSimplifiedView ? 'Fixes' : 'Self-Healing'}
              </h1>
              <p className="text-sm text-slate-400">
                {showSimplifiedView
                  ? 'Review and apply fixes to your workflows'
                  : 'Manage automated fixes and staged deployments for n8n workflows'}
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            onClick={fetchData}
            leftIcon={<RefreshCw size={16} />}
          >
            Refresh
          </Button>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
            <AlertTriangle size={20} className="text-red-400" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-6">
            <TabsTrigger value="healings">
              {showSimplifiedView ? (
                <>
                  <Wrench size={14} className="mr-2" />
                  Pending Fixes
                </>
              ) : (
                <>
                  <Sparkles size={14} className="mr-2" />
                  Healings
                </>
              )}
            </TabsTrigger>
            <TabsTrigger value="approvals">
              <ShieldCheck size={14} className="mr-2" />
              Approvals{pendingApprovalCount > 0 ? ` (${pendingApprovalCount})` : ''}
            </TabsTrigger>
            <TabsTrigger value="connections">
              <Settings size={14} className="mr-2" />
              {showSimplifiedView ? 'Connections' : 'n8n Connections'}
            </TabsTrigger>
            <TabsTrigger value="history">
              <GitBranch size={14} className="mr-2" />
              {showSimplifiedView ? 'History' : 'Version History'}
            </TabsTrigger>
          </TabsList>

          {/* Healings Tab */}
          <TabsContent value="healings">
            <HealingDashboard
              healings={healings}
              isLoading={isLoading}
              verificationMetrics={verificationMetrics}
              onPromote={handlePromote}
              onReject={handleReject}
              onRollback={handleRollback}
              onVerify={handleVerify}
              onRefresh={fetchData}
            />
          </TabsContent>

          {/* Approvals Tab */}
          <TabsContent value="approvals">
            <ApprovalQueue
              healings={healings}
              isLoading={isLoading}
              onApprove={handleApproveHealing}
              onReject={handleRejectHealing}
            />
          </TabsContent>

          {/* Connections Tab */}
          <TabsContent value="connections">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-white">n8n Connections</h2>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setShowAddConnection(true)}
                  leftIcon={<Plus size={14} />}
                >
                  Add Connection
                </Button>
              </div>

              {isLoading ? (
                <Card>
                  <CardContent className="p-4">
                    <div className="animate-pulse space-y-3">
                      {[1, 2].map(i => (
                        <div key={i} className="h-16 bg-slate-700 rounded-lg" />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ) : connections.length === 0 ? (
                <Card>
                  <CardContent className="p-8 text-center text-slate-400">
                    <Settings size={32} className="mx-auto mb-3 opacity-50" />
                    <p className="text-sm">No n8n connections configured</p>
                    <p className="text-xs text-slate-500 mt-1">
                      Add a connection to apply fixes to your n8n workflows
                    </p>
                    <Button
                      variant="primary"
                      size="sm"
                      className="mt-4"
                      onClick={() => setShowAddConnection(true)}
                      leftIcon={<Plus size={14} />}
                    >
                      Add Connection
                    </Button>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-3">
                  {connections.map(conn => (
                    <Card key={conn.id}>
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className={`p-2 rounded-lg ${conn.is_active ? 'bg-green-500/20' : 'bg-slate-500/20'}`}>
                              {conn.is_active
                                ? <CheckCircle2 size={20} className="text-green-400" />
                                : <XCircle size={20} className="text-slate-400" />
                              }
                            </div>
                            <div>
                              <p className="text-sm font-medium text-white">{conn.name}</p>
                              <p className="text-xs text-slate-400">{conn.instance_url}</p>
                              {conn.last_error && (
                                <p className="text-xs text-red-400 mt-1">{conn.last_error}</p>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant={conn.is_active ? 'success' : 'default'} size="sm">
                              {conn.is_active ? 'Active' : 'Inactive'}
                            </Badge>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleTestConnection(conn.id)}
                              isLoading={testingConnection === conn.id}
                            >
                              Test
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => window.open(conn.instance_url, '_blank')}
                              leftIcon={<ExternalLink size={14} />}
                            >
                              Open
                            </Button>
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={() => handleDeleteConnection(conn.id)}
                              isLoading={deletingConnection === conn.id}
                              leftIcon={<Trash2 size={14} />}
                            >
                              Delete
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}

              {/* Add Connection Modal */}
              {showAddConnection && (
                <div className="fixed inset-0 z-50 flex items-center justify-center">
                  <div className="absolute inset-0 bg-black/60" onClick={() => setShowAddConnection(false)} />
                  <div className="relative bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md">
                    <h3 className="text-lg font-semibold text-white mb-4">Add n8n Connection</h3>
                    <div className="space-y-4">
                      <div>
                        <label className="text-sm text-slate-400 mb-1 block">Name</label>
                        <input
                          type="text"
                          value={newConnection.name}
                          onChange={(e) => setNewConnection({ ...newConnection, name: e.target.value })}
                          placeholder="Production n8n"
                          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="text-sm text-slate-400 mb-1 block">Instance URL</label>
                        <input
                          type="text"
                          value={newConnection.instance_url}
                          onChange={(e) => setNewConnection({ ...newConnection, instance_url: e.target.value })}
                          placeholder="https://your-instance.app.n8n.cloud"
                          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="text-sm text-slate-400 mb-1 block">API Key</label>
                        <input
                          type="password"
                          value={newConnection.api_key}
                          onChange={(e) => setNewConnection({ ...newConnection, api_key: e.target.value })}
                          placeholder="n8n_api_..."
                          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                    </div>
                    <div className="flex justify-end gap-2 mt-6">
                      <Button variant="ghost" onClick={() => setShowAddConnection(false)}>
                        Cancel
                      </Button>
                      <Button
                        variant="primary"
                        onClick={handleAddConnection}
                        isLoading={isAddingConnection}
                        disabled={!newConnection.name || !newConnection.instance_url || !newConnection.api_key}
                      >
                        Add Connection
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </TabsContent>

          {/* Version History Tab */}
          <TabsContent value="history">
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <label className="text-sm text-slate-400 mb-1 block">Workflow ID</label>
                  <select
                    value={selectedWorkflowId}
                    onChange={(e) => setSelectedWorkflowId(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Select a workflow...</option>
                    {workflowIds.map(id => (
                      <option key={id} value={id}>{id}</option>
                    ))}
                  </select>
                </div>
                <div className="flex-1">
                  <label className="text-sm text-slate-400 mb-1 block">Connection</label>
                  <select
                    value={selectedConnectionId}
                    onChange={(e) => setSelectedConnectionId(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Select a connection...</option>
                    {connections.map(conn => (
                      <option key={conn.id} value={conn.id}>{conn.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              {selectedWorkflowId && selectedConnectionId ? (
                <VersionHistory
                  versions={versions}
                  workflowId={selectedWorkflowId}
                  onRestore={handleRestoreVersion}
                  isLoading={false}
                />
              ) : (
                <Card>
                  <CardContent className="p-8 text-center text-slate-400">
                    <GitBranch size={32} className="mx-auto mb-3 opacity-50" />
                    <p className="text-sm">Select a workflow and connection to view version history</p>
                  </CardContent>
                </Card>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* Rollback Confirmation Modal */}
      <RollbackConfirmModal
        isOpen={rollbackModal.isOpen}
        onClose={() => setRollbackModal({ isOpen: false, healingId: '' })}
        onConfirm={confirmRollback}
        healingId={rollbackModal.healingId}
        workflowId={rollbackModal.workflowId}
        fixType={rollbackModal.fixType}
      />
    </Layout>
  )
}
