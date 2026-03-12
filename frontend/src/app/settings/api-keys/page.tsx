'use client'

export const dynamic = 'force-dynamic'

import { useState } from 'react'
import { Layout } from '@/components/common/Layout'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import {
  Key,
  Plus,
  Copy,
  Trash2,
  CheckCircle,
  AlertTriangle,
  Clock,
  ArrowLeft,
} from 'lucide-react'
import Link from 'next/link'

interface ApiKey {
  id: string
  name: string
  prefix: string
  createdAt: string
  lastUsed?: string
  scopes: string[]
}

// Demo data - in production would come from API
const demoApiKeys: ApiKey[] = [
  {
    id: '1',
    name: 'Production API Key',
    prefix: 'mao_sk_prod_',
    createdAt: '2024-01-15T10:30:00Z',
    lastUsed: '2024-01-21T14:22:00Z',
    scopes: ['traces:read', 'traces:write', 'detections:read'],
  },
  {
    id: '2',
    name: 'Development Key',
    prefix: 'mao_sk_dev_',
    createdAt: '2024-01-10T08:00:00Z',
    lastUsed: '2024-01-20T09:15:00Z',
    scopes: ['traces:read', 'traces:write', 'detections:read', 'detections:write'],
  },
  {
    id: '3',
    name: 'CI/CD Pipeline',
    prefix: 'mao_sk_ci_',
    createdAt: '2024-01-05T12:00:00Z',
    scopes: ['traces:write'],
  },
]

