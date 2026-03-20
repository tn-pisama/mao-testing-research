'use client'

import { useState, useRef, useEffect } from 'react'
import { ChevronDown, Folder, FolderOpen, Grid, Settings2 } from 'lucide-react'
import { useWorkflowGroups } from '@/hooks/useWorkflowGroups'
import { useUIStore } from '@/stores/uiStore'
import { cn } from '@/lib/utils'

interface WorkflowGroupFilterProps {
  onManageGroups?: () => void
}

export function WorkflowGroupFilter({ onManageGroups }: WorkflowGroupFilterProps) {
  const { groups, isLoading } = useWorkflowGroups()
  const { filterPreferences, setWorkflowGroupFilter } = useUIStore()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const selectedGroupId = filterPreferences.workflowGroupId || 'all'
  const selectedGroup = groups.find((g) => g.id === selectedGroupId)

  const displayName =
    selectedGroupId === 'all'
      ? 'All Workflows'
      : selectedGroupId === 'ungrouped'
      ? 'Ungrouped'
      : selectedGroup?.custom_name || selectedGroup?.name || 'Unknown'

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded-lg text-white text-sm">
        <Folder size={16} className="text-blue-500" />
        <span>Loading...</span>
      </div>
    )
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded-lg text-white text-sm hover:border-zinc-600 transition-colors"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label={`Filter by workflow group: ${displayName}`}
      >
        <Folder size={16} className="text-blue-500" />
        <span>{displayName}</span>
        <ChevronDown
          size={16}
          className={cn('transition-transform', isOpen && 'rotate-180')}
        />
      </button>

      {isOpen && (
        <div className="absolute top-full mt-1 left-0 min-w-[200px] bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl z-50">
          {/* All Workflows */}
          <button
            onClick={() => {
              setWorkflowGroupFilter(null)
              setIsOpen(false)
            }}
            className={cn(
              'w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-zinc-800 transition-colors',
              selectedGroupId === 'all' && 'bg-blue-500/20 text-blue-500'
            )}
          >
            <Grid size={16} />
            <span>All Workflows</span>
          </button>

          {/* Ungrouped */}
          <button
            onClick={() => {
              setWorkflowGroupFilter('ungrouped')
              setIsOpen(false)
            }}
            className={cn(
              'w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-zinc-800 transition-colors',
              selectedGroupId === 'ungrouped' && 'bg-blue-500/20 text-blue-500'
            )}
          >
            <FolderOpen size={16} />
            <span>Ungrouped</span>
          </button>

          {/* Divider */}
          {groups.length > 0 && <div className="border-t border-zinc-700 my-1" />}

          {/* Groups */}
          {groups
            .filter((g) => !g.is_hidden)
            .map((group) => (
              <button
                key={group.id}
                onClick={() => {
                  setWorkflowGroupFilter(group.id)
                  setIsOpen(false)
                }}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-zinc-800 transition-colors',
                  selectedGroupId === group.id && 'bg-blue-500/20 text-blue-500'
                )}
              >
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: group.color || '#3b82f6' }}
                />
                <span className="flex-1 text-left truncate">
                  {group.custom_name || group.name}
                </span>
                <span className="text-xs text-zinc-400">{group.workflow_count || 0}</span>
              </button>
            ))}

          {/* Manage Groups */}
          {onManageGroups && (
            <>
              <div className="border-t border-zinc-700 mt-1" />
              <button
                onClick={() => {
                  setIsOpen(false)
                  onManageGroups()
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-blue-500 hover:bg-zinc-800 transition-colors"
              >
                <Settings2 size={16} />
                <span>Manage Groups</span>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
