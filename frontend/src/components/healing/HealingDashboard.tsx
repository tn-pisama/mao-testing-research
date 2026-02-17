'use client'

import { useState } from 'react'
import {
  Activity,
  CheckCircle2,
  Clock,
  XCircle,
  AlertTriangle,
  RefreshCw,
  ShieldCheck,
  type LucideIcon
} from 'lucide-react'
import { Card, CardContent } from '../ui/Card'
import { Button } from '../ui/Button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/Tabs'
import { HealingCard } from './HealingCard'
import { StagedFixBanner } from './StagedFixBanner'
import type { HealingRecord } from '@/lib/api'

interface HealingDashboardProps {
  healings: HealingRecord[]
  isLoading?: boolean
  onPromote: (healingId: string) => Promise<void>
  onReject: (healingId: string) => Promise<void>
  onRollback: (healingId: string) => Promise<void>
  onRefresh: () => void
}

interface StatsCardProps {
  title: string
  value: number
  icon: LucideIcon
  color: string
}

function StatsCard({ title, value, icon: Icon, color }: StatsCardProps) {
  const colorClasses = {
    blue: 'bg-blue-500/20 text-blue-400',
    green: 'bg-green-500/20 text-green-400',
    amber: 'bg-amber-500/20 text-amber-400',
    red: 'bg-red-500/20 text-red-400',
    purple: 'bg-purple-500/20 text-purple-400',
    slate: 'bg-slate-500/20 text-slate-400',
  }

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-500 mb-1">{title}</p>
            <p className="text-2xl font-bold text-white">{value}</p>
          </div>
          <div className={`p-3 rounded-lg ${colorClasses[color as keyof typeof colorClasses] || colorClasses.slate}`}>
            <Icon size={24} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function HealingDashboard({
  healings,
  isLoading = false,
  onPromote,
  onReject,
  onRollback,
  onRefresh
}: HealingDashboardProps) {
  const [activeTab, setActiveTab] = useState('all')

  // Calculate stats
  const stats = {
    total: healings.length,
    staged: healings.filter(h => h.deployment_stage === 'staged' || h.status === 'staged').length,
    applied: healings.filter(h => h.status === 'applied' || h.deployment_stage === 'promoted').length,
    failed: healings.filter(h => h.status === 'failed' || h.status === 'rejected').length,
    awaitingApproval: healings.filter(h => h.approval_required && h.status === 'pending').length,
  }

  // Filter healings by tab
  const filteredHealings = healings.filter(h => {
    switch (activeTab) {
      case 'staged':
        return h.deployment_stage === 'staged' || h.status === 'staged'
      case 'applied':
        return h.status === 'applied' || h.deployment_stage === 'promoted'
      case 'failed':
        return h.status === 'failed' || h.status === 'rejected'
      case 'pending':
        return h.status === 'pending' || h.status === 'in_progress'
      default:
        return true
    }
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        {/* Stats loading */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <Card key={i}>
              <CardContent className="p-4">
                <div className="animate-pulse">
                  <div className="h-3 bg-slate-700 rounded w-1/2 mb-2" />
                  <div className="h-8 bg-slate-700 rounded w-1/3" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* List loading */}
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="p-4">
                <div className="animate-pulse">
                  <div className="h-4 bg-slate-700 rounded w-1/4 mb-2" />
                  <div className="h-3 bg-slate-700 rounded w-1/2" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatsCard
          title="Total Healings"
          value={stats.total}
          icon={Activity}
          color="blue"
        />
        <StatsCard
          title="Awaiting Approval"
          value={stats.awaitingApproval}
          icon={ShieldCheck}
          color="purple"
        />
        <StatsCard
          title="Staged"
          value={stats.staged}
          icon={Clock}
          color="amber"
        />
        <StatsCard
          title="Applied"
          value={stats.applied}
          icon={CheckCircle2}
          color="green"
        />
        <StatsCard
          title="Failed / Rejected"
          value={stats.failed}
          icon={XCircle}
          color="red"
        />
      </div>

      {/* Staged Fix Banner */}
      <StagedFixBanner
        healings={healings}
        onPromote={onPromote}
        onReject={onReject}
      />

      {/* Healings List */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="all">
                All ({stats.total})
              </TabsTrigger>
              <TabsTrigger value="staged">
                Staged ({stats.staged})
              </TabsTrigger>
              <TabsTrigger value="applied">
                Applied ({stats.applied})
              </TabsTrigger>
              <TabsTrigger value="failed">
                Failed ({stats.failed})
              </TabsTrigger>
              <TabsTrigger value="pending">
                Pending
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <Button
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            leftIcon={<RefreshCw size={14} />}
          >
            Refresh
          </Button>
        </div>

        {filteredHealings.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center text-slate-400">
              <AlertTriangle size={32} className="mx-auto mb-3 opacity-50" />
              <p className="text-sm">No healing records found</p>
              <p className="text-xs text-slate-500 mt-1">
                Healing records are created when fixes are applied to detected issues
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {filteredHealings.map((healing) => (
              <HealingCard
                key={healing.id}
                healing={healing}
                onPromote={onPromote}
                onReject={onReject}
                onRollback={onRollback}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
