'use client'

import { usePathname } from 'next/navigation'
import Link from 'next/link'
import { Layout } from '@/components/common/Layout'
import { cn } from '@/lib/utils'
import {
  BookOpen,
  Rocket,
  AlertTriangle,
  Workflow,
  Plug,
  Code,
  ChevronRight,
  Search,
  Package,
  Terminal,
  Boxes,
  Webhook,
  Target,
  Bot,
  Network,
} from 'lucide-react'

const docsNav = [
  {
    title: 'Overview',
    items: [
      { href: '/docs', label: 'Introduction', icon: BookOpen },
      { href: '/docs/getting-started', label: 'Getting Started', icon: Rocket },
    ],
  },
  {
    title: 'Core Concepts',
    items: [
      { href: '/docs/detections', label: 'Detections', icon: AlertTriangle },
      { href: '/docs/failure-modes', label: 'Failure Modes', icon: Target },
      { href: '/docs/traces', label: 'Traces', icon: Workflow },
    ],
  },
  {
    title: 'SDK & Integration',
    items: [
      { href: '/docs/integration', label: 'Setup Guide', icon: Plug },
      { href: '/docs/sdk', label: 'Python SDK', icon: Package },
      { href: '/docs/cli', label: 'CLI Reference', icon: Terminal },
      { href: '/docs/n8n', label: 'n8n Integration', icon: Boxes },
      { href: '/docs/dify', label: 'Dify Integration', icon: Workflow },
      { href: '/docs/openclaw', label: 'OpenClaw Integration', icon: Bot },
      { href: '/docs/langgraph', label: 'LangGraph Integration', icon: Network },
    ],
  },
  {
    title: 'Reference',
    items: [
      { href: '/docs/api-reference', label: 'REST API', icon: Code },
      { href: '/docs/webhooks', label: 'Webhooks', icon: Webhook },
      { href: '/docs/methodology', label: 'Methodology', icon: Target },
    ],
  },
]

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  return (
    <Layout>
      <div className="flex">
        <aside className="w-64 flex-shrink-0 border-r border-zinc-700 min-h-[calc(100vh-64px)]">
          <div className="p-4 sticky top-0">
            <div className="relative mb-6">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                type="text"
                placeholder="Search docs..."
                className="w-full pl-9 pr-4 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-white text-sm placeholder-zinc-500 focus:outline-none focus:border-blue-500"
              />
            </div>

            <nav className="space-y-6">
              {docsNav.map((section) => {
                const sectionActive = section.items.some(item => pathname === item.href)
                return (
                  <div key={section.title}>
                    <h4 className={cn(
                      'text-xs font-semibold uppercase tracking-wider mb-2 pl-3 border-l-2 transition-colors',
                      sectionActive
                        ? 'text-blue-400 border-blue-500'
                        : 'text-zinc-400 border-transparent'
                    )}>
                      {section.title}
                    </h4>
                    <ul className="space-y-1">
                      {section.items.map((item) => {
                        const Icon = item.icon
                        const isActive = pathname === item.href
                        return (
                          <li key={item.href}>
                            <Link
                              href={item.href}
                              className={cn(
                                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors',
                                isActive
                                  ? 'bg-blue-600/20 text-blue-400 font-medium'
                                  : 'text-zinc-300 hover:bg-zinc-800 hover:text-white'
                              )}
                            >
                              <Icon size={16} />
                              {item.label}
                              {isActive && <ChevronRight size={14} className="ml-auto" />}
                            </Link>
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                )
              })}
            </nav>
          </div>
        </aside>

        <main className="flex-1 min-w-0">
          <div className="max-w-4xl mx-auto p-8">
            {children}
          </div>
        </main>
      </div>
    </Layout>
  )
}
