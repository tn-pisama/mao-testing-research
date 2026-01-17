'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import clsx from 'clsx'
import {
  LayoutDashboard,
  Activity,
  AlertTriangle,
  BarChart3,
  Users,
  Settings,
  Code2,
  FileText,
  Zap,
  Shield,
  GitBranch,
  Box,
  Sparkles,
} from 'lucide-react'

interface NavItem {
  label: string
  href: string
  icon: React.ElementType
  badge?: string
}

const mainNavItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Traces', href: '/traces', icon: Activity },
  { label: 'Detections', href: '/detections', icon: AlertTriangle },
  { label: 'Healing', href: '/healing', icon: Sparkles },
  { label: 'Benchmarks', href: '/benchmarks', icon: BarChart3 },
]

const agentNavItems: NavItem[] = [
  { label: 'Agents', href: '/agents', icon: Users },
  { label: 'Workflows', href: '/workflows', icon: GitBranch },
  { label: 'Tools', href: '/tools', icon: Zap },
]

const settingsNavItems: NavItem[] = [
  { label: 'API Keys', href: '/settings/api-keys', icon: Code2 },
  { label: 'Integrations', href: '/settings/integrations', icon: Box },
  { label: 'Settings', href: '/settings', icon: Settings },
]

interface SidebarProps {
  isCollapsed?: boolean
  onToggle?: () => void
}

export function Sidebar({ isCollapsed = false, onToggle }: SidebarProps) {
  const pathname = usePathname()

  const NavLink = ({ item }: { item: NavItem }) => {
    const isActive = pathname === item.href || pathname?.startsWith(item.href + '/')
    const Icon = item.icon

    return (
      <Link
        href={item.href}
        className={clsx(
          'flex items-center gap-3 px-3 py-2 rounded-lg transition-colors',
          isActive
            ? 'bg-blue-600/20 text-blue-400'
            : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
        )}
      >
        <Icon size={20} />
        {!isCollapsed && (
          <>
            <span className="flex-1">{item.label}</span>
            {item.badge && (
              <span className="px-2 py-0.5 text-xs bg-blue-600 text-white rounded-full">
                {item.badge}
              </span>
            )}
          </>
        )}
      </Link>
    )
  }

  const NavSection = ({ title, items }: { title?: string; items: NavItem[] }) => (
    <div className="space-y-1">
      {title && !isCollapsed && (
        <div className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
          {title}
        </div>
      )}
      {items.map((item) => (
        <NavLink key={item.href} item={item} />
      ))}
    </div>
  )

  return (
    <aside
      className={clsx(
        'flex flex-col bg-slate-900 border-r border-slate-800 transition-all duration-300',
        isCollapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Logo */}
      <div className="flex items-center h-16 px-4 border-b border-slate-800">
        <Link href="/" className="flex items-center gap-2">
          <Shield className="h-8 w-8 text-blue-500" />
          {!isCollapsed && (
            <span className="text-xl font-bold text-white">MAO Testing</span>
          )}
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-4 space-y-6">
        <NavSection items={mainNavItems} />
        <NavSection title="Agents" items={agentNavItems} />
        <NavSection title="Settings" items={settingsNavItems} />
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-slate-800">
        {!isCollapsed && (
          <div className="text-xs text-slate-500">
            <div>MAO Testing Platform</div>
            <div>v1.0.0</div>
          </div>
        )}
      </div>
    </aside>
  )
}
