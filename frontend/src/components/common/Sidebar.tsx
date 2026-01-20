'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import clsx from 'clsx'
import {
  LayoutDashboard,
  Activity,
  AlertTriangle,
  AlertCircle,
  BarChart3,
  Users,
  Settings,
  Code2,
  Zap,
  Shield,
  GitBranch,
  Box,
  Sparkles,
  Wrench,
} from 'lucide-react'
import { useUserPreferences } from '@/lib/user-preferences'

interface NavItem {
  label: string
  href: string
  icon: React.ElementType
  badge?: string
  advancedOnly?: boolean  // Only show for developers or when developer mode is on
}

// n8n user sees simplified navigation with friendly terminology
const n8nNavItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'My Workflows', href: '/n8n', icon: GitBranch },
  { label: 'Problems Found', href: '/detections', icon: AlertCircle },
  { label: 'Fixes', href: '/healing', icon: Wrench },
]

// Developer sees full navigation
const developerMainItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Traces', href: '/traces', icon: Activity },
  { label: 'Detections', href: '/detections', icon: AlertTriangle },
  { label: 'Healing', href: '/healing', icon: Sparkles },
  { label: 'Benchmarks', href: '/benchmarks', icon: BarChart3, advancedOnly: true },
]

const developerAgentItems: NavItem[] = [
  { label: 'Agents', href: '/agents', icon: Users },
  { label: 'n8n Workflows', href: '/n8n', icon: GitBranch },
  { label: 'Tools', href: '/tools', icon: Zap },
]

const n8nSettingsItems: NavItem[] = [
  { label: 'Settings', href: '/settings', icon: Settings },
]

const developerSettingsItems: NavItem[] = [
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
  const { isN8nUser, showAdvancedFeatures, preferences } = useUserPreferences()

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

  const NavSection = ({ title, items }: { title?: string; items: NavItem[] }) => {
    // Filter out advanced-only items if user doesn't have access
    const filteredItems = items.filter(item => !item.advancedOnly || showAdvancedFeatures)

    if (filteredItems.length === 0) return null

    return (
      <div className="space-y-1">
        {title && !isCollapsed && (
          <div className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            {title}
          </div>
        )}
        {filteredItems.map((item) => (
          <NavLink key={item.href} item={item} />
        ))}
      </div>
    )
  }

  // Determine which navigation to show based on user type
  const isSimplifiedView = isN8nUser && !showAdvancedFeatures

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
            <span className="text-xl font-bold text-white">
              {isSimplifiedView ? 'Workflow Guard' : 'MAO Testing'}
            </span>
          )}
        </Link>
      </div>

      {/* Navigation - conditional based on user type */}
      <nav className="flex-1 overflow-y-auto p-4 space-y-6">
        {isSimplifiedView ? (
          <>
            {/* Simplified n8n user navigation */}
            <NavSection items={n8nNavItems} />
            <NavSection title="Settings" items={n8nSettingsItems} />
          </>
        ) : (
          <>
            {/* Full developer navigation */}
            <NavSection items={developerMainItems} />
            <NavSection title="Agents & Workflows" items={developerAgentItems} />
            <NavSection title="Settings" items={developerSettingsItems} />
          </>
        )}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-slate-800">
        {!isCollapsed && (
          <div className="text-xs text-slate-500">
            {isSimplifiedView ? (
              <>
                <div>Workflow Guard</div>
                <div className="text-slate-600">Powered by MAO</div>
              </>
            ) : (
              <>
                <div>MAO Testing Platform</div>
                <div>v1.0.0</div>
              </>
            )}
          </div>
        )}
      </div>
    </aside>
  )
}
