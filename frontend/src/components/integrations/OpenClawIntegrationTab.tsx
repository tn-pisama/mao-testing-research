import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Bot, Globe, Key } from 'lucide-react'
import type { OpenClawInstance, OpenClawAgent } from '@/lib/api'
import { EmptyState } from './EmptyState'

export function OpenClawIntegrationTab({
  instances,
  agents,
}: {
  instances: OpenClawInstance[]
  agents: OpenClawAgent[]
}) {
  return (
    <div className="space-y-6">
      {/* Instances */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">OpenClaw Instances</h2>
        {instances.length === 0 ? (
          <EmptyState
            icon={Bot}
            title="No OpenClaw instances connected"
            description="Register an OpenClaw instance to monitor agent sessions."
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
                      {inst.otel_enabled && (
                        <Badge variant="info" size="sm">OTEL</Badge>
                      )}
                    </div>
                    <div className="text-xs text-zinc-400 mt-1 flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <Globe size={12} />
                        {inst.gateway_url}
                      </span>
                      <Badge variant="default" size="sm">{inst.ingestion_mode}</Badge>
                    </div>
                  </div>
                  <div className="text-xs text-zinc-500">
                    {inst.channels_configured.length > 0
                      ? inst.channels_configured.join(', ')
                      : 'No channels'}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>

      {/* Agents */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Registered Agents</h2>
        {agents.length === 0 ? (
          <EmptyState
            icon={Key}
            title="No agents registered"
            description="Register agents within your OpenClaw instances for monitoring."
          />
        ) : (
          <Card>
            <div className="divide-y divide-zinc-700">
              {agents.map((agent) => (
                <div key={agent.id} className="p-4 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">
                        {agent.agent_name || agent.agent_key}
                      </span>
                      {agent.monitoring_enabled ? (
                        <Badge variant="success" size="sm">Monitoring</Badge>
                      ) : (
                        <Badge variant="default" size="sm">Paused</Badge>
                      )}
                    </div>
                    <div className="text-xs text-zinc-400 mt-1 flex items-center gap-3">
                      <span>Key: {agent.agent_key}</span>
                      {agent.model && <span>Model: {agent.model}</span>}
                    </div>
                  </div>
                  <div className="text-right text-xs text-zinc-400">
                    <div>{agent.total_sessions} sessions</div>
                    <div>{agent.total_messages} messages</div>
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
