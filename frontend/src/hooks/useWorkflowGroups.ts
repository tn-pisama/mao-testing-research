'use client'

import { useState, useEffect } from 'react'
import { useSafeAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { createApiClient, type WorkflowGroup, type CreateGroupRequest } from '@/lib/api'

export function useWorkflowGroups() {
  const { getToken } = useSafeAuth()
  const { tenantId } = useTenant()
  const [groups, setGroups] = useState<WorkflowGroup[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadGroups() {
      try {
        const token = await getToken()
        if (!token || !tenantId || tenantId === 'default') {
          setGroups([])
          setIsLoading(false)
          return
        }

        const api = createApiClient(token, tenantId)
        const data = await api.listWorkflowGroups()
        setGroups(data)
        setError(null)
      } catch (err) {
        // Non-critical: workflow groups are optional
        console.warn('Failed to load workflow groups:', (err as Error).message)
        setError('Failed to load groups')
        setGroups([])
      } finally {
        setIsLoading(false)
      }
    }
    loadGroups()
  }, [getToken, tenantId])

  const createGroup = async (data: CreateGroupRequest) => {
    const token = await getToken()
    if (!token || !tenantId) throw new Error('Not authenticated')

    const api = createApiClient(token, tenantId)
    const newGroup = await api.createWorkflowGroup(data)
    setGroups([...groups, newGroup])
    return newGroup
  }

  const updateGroup = async (groupId: string, data: Partial<CreateGroupRequest>) => {
    const token = await getToken()
    if (!token || !tenantId) throw new Error('Not authenticated')

    const api = createApiClient(token, tenantId)
    const updated = await api.updateWorkflowGroup(groupId, data)
    setGroups(groups.map((g) => (g.id === groupId ? updated : g)))
    return updated
  }

  const deleteGroup = async (groupId: string) => {
    const token = await getToken()
    if (!token || !tenantId) throw new Error('Not authenticated')

    const api = createApiClient(token, tenantId)
    await api.deleteWorkflowGroup(groupId)
    setGroups(groups.filter((g) => g.id !== groupId))
  }

  const assignWorkflows = async (groupId: string, workflowIds: string[]) => {
    const token = await getToken()
    if (!token || !tenantId) throw new Error('Not authenticated')

    const api = createApiClient(token, tenantId)
    return await api.assignWorkflowsToGroup(groupId, workflowIds)
  }

  const runAutoDetection = async (groupId: string) => {
    const token = await getToken()
    if (!token || !tenantId) throw new Error('Not authenticated')

    const api = createApiClient(token, tenantId)
    return await api.runGroupAutoDetection(groupId)
  }

  return {
    groups,
    isLoading,
    error,
    createGroup,
    updateGroup,
    deleteGroup,
    assignWorkflows,
    runAutoDetection,
  }
}
