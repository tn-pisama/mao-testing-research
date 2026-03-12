'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect } from 'react'
import { Layout } from '@/components/common/Layout'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs'
import { HealingDashboard } from '@/components/healing/HealingDashboard'
import { ApprovalQueue } from '@/components/healing/ApprovalQueue'
import { VersionHistory } from '@/components/healing/VersionHistory'
import { RollbackConfirmModal } from '@/components/healing/RollbackConfirmModal'
import { ConnectionsManager } from '@/components/healing/ConnectionsManager'
import { toast } from 'sonner'
import {
  Sparkles,
  Settings,
  GitBranch,
  AlertTriangle,
  RefreshCw,
  Wrench,
  ShieldCheck,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { useUserPreferences } from '@/lib/user-preferences'
import {
  useHealingRecordsQuery,
  useN8nConnectionsQuery,
  useVerificationMetricsQuery,
  useWorkflowVersionsQuery,
  usePromoteHealingMutation,
  useRejectHealingMutation,
  useVerifyHealingMutation,
  useRollbackHealingMutation,
  useApproveHealingMutation,
  useRestoreVersionMutation,
} from '@/hooks/useQueries'

export default function HealingPage() {
  const { isN8nUser, showAdvancedFeatures } = useUserPreferences()
  const showSimplifiedView = isN8nUser && !showAdvancedFeatures

  const [activeTab, setActiveTab] = useState('healings')

  // --- Data fetching via TanStack Query ---
  const { records: healings, isLoading, isDemoMode, refetch: refetchHealings } =
    useHealingRecordsQuery({ perPage: 50 })
  const { connections } = useN8nConnectionsQuery()
  const { data: verificationMetrics } = useVerificationMetricsQuery()

  // Version history
  const [selectedWorkflowId, setSelectedWorkflowId] = useState('')
  const [selectedConnectionId, setSelectedConnectionId] = useState('')
  const { versions } = useWorkflowVersionsQuery(selectedWorkflowId, selectedConnectionId)

  // Rollback modal
  const [rollbackModal, setRollbackModal] = useState<{
    isOpen: boolean
    healingId: string
    workflowId?: string
    fixType?: string
  }>({ isOpen: false, healingId: '' })

  // Auto-poll when active healings exist
  const hasActive = healings.some(
    h => h.status === 'in_progress' || h.deployment_stage === 'staged'
  )
  useEffect(() => {
    if (!hasActive) return
    const interval = setInterval(() => refetchHealings(), 15_000)
    return () => clearInterval(interval)
  }, [hasActive, refetchHealings])

  // --- Mutations ---
  const promoteMutation = usePromoteHealingMutation()
  const rejectMutation = useRejectHealingMutation()
  const verifyMutation = useVerifyHealingMutation()
  const rollbackMutation = useRollbackHealingMutation()
  const approveMutation = useApproveHealingMutation()
  const restoreVersionMutation = useRestoreVersionMutation()

  // --- Handlers ---
  const handlePromote = async (healingId: string) => {
    try {
      await promoteMutation.mutateAsync(healingId)
      toast.success('Fix promoted', { description: 'The fix is now live in your workflow.' })
    } catch (err) {
      const e = err as Error & { status?: number }
      if (e.status === 400 && e.message?.includes('erification')) {
        toast.warning('Verification required', {
          description: 'Please verify the fix before promoting it to production.',
        })
      } else {
        toast.error('Promotion failed', { description: e.message || 'Failed to promote the fix.' })
      }
    }
  }

  const handleReject = async (healingId: string) => {
    if (!window.confirm('Reject this fix? The original workflow will be restored.')) return
    try {
      await rejectMutation.mutateAsync(healingId)
      toast.success('Fix rejected', { description: 'The staged fix has been rejected.' })
    } catch (err) {
      toast.error('Rejection failed', { description: (err as Error).message })
    }
  }

  const handleVerify = async (healingId: string, level: number = 1) => {
    try {
      const result = await verifyMutation.mutateAsync({ healingId, level })
      const r = result as { passed: boolean; level: number; confidence_reduction: number; error?: string; config_checks: Array<{ success: boolean }> }
      if (r.passed) {
        toast.success('Verification passed', {
          description: `Level ${r.level} checks passed. Confidence reduced by ${(r.confidence_reduction * 100).toFixed(0)}%.`,
        })
      } else {
        toast.error('Verification failed', {
          description: r.error || `${r.config_checks.filter(c => !c.success).length} check(s) did not pass.`,
        })
      }
    } catch (err) {
      toast.error('Verification error', { description: (err as Error).message })
    }
  }

  const handleRollback = async (healingId: string) => {
    const healing = healings.find(h => h.id === healingId)
    setRollbackModal({
      isOpen: true,
      healingId,
      workflowId: healing?.workflow_id,
      fixType: healing?.fix_type,
    })
  }

  const confirmRollback = async () => {
    try {
      await rollbackMutation.mutateAsync(rollbackModal.healingId)
      toast.success('Fix rolled back', { description: 'The original workflow has been restored.' })
      setRollbackModal({ isOpen: false, healingId: '' })
    } catch (err) {
      toast.error('Rollback failed', { description: (err as Error).message })
    }
  }

  const handleApproveHealing = async (healingId: string, notes: string) => {
    try {
      await approveMutation.mutateAsync({ healingId, approved: true, notes: notes || undefined })
      toast.success('Healing approved', { description: 'The fix has been approved and healing has started.' })
    } catch (err) {
      toast.error('Approval failed', { description: (err as Error).message })
    }
  }

  const handleRejectHealing = async (healingId: string, notes: string) => {
    if (!window.confirm('Reject this healing request?')) return
    try {
      await approveMutation.mutateAsync({ healingId, approved: false, notes: notes || undefined })
      toast.success('Healing rejected', { description: 'The healing request has been rejected.' })
    } catch (err) {
      toast.error('Rejection failed', { description: (err as Error).message })
    }
  }

  const handleRestoreVersion = async (versionId: string) => {
    if (!window.confirm('Restore this version? The current workflow will be overwritten.')) return
    try {
      await restoreVersionMutation.mutateAsync(versionId)
      toast.success('Version restored', { description: 'Workflow has been restored to the selected version.' })
    } catch (err) {
      toast.error('Restore failed', { description: (err as Error).message })
    }
  }

  const pendingApprovalCount = healings.filter(
    h => h.approval_required && h.status === 'pending'
  ).length

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
              <p className="text-sm text-zinc-400">
                {showSimplifiedView
                  ? 'Review and apply fixes to your workflows'
                  : 'Manage automated fixes and staged deployments for n8n workflows'}
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            onClick={() => refetchHealings()}
            leftIcon={<RefreshCw size={16} />}
          >
            Refresh
          </Button>
        </div>

        {/* Demo Mode Banner */}
        {isDemoMode && (
          <div className="mb-6 p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-center gap-3">
            <AlertTriangle size={20} className="text-amber-400" />
            <p className="text-sm text-amber-300">
              Demo mode — API unavailable. Showing sample data.
            </p>
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
              verificationMetrics={verificationMetrics ?? null}
              onPromote={handlePromote}
              onReject={handleReject}
              onRollback={handleRollback}
              onVerify={handleVerify}
              onRefresh={() => refetchHealings()}
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
            <ConnectionsManager
              connections={connections}
              isLoading={isLoading}
            />
          </TabsContent>

          {/* Version History Tab */}
          <TabsContent value="history">
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <label className="text-sm text-zinc-400 mb-1 block">Workflow ID</label>
                  <select
                    value={selectedWorkflowId}
                    onChange={(e) => setSelectedWorkflowId(e.target.value)}
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Select a workflow...</option>
                    {workflowIds.map(id => (
                      <option key={id} value={id}>{id}</option>
                    ))}
                  </select>
                </div>
                <div className="flex-1">
                  <label className="text-sm text-zinc-400 mb-1 block">Connection</label>
                  <select
                    value={selectedConnectionId}
                    onChange={(e) => setSelectedConnectionId(e.target.value)}
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                  <CardContent className="p-8 text-center text-zinc-400">
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
