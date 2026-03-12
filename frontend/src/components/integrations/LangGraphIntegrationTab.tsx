import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Network, Plus, Globe, Key } from 'lucide-react'
import type { LangGraphDeployment, LangGraphAssistant } from '@/lib/api'
import { EmptyState } from './EmptyState'

export function LangGraphIntegrationTab({
  deployments,
  assistants,
}: {
  deployments: LangGraphDeployment[]
  assistants: LangGraphAssistant[]
}) {
  return (
    <div className="space-y-6">
      {/* Deployments */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">LangGraph Deployments</h2>
          <a
            href="/langgraph"
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-white text-sm transition-colors"
          >
            <Plus size={14} />
            Manage Deployments
          </a>
        </div>
        {deployments.length === 0 ? (
          <EmptyState
            icon={Network}
            title="No LangGraph deployments connected"
            description="Register a LangGraph deployment to monitor graph runs."
          />
        ) : (
          <Card>
            <div className="divide-y divide-zinc-700">
              {deployments.map((dep) => (
                <div key={dep.id} className="p-4 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{dep.name}</span>
                      {dep.is_active ? (
                        <Badge variant="success" size="sm">Active</Badge>
                      ) : (
                        <Badge variant="default" size="sm">Inactive</Badge>
                      )}
                    </div>
                    <div className="text-xs text-zinc-400 mt-1 flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <Globe size={12} />
                        {dep.api_url}
                      </span>
                      {dep.graph_name && <span>Graph: {dep.graph_name}</span>}
                      <Badge variant="default" size="sm">{dep.ingestion_mode}</Badge>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>

      {/* Assistants */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Registered Assistants</h2>
        {assistants.length === 0 ? (
          <EmptyState
            icon={Key}
            title="No assistants registered"
            description="Register assistants within your LangGraph deployments for monitoring."
          />
        ) : (
          <Card>
            <div className="divide-y divide-zinc-700">
              {assistants.map((asst) => (
                <div key={asst.id} className="p-4 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">
                        {asst.name || asst.assistant_id}
                      </span>
                      {asst.monitoring_enabled ? (
                        <Badge variant="success" size="sm">Monitoring</Badge>
                      ) : (
                        <Badge variant="default" size="sm">Paused</Badge>
                      )}
                    </div>
                    <div className="text-xs text-zinc-400 mt-1 flex items-center gap-3">
                      <span>Graph: {asst.graph_id}</span>
                      <span>ID: {asst.assistant_id}</span>
                    </div>
                  </div>
                  <div className="text-right text-xs text-zinc-400">
                    <div>{asst.total_runs} runs</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
