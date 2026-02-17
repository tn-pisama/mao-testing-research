'use client'

import { useState } from 'react'
import { Bell, Search, Menu, User, WifiOff, Wifi } from 'lucide-react'
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
    <header className="flex items-center justify-between h-16 px-6 bg-[#0a0a0a] border-b border-primary-500/30 shadow-[0_0_10px_rgba(0,255,136,0.1)]">
      <div className="flex items-center gap-4">
        {onMenuClick && (
          <button
            onClick={onMenuClick}
            className="p-2 text-primary-400 hover:text-primary-500 hover:bg-primary-500/10 hover:shadow-glow-green rounded-lg lg:hidden"
          >
            <Menu size={20} />
          </button>
        )}
        {title && <h1 className="text-xl font-semibold text-primary-500 font-mono">{title}</h1>}
      </div>

      <div className="flex items-center gap-3">
        {/* Workflow Group Filter */}
        <WorkflowGroupFilter onManageGroups={() => setIsManageModalOpen(true)} />

        {/* Demo Mode Indicator */}
        {isDemoMode && (
          <span className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">
            <WifiOff size={12} />
            Demo Mode
          </span>
        )}
        {!isDemoMode && (
          <span className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded-full bg-green-500/20 text-green-400 border border-green-500/30">
            <Wifi size={12} />
            Live
          </span>
        )}

        {/* Search */}
        <div className="hidden md:flex items-center gap-2 px-3 py-2 bg-black border border-primary-500/30 rounded-lg font-mono">
          <Search size={18} className="text-primary-400" />
          <input
            type="text"
            placeholder="Search..."
            className="bg-transparent border-none outline-none text-sm text-primary-400 placeholder-primary-500/40 w-48"
          />
          <kbd className="hidden lg:inline-flex px-2 py-0.5 text-xs bg-primary-500/20 text-primary-500 border border-primary-500/30 rounded font-mono">
            ⌘K
          </kbd>
        </div>

        {/* Notifications */}
        <button
          className="p-2 text-primary-400 hover:text-primary-500 hover:bg-primary-500/10 hover:shadow-glow-green rounded-lg relative"
          aria-label={`Notifications${notificationCount > 0 ? ` (${notificationCount} unread)` : ''}`}
        >
          <Bell size={20} />
          {notificationCount > 0 && (
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
          )}
        </button>

        {/* User Menu */}
        <button className="flex items-center gap-2 p-2 text-primary-400 hover:text-primary-500 hover:bg-primary-500/10 hover:shadow-glow-green rounded-lg">
          <User size={20} />
        </button>
      </div>

      <ManageGroupsModal
        isOpen={isManageModalOpen}
        onClose={() => setIsManageModalOpen(false)}
      />
    </header>
  )
}
