'use client'

export const dynamic = 'force-dynamic'

import Link from 'next/link'
import { Layout } from '@/components/common/Layout'
import { Card, CardContent } from '@/components/ui/Card'
import {
  Zap,
  Play,
  Shield,
  Bug,
  GitCompare,
  FileJson,
  Terminal,
  ExternalLink,
  Clock,
  CheckCircle,
  ArrowRight,
} from 'lucide-react'

interface Tool {
  id: string
  name: string
  description: string
  icon: React.ElementType
  href: string
  status: 'available' | 'beta' | 'coming_soon'
  lastUsed?: string
}

const tools: Tool[] = [
  {
    id: 'replay',
    name: 'Run Replay',
    description: 'Replay agent runs deterministically for debugging and testing',
    icon: Play,
    href: '/replay',
    status: 'available',
    lastUsed: '2 hours ago',
  },
  {
    id: 'chaos',
    name: 'Chaos Injection',
    description: 'Inject failures and edge cases to test agent resilience',
    icon: Bug,
    href: '/chaos',
    status: 'available',
    lastUsed: '1 day ago',
  },
  {
    id: 'security',
    name: 'Security Scanner',
    description: 'Scan for prompt injection, hallucination, and other vulnerabilities',
    icon: Shield,
    href: '/security',
    status: 'available',
  },
  {
    id: 'regression',
    name: 'Regression Testing',
    description: 'Compare agent behavior against baselines to detect drift',
    icon: GitCompare,
    href: '/regression',
    status: 'available',
  },
  {
    id: 'diagnose',
    name: 'Agent Forensics',
    description: 'Deep-dive analysis of agent execution with AI-powered insights',
    icon: Terminal,
    href: '/diagnose',
    status: 'available',
  },
  {
    id: 'import',
    name: 'Run Import',
    description: 'Import runs from LangSmith, OpenTelemetry, or custom formats',
    icon: FileJson,
    href: '/import',
    status: 'available',
  },
]

function getStatusBadge(status: Tool['status']) {
  switch (status) {
    case 'available':
      return (
        <span className="flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-emerald-500/20 text-emerald-400">
          <CheckCircle size={12} />
          Available
        </span>
      )
    case 'beta':
      return (
        <span className="px-2 py-0.5 text-xs rounded-full bg-amber-500/20 text-amber-400">
          Beta
        </span>
      )
    case 'coming_soon':
      return (
        <span className="px-2 py-0.5 text-xs rounded-full bg-zinc-500/20 text-zinc-400">
          Coming Soon
        </span>
      )
  }
}

export default function ToolsPage() {
  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-yellow-600/20 rounded-lg">
                <Zap className="w-6 h-6 text-yellow-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">Testing Tools</h1>
            </div>
            <p className="text-zinc-400">
              Powerful tools for debugging, testing, and analyzing your AI agents
            </p>
          </div>
        </div>

        {/* Tools Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tools.map((tool) => {
            const Icon = tool.icon
            const isDisabled = tool.status === 'coming_soon'

            return (
              <Link
                key={tool.id}
                href={isDisabled ? '#' : tool.href}
                className={`block ${isDisabled ? 'cursor-not-allowed' : ''}`}
              >
                <Card className={`h-full transition-all ${isDisabled ? 'opacity-60' : 'hover:border-zinc-600 hover:bg-zinc-800/50'}`}>
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-2 bg-zinc-700 rounded-lg">
                        <Icon size={20} className="text-zinc-300" />
                      </div>
                      {getStatusBadge(tool.status)}
                    </div>
                    <h3 className="text-white font-semibold mb-1">{tool.name}</h3>
                    <p className="text-sm text-zinc-400 mb-3">{tool.description}</p>
                    <div className="flex items-center justify-between">
                      {tool.lastUsed ? (
                        <span className="text-xs text-zinc-500 flex items-center gap-1">
                          <Clock size={12} />
                          Used {tool.lastUsed}
                        </span>
                      ) : (
                        <span />
                      )}
                      {!isDisabled && (
                        <ArrowRight size={16} className="text-zinc-500" />
                      )}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            )
          })}
        </div>

        {/* Documentation Section */}
        <div className="mt-8 p-6 bg-zinc-800/50 rounded-xl border border-zinc-700">
          <h3 className="text-lg font-semibold text-white mb-4">Documentation</h3>
          <div className="grid md:grid-cols-2 gap-4">
            <Link
              href="/docs/cli"
              className="flex items-center justify-between p-4 bg-zinc-900 rounded-lg hover:bg-zinc-800 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Terminal size={20} className="text-zinc-400" />
                <div>
                  <div className="text-sm font-medium text-white">CLI Reference</div>
                  <div className="text-xs text-zinc-400">Use tools from the command line</div>
                </div>
              </div>
              <ExternalLink size={16} className="text-zinc-500" />
            </Link>
            <Link
              href="/docs/sdk"
              className="flex items-center justify-between p-4 bg-zinc-900 rounded-lg hover:bg-zinc-800 transition-colors"
            >
              <div className="flex items-center gap-3">
                <FileJson size={20} className="text-zinc-400" />
                <div>
                  <div className="text-sm font-medium text-white">SDK Integration</div>
                  <div className="text-xs text-zinc-400">Integrate tools into your codebase</div>
                </div>
              </div>
              <ExternalLink size={16} className="text-zinc-500" />
            </Link>
          </div>
        </div>
      </div>
    </Layout>
  )
}
