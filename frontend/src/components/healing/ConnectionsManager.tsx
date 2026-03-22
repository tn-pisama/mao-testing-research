'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import {
  Settings,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  ExternalLink,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import type { N8nConnection } from '@/lib/api'
import {
  useCreateConnectionMutation,
  useTestConnectionMutation,
  useDeleteConnectionMutation,
} from '@/hooks/useQueries'

interface ConnectionsManagerProps {
  connections: N8nConnection[]
  isLoading: boolean
}

export function ConnectionsManager({ connections, isLoading }: ConnectionsManagerProps) {
  const [showAddConnection, setShowAddConnection] = useState(false)
  const [newConnection, setNewConnection] = useState({
    name: '',
    instance_url: '',
    api_key: '',
  })

  const createMutation = useCreateConnectionMutation()
  const testMutation = useTestConnectionMutation()
  const deleteMutation = useDeleteConnectionMutation()

  const handleAddConnection = () => {
    if (!newConnection.name || !newConnection.instance_url || !newConnection.api_key) return
    createMutation.mutate(newConnection, {
      onSuccess: () => {
        toast.success('Connection added', { description: `${newConnection.name} has been configured.` })
        setNewConnection({ name: '', instance_url: '', api_key: '' })
        setShowAddConnection(false)
      },
      onError: (err) => {
        toast.error('Failed to add connection', {
          description: (err as Error).message || 'Check the URL and API key.',
        })
      },
    })
  }

  const handleTestConnection = (connectionId: string) => {
    testMutation.mutate(connectionId, {
      onSuccess: () => toast.success('Connection verified', { description: 'Your n8n instance is reachable.' }),
      onError: (err) => toast.error('Connection test failed', { description: (err as Error).message }),
    })
  }

  const handleDeleteConnection = (connectionId: string) => {
    if (!window.confirm('Delete this connection?')) return
    deleteMutation.mutate(connectionId, {
      onSuccess: () => toast.success('Connection deleted'),
      onError: (err) => toast.error('Failed to delete connection', { description: (err as Error).message }),
    })
  }

  return (
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
                <div key={i} className="h-16 bg-zinc-700 rounded-lg" />
              ))}
            </div>
          </CardContent>
        </Card>
      ) : connections.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-zinc-400">
            <Settings size={32} className="mx-auto mb-3 opacity-50" />
            <p className="text-sm">No n8n connections configured</p>
            <p className="text-xs text-zinc-500 mt-1">
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
                    <div className={`p-2 rounded-lg ${conn.is_active ? 'bg-green-500/20' : 'bg-zinc-500/20'}`}>
                      {conn.is_active
                        ? <CheckCircle2 size={20} className="text-green-400" />
                        : <XCircle size={20} className="text-zinc-400" />
                      }
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">{conn.name}</p>
                      <p className="text-xs text-zinc-400">{conn.instance_url}</p>
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
                      isLoading={testMutation.isPending && testMutation.variables === conn.id}
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
                      isLoading={deleteMutation.isPending && deleteMutation.variables === conn.id}
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
          <div className="relative bg-zinc-900 border border-zinc-700 rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold text-white mb-4">Add n8n Connection</h3>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-zinc-400 mb-1 block">Name</label>
                <input
                  type="text"
                  value={newConnection.name}
                  onChange={(e) => setNewConnection({ ...newConnection, name: e.target.value })}
                  placeholder="Production n8n"
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="text-sm text-zinc-400 mb-1 block">Instance URL</label>
                <input
                  type="text"
                  value={newConnection.instance_url}
                  onChange={(e) => setNewConnection({ ...newConnection, instance_url: e.target.value })}
                  placeholder="https://your-instance.app.n8n.cloud"
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="text-sm text-zinc-400 mb-1 block">API Key</label>
                <input
                  type="password"
                  value={newConnection.api_key}
                  onChange={(e) => setNewConnection({ ...newConnection, api_key: e.target.value })}
                  placeholder="n8n_api_..."
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                isLoading={createMutation.isPending}
                disabled={!newConnection.name || !newConnection.instance_url || !newConnection.api_key}
              >
                Add Connection
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
