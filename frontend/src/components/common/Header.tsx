'use client'

import { useState } from 'react'
import { Bell, Search, Menu, User, WifiOff, Wifi } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useApiWithFallback } from '@/hooks/useApiWithFallback'
import { WorkflowGroupFilter } from '@/components/filters/WorkflowGroupFilter'
import { ManageGroupsModal } from '@/components/modals/ManageGroupsModal'

interface HeaderProps {
  onMenuClick?: () => void
  title?: string
  notificationCount?: number
}

export function Header({ onMenuClick, title, notificationCount = 0 }: HeaderProps) {
  const { isDemoMode } = useApiWithFallback()
  const [isManageModalOpen, setIsManageModalOpen] = useState(false)

  return (
    <header className="flex items-center justify-between h-14 px-6 bg-zinc-950 border-b border-zinc-800">
      <div className="flex items-center gap-4">
        {onMenuClick && (
          <button
            onClick={onMenuClick}
            className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg lg:hidden"
          >
            <Menu size={20} />
          </button>
        )}
        {title && <h1 className="text-lg font-semibold text-white">{title}</h1>}
      </div>

      <div className="flex items-center gap-3">
        {/* Workflow Group Filter */}
        <WorkflowGroupFilter onManageGroups={() => setIsManageModalOpen(true)} />

        {/* Demo Mode Indicator */}
        {isDemoMode && (
          <span className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <WifiOff size={12} />
            Demo
          </span>
        )}
        {!isDemoMode && (
          <span className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full bg-green-500/10 text-green-400 border border-green-500/20">
            <Wifi size={12} />
            Live
          </span>
        )}

        {/* Search */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg">
          <Search size={16} className="text-zinc-500" />
          <input
            type="text"
            placeholder="Search..."
            className="bg-transparent border-none outline-none text-sm text-zinc-300 placeholder-zinc-600 w-44"
          />
          <kbd className="hidden lg:inline-flex px-1.5 py-0.5 text-[10px] text-zinc-500 bg-zinc-800 border border-zinc-700 rounded">
            ⌘K
          </kbd>
        </div>

        {/* Notifications */}
        <button
          className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg relative"
          aria-label={`Notifications${notificationCount > 0 ? ` (${notificationCount} unread)` : ''}`}
        >
          <Bell size={18} />
          {notificationCount > 0 && (
            <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-red-500 rounded-full" />
          )}
        </button>

        {/* User Menu */}
        <button
          className="flex items-center gap-2 p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg"
          aria-label="User menu"
        >
          <User size={18} />
        </button>
      </div>

      <ManageGroupsModal
        isOpen={isManageModalOpen}
        onClose={() => setIsManageModalOpen(false)}
      />
    </header>
  )
}