export default function ApiKeysPage() {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>(demoApiKeys)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  const handleCopy = (prefix: string, id: string) => {
    navigator.clipboard.writeText(`${prefix}${'*'.repeat(24)}`)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const handleDelete = (id: string) => {
    setApiKeys(keys => keys.filter(k => k.id !== id))
    setDeleteConfirm(null)
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <Link
            href="/settings"
            className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <ArrowLeft size={20} />
          </Link>
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <div className="p-2 bg-blue-600/20 rounded-lg">
                <Key className="w-5 h-5 text-blue-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">API Keys</h1>
            </div>
            <p className="text-zinc-400 text-sm">
              Manage API keys for accessing the PISAMA API
            </p>
          </div>
          <Button onClick={() => setShowCreateModal(true)} leftIcon={<Plus size={16} />}>
            Create API Key
          </Button>
        </div>

        {/* API Keys List */}
        <Card>
          <CardContent className="p-0">
            {apiKeys.length === 0 ? (
              <div className="text-center py-12">
                <Key size={32} className="mx-auto mb-3 text-zinc-600" />
                <p className="text-zinc-400 mb-1">No API keys yet</p>
                <p className="text-sm text-zinc-500">
                  Create an API key to start using the PISAMA API
                </p>
              </div>
            ) : (
              <div className="divide-y divide-zinc-700">
                {apiKeys.map((key) => (
                  <div key={key.id} className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-white font-medium">{key.name}</span>
                        </div>
                        <div className="flex items-center gap-2 mb-2">
                          <code className="text-sm text-zinc-400 bg-zinc-800 px-2 py-1 rounded">
                            {key.prefix}{'*'.repeat(20)}
                          </code>
                          <button
                            onClick={() => handleCopy(key.prefix, key.id)}
                            className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-700 rounded transition-colors"
                            aria-label="Copy API key"
                          >
                            {copiedId === key.id ? (
                              <CheckCircle size={14} className="text-emerald-400" />
                            ) : (
                              <Copy size={14} />
                            )}
                          </button>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-zinc-500">
                          <span className="flex items-center gap-1">
                            <Clock size={12} />
                            Created {formatDate(key.createdAt)}
                          </span>
                          {key.lastUsed && (
                            <span>Last used {formatDate(key.lastUsed)}</span>
                          )}
                        </div>
                        <div className="flex gap-1 mt-2">
                          {key.scopes.map((scope) => (
                            <span
                              key={scope}
                              className="px-2 py-0.5 text-xs bg-zinc-700 text-zinc-300 rounded"
                            >
                              {scope}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {deleteConfirm === key.id ? (
                          <>
                            <Button
                              size="sm"
                              variant="danger"
                              onClick={() => handleDelete(key.id)}
                            >
                              Confirm
                            </Button>
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => setDeleteConfirm(null)}
                            >
                              Cancel
                            </Button>
                          </>
                        ) : (
                          <button
                            onClick={() => setDeleteConfirm(key.id)}
                            className="p-2 text-zinc-400 hover:text-red-400 hover:bg-zinc-700 rounded transition-colors"
                            aria-label="Delete API key"
                          >
                            <Trash2 size={16} />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Usage Stats */}
        <div className="mt-6">
          <h3 className="text-lg font-semibold text-white mb-3">Usage This Month</h3>
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-white">12,450</div>
                <div className="text-xs text-zinc-400">API Requests</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-white">847</div>
                <div className="text-xs text-zinc-400">Traces Processed</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="text-2xl font-bold text-white">156</div>
                <div className="text-xs text-zinc-400">Detections Created</div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Create Modal */}
        {showCreateModal && (
          <CreateApiKeyModal
            onClose={() => setShowCreateModal(false)}
            onCreated={(newKey) => {
              setApiKeys(keys => [newKey, ...keys])
              setShowCreateModal(false)
            }}
          />
        )}
      </div>
    </Layout>
  )
}

interface CreateApiKeyModalProps {
  onClose: () => void
  onCreated: (key: ApiKey) => void
}

function CreateApiKeyModal({ onClose, onCreated }: CreateApiKeyModalProps) {
  const [name, setName] = useState('')
  const [scopes, setScopes] = useState<string[]>(['traces:read', 'traces:write'])
  const [isCreating, setIsCreating] = useState(false)
  const [newKey, setNewKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const availableScopes = [
    { id: 'traces:read', label: 'Read Traces' },
    { id: 'traces:write', label: 'Write Traces' },
    { id: 'detections:read', label: 'Read Detections' },
    { id: 'detections:write', label: 'Write Detections' },
    { id: 'quality:read', label: 'Read Quality Assessments' },
  ]

  const handleCreate = async () => {
    if (!name.trim()) return
    setIsCreating(true)

    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 500))

    const generatedKey = `mao_sk_${Math.random().toString(36).substring(2, 15)}${Math.random().toString(36).substring(2, 15)}`
    setNewKey(generatedKey)
    setIsCreating(false)
  }

  const handleCopyAndClose = () => {
    if (newKey) {
      navigator.clipboard.writeText(newKey)
      setCopied(true)
      setTimeout(() => {
        onCreated({
          id: Math.random().toString(),
          name,
          prefix: newKey.substring(0, 12) + '_',
          createdAt: new Date().toISOString(),
          scopes,
        })
      }, 500)
    }
  }

  const toggleScope = (scopeId: string) => {
    setScopes(prev =>
      prev.includes(scopeId)
        ? prev.filter(s => s !== scopeId)
        : [...prev, scopeId]
    )
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" role="dialog" aria-modal="true" aria-labelledby="create-api-key-title">
      <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700 w-full max-w-md">
        {newKey ? (
          <>
            <div className="flex items-center gap-2 mb-4">
              <CheckCircle className="text-emerald-400" size={20} />
              <h2 id="create-api-key-title" className="text-lg font-semibold text-white">API Key Created</h2>
            </div>

            <div className="p-4 bg-zinc-900 rounded-lg mb-4">
              <p className="text-xs text-zinc-400 mb-2">
                Copy this key now. You won&apos;t be able to see it again.
              </p>
              <code className="text-sm text-emerald-400 break-all">{newKey}</code>
            </div>

            <div className="flex items-center gap-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg mb-4">
              <AlertTriangle size={16} className="text-amber-400 flex-shrink-0" />
              <p className="text-xs text-amber-300">
                Store this key securely. It provides access to your API.
              </p>
            </div>

            <Button
              onClick={handleCopyAndClose}
              className="w-full"
              leftIcon={copied ? <CheckCircle size={16} /> : <Copy size={16} />}
            >
              {copied ? 'Copied!' : 'Copy & Close'}
            </Button>
          </>
        ) : (
          <>
            <h2 id="create-api-key-title" className="text-lg font-semibold text-white mb-4">Create API Key</h2>

            <div className="space-y-4">
              <div>
                <label htmlFor="api-key-name" className="text-sm font-medium text-zinc-300 block mb-2">
                  Key Name
                </label>
                <input
                  id="api-key-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Production API Key"
                  aria-required="true"
                  className="w-full bg-zinc-900 border border-zinc-600 rounded-lg p-3 text-white text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-zinc-300 block mb-2">
                  Permissions
                </label>
                <div className="space-y-2">
                  {availableScopes.map((scope) => (
                    <label
                      key={scope.id}
                      className="flex items-center gap-3 p-2 bg-zinc-900 rounded-lg cursor-pointer hover:bg-zinc-800"
                    >
                      <input
                        type="checkbox"
                        checked={scopes.includes(scope.id)}
                        onChange={() => toggleScope(scope.id)}
                        className="w-4 h-4 rounded border-zinc-600 text-blue-500 focus:ring-blue-500 focus:ring-offset-zinc-800"
                      />
                      <span className="text-sm text-zinc-300">{scope.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <Button
                  onClick={handleCreate}
                  disabled={!name.trim() || isCreating}
                  loading={isCreating}
                  className="flex-1"
                >
                  Create Key
                </Button>
                <Button
                  variant="secondary"
                  onClick={onClose}
                  disabled={isCreating}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
