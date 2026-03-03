'use client'

import { LucideIcon, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { Card } from '../ui/Card'
import { cn } from '@/lib/utils'

interface StatsCardProps {
  title: string
  value: string | number
  icon: LucideIcon
  change?: number
  changeLabel?: string
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple'
}

const colorStyles = {
  blue: {
    iconBg: 'bg-blue-500/10 border border-zinc-700',
    iconColor: 'text-blue-400',
  },
  green: {
    iconBg: 'bg-green-500/20 border border-green-500/30',
    iconColor: 'text-green-500',
  },
  yellow: {
    iconBg: 'bg-violet-500/20 border border-violet-500/30',
    iconColor: 'text-violet-500',
  },
  red: {
    iconBg: 'bg-red-500/20 border border-red-500/30',
    iconColor: 'text-red-500',
  },
  purple: {
    iconBg: 'bg-violet-500/20 border border-violet-500/30',
    iconColor: 'text-violet-500',
  },
}

export function StatsCard({
  title,
  value,
  icon: Icon,
  change,
  changeLabel = 'vs last period',
  color = 'blue',
}: StatsCardProps) {
  const styles = colorStyles[color]

  const TrendIcon = change === undefined ? Minus : change >= 0 ? TrendingUp : TrendingDown
  const trendColor = change === undefined
    ? 'text-white/60'
    : change >= 0
      ? 'text-green-500'
      : 'text-red-500'

  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-white/60">{title}</p>
          <p className="mt-1 text-3xl font-bold text-white font-mono">{value}</p>
          {change !== undefined && (
            <div className="flex items-center mt-2 gap-1">
              <TrendIcon size={14} className={trendColor} />
              <span className={cn('text-sm font-medium font-mono', trendColor)}>
                {change >= 0 ? '+' : ''}{change}%
              </span>
              <span className="text-xs text-white/40">{changeLabel}</span>
            </div>
          )}
        </div>
        <div className={cn('p-3 rounded-lg', styles.iconBg)}>
          <Icon size={24} className={styles.iconColor} />
        </div>
      </div>
    </Card>
  )
}
