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
  Star,
  User,
  RotateCcw,
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
const n8nObserveItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'My Workflows', href: '/n8n', icon: GitBranch },
]

const n8nImproveItems: NavItem[] = [
  { label: 'Quality', href: '/quality', icon: Star },
  { label: 'Problems Found', href: '/detections', icon: AlertCircle },
  { label: 'Fixes', href: '/healing', icon: Wrench },
]

// Developer sees full navigation
const developerObserveItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Traces', href: '/traces', icon: Activity },
  { label: 'Detections', href: '/detections', icon: AlertTriangle },
]

const developerImproveItems: NavItem[] = [
  { label: 'Quality', href: '/quality', icon: Star },
  { label: 'Healing', href: '/healing', icon: Sparkles },
  { label: 'Replay', href: '/replay', icon: RotateCcw },
  { label: 'Benchmarks', href: '/benchmarks', icon: BarChart3, advancedOnly: true },
]

const developerConfigureItems: NavItem[] = [
  { label: 'Agents', href: '/agents', icon: Users },
  { label: 'Workflows', href: '/n8n', icon: GitBranch },
  { label: 'Tools', href: '/tools', icon: Zap },
]

const n8nSettingsItems: NavItem[] = [
  { label: 'Account', href: '/account', icon: User },
  { label: 'Settings', href: '/settings', icon: Settings },
]

const developerSettingsItems: NavItem[] = [
  { label: 'Account', href: '/account', icon: User },
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
    const isActive = pathname === item.href ||
      (item.href !== '/settings' && pathname?.startsWith(item.href + '/'))
    const Icon = item.icon

    return (
      <Link
        href={item.href}
        className={clsx(
          'flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200 font-mono',
          isActive
            ? 'bg-primary-500/20 text-primary-500 shadow-glow-green border border-primary-500/50'
            : 'text-primary-400 hover:bg-primary-500/10 hover:text-primary-500 hover:shadow-glow-green'
        )}
      >
        <Icon size={20} />
        {!isCollapsed && (
          <>
            <span className="flex-1">{item.label}</span>
            {item.badge && (
              <span className="px-2 py-0.5 text-xs bg-primary-500/20 text-primary-500 border border-primary-500/50 rounded-full font-mono">
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
          <div className="px-3 py-2 text-xs font-semibold text-primary-500/60 uppercase tracking-wider font-mono">
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
        'flex flex-col bg-[#0a0a0a] border-r border-primary-500/30 shadow-[0_0_10px_rgba(0,255,136,0.1)] transition-all duration-300',
        isCollapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Logo */}
      <div className="flex items-center h-16 px-4 border-b border-primary-500/30">
        <Link href="/" className="flex items-center gap-2">
          <Shield className="h-8 w-8 text-primary-500 shadow-glow-green" />
          {!isCollapsed && (
            <span className="text-xl font-bold text-primary-500 font-mono glow-text">
              {isSimplifiedView ? 'Workflow Guard' : 'Pisama'}
            </span>
          )}
        </Link>
      </div>

      {/* Navigation - conditional based on user type */}
      <nav className="flex-1 overflow-y-auto p-4 space-y-6">
        {isSimplifiedView ? (
          <>
            {/* Simplified n8n user navigation */}
            <NavSection title="Observe" items={n8nObserveItems} />
            <NavSection title="Improve" items={n8nImproveItems} />
            <NavSection title="Settings" items={n8nSettingsItems} />
          </>
        ) : (
          <>
            {/* Full developer navigation */}
            <NavSection title="Observe" items={developerObserveItems} />
            <NavSection title="Improve" items={developerImproveItems} />
            <NavSection title="Configure" items={developerConfigureItems} />
            <NavSection title="Settings" items={developerSettingsItems} />
          </>
        )}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-primary-500/30">
        {!isCollapsed && (
          <div className="text-xs text-primary-400 font-mono">
            {isSimplifiedView ? (
              <>
                <div>Workflow Guard</div>
                <div className="text-primary-500/60">Powered by Pisama</div>
              </>
            ) : (
              <>
                <div>Pisama Platform</div>
                <div>v1.0.0</div>
              </>
            )}
          </div>
        )}
      </div>
    </aside>
  )
}
