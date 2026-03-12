import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { GitBranch, Plus, Globe } from 'lucide-react'
import type { N8nWorkflow } from '@/lib/api'
import { EmptyState } from './EmptyState'

export function N8nIntegrationTab({ workflows }: { workflows: N8nWorkflow[] }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">n8n Workflows</h2>
        <a
          href="/n8n"
          className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-700 rounded-lg text-white text-sm transition-colors"
        >
          <Plus size={14} />
          Manage Workflows
        </a>
      </div>

      {workflows.length === 0 ? (
        <EmptyState
          icon={GitBranch}
          title="No n8n workflows registered"
          description="Register your n8n workflows to start monitoring executions."
        />
      ) : (
        <Card>
          <div className="divide-y divide-zinc-700">
            {workflows.map((w) => (
              <div key={w.id} className="p-4 flex items-center justify-between">
                <div>
                  <div className="text-white font-medium">
                    {w.workflow_name || w.workflow_id}
                  </div>
                  <div className="text-xs text-zinc-400 mt-1 flex items-center gap-3">
                    <span>ID: {w.workflow_id}</span>
                    {w.ingestion_mode && (
                      <Badge variant="default" size="sm">{w.ingestion_mode}</Badge>
                    )}
                  </div>
                </div>
                <div className="text-xs text-zinc-500 flex items-center gap-2">
                  <Globe size={12} />
                  {w.webhook_url}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
