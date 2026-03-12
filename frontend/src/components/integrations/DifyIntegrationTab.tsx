import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Workflow, Globe, Key } from 'lucide-react'
import type { DifyInstance, DifyApp } from '@/lib/api'
import { EmptyState } from './EmptyState'

export function DifyIntegrationTab({
  instances,
  apps,
}: {
  instances: DifyInstance[]
  apps: DifyApp[]
}) {
  return (
    <div className="space-y-6">
      {/* Instances */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Dify Instances</h2>
        {instances.length === 0 ? (
          <EmptyState
            icon={Workflow}
            title="No Dify instances connected"
            description="Register a Dify instance to monitor workflow runs and app executions."
          />
        ) : (
          <Card>
            <div className="divide-y divide-zinc-700">
              {instances.map((inst) => (
                <div key={inst.id} className="p-4 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{inst.name}</span>
                      {inst.is_active ? (
                        <Badge variant="success" size="sm">Active</Badge>
                      ) : (
                        <Badge variant="default" size="sm">Inactive</Badge>
                      )}
                    </div>
                    <div className="text-xs text-zinc-400 mt-1 flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <Globe size={12} />
                        {inst.base_url}
                      </span>
                      <Badge variant="default" size="sm">{inst.ingestion_mode}</Badge>
                    </div>
                  </div>
                  <div className="text-xs text-zinc-500">
                    {inst.app_types_configured.length > 0
                      ? inst.app_types_configured.join(', ')
                      : 'No app types'}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>

      {/* Apps */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Registered Apps</h2>
        {apps.length === 0 ? (
          <EmptyState
            icon={Key}
            title="No apps registered"
            description="Register Dify apps within your instances for monitoring."
          />
        ) : (
          <Card>
            <div className="divide-y divide-zinc-700">
              {apps.map((app) => (
                <div key={app.id} className="p-4 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">
                        {app.app_name || app.app_id}
                      </span>
                      <Badge variant="info" size="sm">{app.app_type}</Badge>
                      {app.monitoring_enabled ? (
                        <Badge variant="success" size="sm">Monitoring</Badge>
                      ) : (
                        <Badge variant="default" size="sm">Paused</Badge>
                      )}
                    </div>
                    <div className="text-xs text-zinc-400 mt-1">
                      App ID: {app.app_id}
                    </div>
                  </div>
                  <div className="text-right text-xs text-zinc-400">
                    <div>{app.total_runs} runs</div>
                    <div>{app.total_tokens.toLocaleString()} tokens</div>
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
