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
    // Workflow groups endpoint not yet deployed — skip API call
    // This also prevents Mixed Content errors from old cached JS bundles
    setGroups([])
    setIsLoading(false)
  }, [tenantId])

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
