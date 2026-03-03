'use client'

import { useState } from 'react'
import { X, Plus, Edit2, Trash2, Loader2 } from 'lucide-react'
import { useWorkflowGroups } from '@/hooks/useWorkflowGroups'
import { Button } from '@/components/ui/Button'
import type { CreateGroupRequest } from '@/lib/api'

interface ManageGroupsModalProps {
  isOpen: boolean
  onClose: () => void
}

export function ManageGroupsModal({ isOpen, onClose }: ManageGroupsModalProps) {
  const { groups, createGroup, updateGroup, deleteGroup } = useWorkflowGroups()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [formData, setFormData] = useState<Partial<CreateGroupRequest>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleCreate = async () => {
    if (!formData.name) {
      setError('Group name is required')
      return
    }

    setIsSubmitting(true)
    setError(null)
    try {
      await createGroup(formData as CreateGroupRequest)
      setFormData({})
      setIsCreating(false)
    } catch (err) {
      console.error('Failed to create group:', err)
      setError('Failed to create group')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleUpdate = async (groupId: string) => {
    if (!formData.name) {
      setError('Group name is required')
      return
    }

    setIsSubmitting(true)
    setError(null)
    try {
      await updateGroup(groupId, formData)
      setEditingId(null)
      setFormData({})
    } catch (err) {
      console.error('Failed to update group:', err)
      setError('Failed to update group')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDelete = async (groupId: string) => {
    if (!confirm('Delete this group? Workflows will not be deleted.')) {
      return
    }

    setIsSubmitting(true)
    setError(null)
    try {
      await deleteGroup(groupId)
    } catch (err) {
      console.error('Failed to delete group:', err)
      setError('Failed to delete group')
    } finally {
      setIsSubmitting(false)
    }
  }

  const startEdit = (groupId: string, name: string, description?: string) => {
    setEditingId(groupId)
    setFormData({ name, description })
    setIsCreating(false)
    setError(null)
  }

  const cancelEdit = () => {
    setEditingId(null)
    setIsCreating(false)
    setFormData({})
    setError(null)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-zinc-900 rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden border border-zinc-700">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-700">
          <h2 className="text-xl font-bold text-white">Manage Workflow Groups</h2>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white transition-colors"
            aria-label="Close dialog"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 overflow-y-auto max-h-[60vh]">
          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-500 text-sm">
              {error}
            </div>
          )}

          {/* Create New Button */}
          {!isCreating && !editingId && (
            <Button
              onClick={() => {
                setIsCreating(true)
                setFormData({})
                setError(null)
              }}
              variant="primary"
              className="mb-4"
            >
              <Plus size={16} />
              Create New Group
            </Button>
          )}

          {/* Create Form */}
          {isCreating && (
            <div className="mb-4 p-4 bg-zinc-800 rounded-lg border border-zinc-700">
              <input
                type="text"
                placeholder="Group Name"
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded text-white mb-2 focus:border-blue-500 focus:outline-none"
              />
              <textarea
                placeholder="Description (optional)"
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded text-white mb-2 focus:border-blue-500 focus:outline-none"
                rows={2}
              />
              <div className="flex gap-2">
                <Button onClick={handleCreate} variant="primary" disabled={isSubmitting}>
                  {isSubmitting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Saving...
                    </>
                  ) : (
                    'Save'
                  )}
                </Button>
                <Button onClick={cancelEdit} variant="secondary" disabled={isSubmitting}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {/* Groups List */}
          <div className="space-y-2">
            {groups.map((group) => (
              <div
                key={group.id}
                className="p-3 bg-zinc-800 rounded-lg border border-zinc-700 hover:border-zinc-600 transition-colors"
              >
                {editingId === group.id ? (
                  // Edit Mode
                  <div>
                    <input
                      type="text"
                      value={formData.name || group.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded text-white mb-2 focus:border-blue-500 focus:outline-none"
                    />
                    <textarea
                      value={formData.description || group.description || ''}
                      onChange={(e) =>
                        setFormData({ ...formData, description: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded text-white mb-2 focus:border-blue-500 focus:outline-none"
                      rows={2}
                    />
                    <div className="flex gap-2">
                      <Button
                        onClick={() => handleUpdate(group.id)}
                        variant="primary"
                        disabled={isSubmitting}
                      >
                        {isSubmitting ? (
                          <>
                            <Loader2 size={16} className="animate-spin" />
                            Saving...
                          </>
                        ) : (
                          'Save'
                        )}
                      </Button>
                      <Button onClick={cancelEdit} variant="secondary" disabled={isSubmitting}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  // View Mode
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-4 h-4 rounded-full"
                        style={{ backgroundColor: group.color || '#3b82f6' }}
                      />
                      <div>
                        <div className="font-medium text-white">{group.name}</div>
                        {group.description && (
                          <div className="text-sm text-zinc-400">
                            {group.description}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-zinc-400">
                        {group.workflow_count || 0} workflows
                      </span>
                      <button
                        onClick={() => startEdit(group.id, group.name, group.description)}
                        className="p-1 text-zinc-400 hover:text-white transition-colors"
                        disabled={isSubmitting}
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        onClick={() => handleDelete(group.id)}
                        className="p-1 text-red-500 hover:text-red-400 transition-colors"
                        disabled={isSubmitting}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {groups.length === 0 && !isCreating && (
            <div className="text-center py-8 text-zinc-400">
              No workflow groups yet. Create one to get started!
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-700 flex justify-end">
          <Button onClick={onClose} variant="secondary">
            Close
          </Button>
        </div>
      </div>
    </div>
  )
}
