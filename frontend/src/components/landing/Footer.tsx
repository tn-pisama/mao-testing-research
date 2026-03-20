'use client'

import Link from 'next/link'
import { Shield } from 'lucide-react'

const resourceLinks = [
  { label: 'Documentation', href: '/docs' },
  { label: 'API Reference', href: '/docs/api-reference' },
  { label: 'Getting Started', href: '/docs/getting-started' },
  { label: 'Failure Modes', href: '/docs/failure-modes' },
]

const integrationLinks = [
  { label: 'n8n', href: '/docs/n8n' },
  { label: 'LangGraph', href: '/docs/langgraph' },
  { label: 'Dify', href: '/docs/dify' },
  { label: 'OpenClaw', href: '/docs/openclaw' },
  { label: 'SDK', href: '/docs/sdk' },
]

export function Footer() {
  return (
    <footer className="border-t border-zinc-800">
      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-8 mb-8">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Shield size={20} className="text-blue-500" />
              <span className="font-semibold text-white">Pisama</span>
            </div>
            <p className="text-sm text-zinc-500 leading-relaxed">
              Agent forensics for teams building with AI.
            </p>
          </div>

          {/* Resources */}
          <div>
            <h4 className="text-sm font-medium text-zinc-300 mb-3">Resources</h4>
            <ul className="space-y-2">
              {resourceLinks.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Integrations */}
          <div>
            <h4 className="text-sm font-medium text-zinc-300 mb-3">Integrations</h4>
            <ul className="space-y-2">
              {integrationLinks.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="pt-6 border-t border-zinc-800 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-zinc-600">
            &copy; {new Date().getFullYear()} Pisama. All rights reserved.
          </p>
          <div className="flex items-center gap-4">
            <Link href="/terms" className="text-xs text-zinc-600 hover:text-zinc-400 transition-colors">
              Terms
            </Link>
            <Link href="/terms" className="text-xs text-zinc-600 hover:text-zinc-400 transition-colors">
              Privacy
            </Link>
          </div>
        </div>
      </div>
    </footer>
  )
}
