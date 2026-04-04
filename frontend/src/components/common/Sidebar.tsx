'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  Activity,
  AlertTriangle,
  Settings,
  Code2,
  Shield,
  Box,
  Wrench,
  Star,
  User,
  Bot,
  LogOut,
  BookOpen,
  ClipboardCheck,
  CreditCard,
} from 'lucide-react'
import { signOut } from 'next-auth/react'
import { clearAllCaches } from '@/hooks/useSafeAuth'
import { TenantSwitcher } from './TenantSwitcher'

interface NavItem {
  label: string
  href: string
  icon: React.ElementType
  badge?: string
}

// Unified navigation — all platforms treated equally
const observeItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Runs', href: '/traces', icon: Activity },
  { label: 'Detections', href: '/detections', icon: AlertTriangle },
]

const improveItems: NavItem[] = [
  { label: 'Workflows', href: '/quality', icon: Star },
  { label: 'Agents', href: '/agents', icon: Bot },
  { label: 'Healing', href: '/healing', icon: Wrench },
  { label: 'Review', href: '/review', icon: ClipboardCheck },
]

const configureItems: NavItem[] = [
  { label: 'Integrations', href: '/integrations', icon: Box },
  { label: 'API Keys', href: '/settings/api-keys', icon: Code2 },
]

const settingsItems: NavItem[] = [
  { label: 'Billing', href: '/billing', icon: CreditCard },
  { label: 'Account', href: '/account', icon: User },
  { label: 'Settings', href: '/settings', icon: Settings },
  { label: 'Docs', href: '/docs/', icon: BookOpen },
]

function NavLink({ item, pathname, isCollapsed }: { item: NavItem; pathname: string | null; isCollapsed: boolean }) {
  const isExternal = item.href.startsWith('http')
  const isRewriteRoute = item.href.startsWith('/docs')
  const isActive = !isExternal && (pathname === item.href ||
    (item.href !== '/settings' && pathname?.startsWith(item.href + '/')))
  const Icon = item.icon

  const className = cn(
    'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors duration-150',
    isActive
      ? 'bg-blue-500/10 text-blue-400 border-l-2 border-blue-500 -ml-px'
      : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
  )

  const content = (
    <>
      <Icon size={18} />
      {!isCollapsed && (
        <>
          <span className="flex-1">{item.label}</span>
          {item.badge && (
            <span className="px-1.5 py-0.5 text-xs bg-zinc-800 text-zinc-400 rounded">
              {item.badge}
            </span>
          )}
        </>
      )}
    </>
  )

  if (isExternal) {
    return (
      <a href={item.href} target="_blank" rel="noopener noreferrer" className={className}>
        {content}
      </a>
    )
  }

  if (isRewriteRoute) {
    return (
      <a href={item.href} className={className}>
        {content}
      </a>
    )
  }

  return (
    <Link href={item.href} className={className}>
      {content}
    </Link>
  )
}

function NavSection({ title, items, pathname, isCollapsed }: { title?: string; items: NavItem[]; pathname: string | null; isCollapsed: boolean }) {
  if (items.length === 0) return null

  return (
    <div className="space-y-0.5">
      {title && !isCollapsed && (
        <div className="px-3 py-2 text-xs font-medium text-zinc-400 uppercase tracking-wider">
          {title}
        </div>
      )}
      {items.map((item) => (
        <NavLink key={item.href} item={item} pathname={pathname} isCollapsed={isCollapsed} />
      ))}
    </div>
  )
}

interface SidebarProps {
  isCollapsed?: boolean
  onToggle?: () => void
}

export function Sidebar({ isCollapsed = false, onToggle: _onToggle }: SidebarProps) {
  const pathname = usePathname()

  return (
    <aside
      aria-label="Sidebar"
      className={cn(
        'flex flex-col bg-zinc-950 border-r border-zinc-800 transition-all duration-300',
        isCollapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Logo */}
      <div className="flex items-center h-14 px-4 border-b border-zinc-800">
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <Shield className="h-7 w-7 text-blue-500" />
          {!isCollapsed && (
            <span className="text-lg font-semibold text-white tracking-tight">
              Pisama
            </span>
          )}
        </Link>
      </div>

      {/* Synth Agent Tenant Switcher */}
      <TenantSwitcher isCollapsed={isCollapsed} />

      {/* Navigation */}
      <nav aria-label="Main navigation" className="flex-1 overflow-y-auto p-3 space-y-5 relative [mask-image:linear-gradient(to_bottom,black_calc(100%-2rem),transparent)]">
        <NavSection title="Observe" items={observeItems} pathname={pathname} isCollapsed={isCollapsed} />
        <NavSection title="Improve" items={improveItems} pathname={pathname} isCollapsed={isCollapsed} />
        <NavSection title="Configure" items={configureItems} pathname={pathname} isCollapsed={isCollapsed} />
        <NavSection title="Settings" items={settingsItems} pathname={pathname} isCollapsed={isCollapsed} />
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-zinc-800">
        <button
          onClick={() => { clearAllCaches(); signOut({ callbackUrl: '/' }) }}
          className="flex items-center gap-2 w-full px-3 py-2 text-sm text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
          aria-label="Sign out"
        >
          <LogOut size={16} />
          {!isCollapsed && <span>Sign out</span>}
        </button>
      </div>
    </aside>
  )
}
