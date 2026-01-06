'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import dynamic from 'next/dynamic'
import {
  LayoutDashboard,
  Workflow,
  AlertTriangle,
  Settings,
  Menu,
  X,
  Bot,
  PlayCircle,
  BookOpen,
  Zap,
  RotateCcw,
  GitBranch,
  FlaskConical,
  Search,
  User,
  Target,
  Users
} from 'lucide-react'
import { useUIStore } from '@/stores/uiStore'
import { clsx } from 'clsx'

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY

// Dynamically import UserButton to avoid SSR issues when Clerk isn't configured
const UserButton = dynamic(
  () => import('@clerk/nextjs').then(mod => mod.UserButton),
  {
    ssr: false,
    loading: () => (
      <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center">
        <User size={16} className="text-slate-400" />
      </div>
    )
  }
)

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/diagnose', label: 'Diagnose', icon: Search, badge: 'New' },
  { href: '/agents', label: 'Agents', icon: Bot, badge: 'Live' },
  { href: '/traces', label: 'Traces', icon: Workflow },
  { href: '/detections', label: 'Detections', icon: AlertTriangle },
  { href: '/testing', label: 'Testing', icon: FlaskConical },
  { href: '/chaos', label: 'Chaos', icon: Zap },
  { href: '/replay', label: 'Replay', icon: RotateCcw },
  { href: '/regression', label: 'Regression', icon: GitBranch },
  { href: '/demo', label: 'Demo', icon: PlayCircle },
  { href: '/benchmarks', label: 'Benchmarks', icon: Target },
  { href: '/case-studies', label: 'Case Studies', icon: Users },
  { href: '/docs', label: 'Docs', icon: BookOpen },
  { href: '/settings', label: 'Settings', icon: Settings },
]

export function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { sidebarCollapsed, setSidebarCollapsed } = useUIStore()

  return (
    <div className="min-h-screen bg-slate-900 flex">
      <aside
        className={clsx(
          'bg-slate-800 border-r border-slate-700 transition-all duration-300 flex flex-col',
          sidebarCollapsed ? 'w-16' : 'w-64'
        )}
      >
        {/* Logo */}
        <div className="p-4 border-b border-slate-700">
          <Link href="/dashboard" className="flex items-center gap-2">
            {sidebarCollapsed ? (
              <span className="text-xl font-black text-white tracking-tight">P</span>
            ) : (
              <span className="text-2xl font-black text-white tracking-tight">PISAMA</span>
            )}
          </Link>
        </div>

        {/* User & Toggle */}
        <div className="p-4 flex items-center justify-between border-b border-slate-700">
          {!sidebarCollapsed && (
            hasClerk ? (
              <UserButton afterSignOutUrl="/" />
            ) : (
              <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center">
                <User size={16} className="text-slate-400" />
              </div>
            )
          )}
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-2 text-slate-400 hover:text-white transition-colors"
          >
            {sidebarCollapsed ? <Menu size={20} /> : <X size={20} />}
          </button>
        </div>
        <nav className="p-2">
          {navItems.map((item) => {
            const isActive = pathname.startsWith(item.href)
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200 mb-1 group',
                  isActive
                    ? 'bg-primary-600 text-white shadow-lg shadow-primary-500/20'
                    : 'text-slate-400 hover:bg-slate-700 hover:text-white'
                )}
              >
                <item.icon size={20} className={clsx(isActive && 'animate-pulse-subtle')} />
                {!sidebarCollapsed && (
                  <span className="flex-1 flex items-center justify-between">
                    <span>{item.label}</span>
                    {item.badge && (
                      <span className={clsx(
                        'px-1.5 py-0.5 text-[10px] font-medium rounded-full',
                        item.badge === 'Live' 
                          ? 'bg-emerald-500/20 text-emerald-400' 
                          : 'bg-purple-500/20 text-purple-400'
                      )}>
                        {item.badge}
                      </span>
                    )}
                  </span>
                )}
              </Link>
            )
          })}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  )
}
