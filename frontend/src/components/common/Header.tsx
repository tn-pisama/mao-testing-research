'use client'

import { Bell, Search, Menu, User } from 'lucide-react'

interface HeaderProps {
  onMenuClick?: () => void
  title?: string
  notificationCount?: number
}

export function Header({ onMenuClick, title, notificationCount = 0 }: HeaderProps) {
  return (
    <header className="flex items-center justify-between h-16 px-6 bg-slate-900 border-b border-slate-800">
      <div className="flex items-center gap-4">
        {onMenuClick && (
          <button
            onClick={onMenuClick}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg lg:hidden"
          >
            <Menu size={20} />
          </button>
        )}
        {title && <h1 className="text-xl font-semibold text-white">{title}</h1>}
      </div>

      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="hidden md:flex items-center gap-2 px-3 py-2 bg-slate-800 rounded-lg">
          <Search size={18} className="text-slate-400" />
          <input
            type="text"
            placeholder="Search..."
            className="bg-transparent border-none outline-none text-sm text-slate-300 placeholder-slate-500 w-48"
          />
          <kbd className="hidden lg:inline-flex px-2 py-0.5 text-xs bg-slate-700 text-slate-400 rounded">
            ⌘K
          </kbd>
        </div>

        {/* Notifications */}
        <button
          className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg relative"
          aria-label={`Notifications${notificationCount > 0 ? ` (${notificationCount} unread)` : ''}`}
        >
          <Bell size={20} />
          {notificationCount > 0 && (
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
          )}
        </button>

        {/* User Menu */}
        <button className="flex items-center gap-2 p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg">
          <User size={20} />
        </button>
      </div>
    </header>
  )
}
