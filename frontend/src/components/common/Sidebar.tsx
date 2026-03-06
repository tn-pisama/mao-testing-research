'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
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
  Workflow,
  Bot,
  Network,
  Terminal,
  MessageSquare,
  Brain,
} from 'lucide-react'
import { useUserPreferences } from '@/lib/user-preferences'

interface NavItem {
  label: string
  href: string
  icon: React.ElementType
  badge?: string
  advancedOnly?: boolean
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
  { label: 'Detector Status', href: '/detector-status', icon: Shield },
]

const developerImproveItems: NavItem[] = [
  { label: 'Quality', href: '/quality', icon: Star },
  { label: 'Custom Scorers', href: '/evals/scorers', icon: Sparkles },
  { label: 'Conversations', href: '/conversation-evaluations', icon: MessageSquare },
  { label: 'Memory', href: '/memory', icon: Brain },
  { label: 'Healing', href: '/healing', icon: Sparkles },
  { label: 'Replay', href: '/replay', icon: RotateCcw },
  { label: 'Benchmarks', href: '/benchmarks', icon: BarChart3, advancedOnly: true },
]

const developerConfigureItems: NavItem[] = [
  { label: 'Integrations', href: '/integrations', icon: Box },
  { label: 'Agents', href: '/agents', icon: Users },
  { label: 'n8n Workflows', href: '/n8n', icon: GitBranch },
  { label: 'Dify Apps', href: '/dify', icon: Workflow },
  { label: 'OpenClaw', href: '/openclaw', icon: Bot },
  { label: 'LangGraph', href: '/langgraph', icon: Network },
  { label: 'Tools', href: '/tools', icon: Zap },
  { label: 'Developer API', href: '/tools/developer-api', icon: Terminal },
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
        className={cn(
          'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors duration-150',
          isActive
            ? 'bg-blue-500/10 text-blue-400 border-l-2 border-blue-500 -ml-px'
            : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
        )}
      >
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
      </Link>
    )
  }

  const NavSection = ({ title, items }: { title?: string; items: NavItem[] }) => {
    const filteredItems = items.filter(item => !item.advancedOnly || showAdvancedFeatures)

    if (filteredItems.length === 0) return null

    return (
      <div className="space-y-0.5">
        {title && !isCollapsed && (
          <div className="px-3 py-2 text-xs font-medium text-zinc-400 uppercase tracking-wider">
            {title}
          </div>
        )}
        {filteredItems.map((item) => (
          <NavLink key={item.href} item={item} />
        ))}
      </div>
    )
  }

  const isSimplifiedView = isN8nUser && !showAdvancedFeatures

  return (
    <aside
      className={cn(
        'flex flex-col bg-zinc-950 border-r border-zinc-800 transition-all duration-300',
        isCollapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Logo */}
      <div className="flex items-center h-14 px-4 border-b border-zinc-800">
        <Link href="/" className="flex items-center gap-2.5">
          <Shield className="h-7 w-7 text-blue-500" />
          {!isCollapsed && (
            <span className="text-lg font-semibold text-white tracking-tight">
              {isSimplifiedView ? 'Workflow Guard' : 'Pisama'}
            </span>
          )}
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-5 relative [mask-image:linear-gradient(to_bottom,black_calc(100%-2rem),transparent)]">
        {isSimplifiedView ? (
          <>
            <NavSection title="Observe" items={n8nObserveItems} />
            <NavSection title="Improve" items={n8nImproveItems} />
            <NavSection title="Settings" items={n8nSettingsItems} />
          </>
        ) : (
          <>
            <NavSection title="Observe" items={developerObserveItems} />
            <NavSection title="Improve" items={developerImproveItems} />
            <NavSection title="Configure" items={developerConfigureItems} />
            <NavSection title="Settings" items={developerSettingsItems} />
          </>
        )}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-zinc-800">
        {!isCollapsed && (
          <div className="text-xs text-zinc-500">
            {isSimplifiedView ? (
              <>
                <div>Workflow Guard</div>
                <div className="text-zinc-600">Powered by Pisama</div>
              </>
            ) : (
              <>
                <div className="text-zinc-400">Pisama Platform</div>
                <div>v1.0.0</div>
              </>
            )}
          </div>
        )}
      </div>
    </aside>
  )
}
