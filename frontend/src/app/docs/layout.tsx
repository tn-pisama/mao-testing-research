'use client'

import { usePathname } from 'next/navigation'
import Link from 'next/link'
import { Layout } from '@/components/common/Layout'
import { clsx } from 'clsx'
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
        <aside className="w-64 flex-shrink-0 border-r border-slate-700 min-h-[calc(100vh-64px)]">
          <div className="p-4 sticky top-0">
            <div className="relative mb-6">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search docs..."
                className="w-full pl-9 pr-4 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-primary-500"
              />
            </div>

            <nav className="space-y-6">
              {docsNav.map((section) => (
                <div key={section.title}>
                  <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
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
                            className={clsx(
                              'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors',
                              isActive
                                ? 'bg-primary-600/20 text-primary-400 font-medium'
                                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
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
              ))}
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
