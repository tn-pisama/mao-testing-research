'use client'

import { clsx } from 'clsx'
import { LucideIcon, Inbox, Search, AlertCircle, Workflow, Bot } from 'lucide-react'

type EmptyStateVariant = 'default' | 'search' | 'error' | 'traces' | 'agents' | 'detections'

const variants: Record<EmptyStateVariant, { icon: LucideIcon; title: string; description: string }> = {
  default: {
    icon: Inbox,
    title: 'No data yet',
    description: 'Data will appear here once available.',
  },
  search: {
    icon: Search,
    title: 'No results found',
    description: 'Try adjusting your search or filter criteria.',
  },
  error: {
    icon: AlertCircle,
    title: 'Something went wrong',
    description: 'An error occurred while loading data. Please try again.',
  },
  traces: {
    icon: Workflow,
    title: 'No traces recorded',
    description: 'Start your multi-agent workflow to begin collecting traces.',
  },
  agents: {
    icon: Bot,
    title: 'No agents active',
    description: 'Deploy agents to see them in action here.',
  },
  detections: {
    icon: AlertCircle,
    title: 'No issues detected',
    description: 'Your agents are running smoothly with no anomalies.',
  },
}

interface EmptyStateProps {
  variant?: EmptyStateVariant
  title?: string
  description?: string
  icon?: LucideIcon
  action?: React.ReactNode
  className?: string
}

export function EmptyState({
  variant = 'default',
  title,
  description,
  icon,
  action,
  className,
}: EmptyStateProps) {
  const config = variants[variant]
  const Icon = icon || config.icon
  const displayTitle = title || config.title
  const displayDescription = description || config.description

  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center py-12 px-6 text-center',
        className
      )}
    >
      <div className="p-4 rounded-full bg-slate-800/50 border border-slate-700 mb-4">
        <Icon size={32} className="text-slate-500" />
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">{displayTitle}</h3>
      <p className="text-sm text-slate-400 max-w-sm mb-4">{displayDescription}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
