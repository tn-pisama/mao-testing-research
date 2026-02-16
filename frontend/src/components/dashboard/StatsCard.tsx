'use client'

import { LucideIcon, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { Card } from '../ui/Card'
import clsx from 'clsx'

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
    iconBg: 'bg-primary-500/20 border border-primary-500/30 shadow-glow-cyan',
    iconColor: 'text-primary-500',
  },
  green: {
    iconBg: 'bg-success-500/20 border border-success-500/30',
    iconColor: 'text-success-500',
  },
  yellow: {
    iconBg: 'bg-accent-500/20 border border-accent-500/30',
    iconColor: 'text-accent-500',
  },
  red: {
    iconBg: 'bg-danger-500/20 border border-danger-500/30',
    iconColor: 'text-danger-500',
  },
  purple: {
    iconBg: 'bg-accent-500/20 border border-accent-500/30',
    iconColor: 'text-accent-500',
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
      ? 'text-success-500'
      : 'text-danger-500'

  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-white/60 font-mono">{title}</p>
          <p className="mt-1 text-3xl font-bold text-primary-500 font-mono">{value}</p>
          {change !== undefined && (
            <div className="flex items-center mt-2 gap-1">
              <TrendIcon size={14} className={trendColor} />
              <span className={clsx('text-sm font-medium font-mono', trendColor)}>
                {change >= 0 ? '+' : ''}{change}%
              </span>
              <span className="text-xs text-white/40 font-mono">{changeLabel}</span>
            </div>
          )}
        </div>
        <div className={clsx('p-3 rounded-lg', styles.iconBg)}>
          <Icon size={24} className={styles.iconColor} />
        </div>
      </div>
    </Card>
  )
}
