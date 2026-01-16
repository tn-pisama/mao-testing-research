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
    iconBg: 'bg-blue-500/20',
    iconColor: 'text-blue-400',
  },
  green: {
    iconBg: 'bg-green-500/20',
    iconColor: 'text-green-400',
  },
  yellow: {
    iconBg: 'bg-yellow-500/20',
    iconColor: 'text-yellow-400',
  },
  red: {
    iconBg: 'bg-red-500/20',
    iconColor: 'text-red-400',
  },
  purple: {
    iconBg: 'bg-purple-500/20',
    iconColor: 'text-purple-400',
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
    ? 'text-slate-400'
    : change >= 0
      ? 'text-green-400'
      : 'text-red-400'

  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-400">{title}</p>
          <p className="mt-1 text-3xl font-bold text-white">{value}</p>
          {change !== undefined && (
            <div className="flex items-center mt-2 gap-1">
              <TrendIcon size={14} className={trendColor} />
              <span className={clsx('text-sm font-medium', trendColor)}>
                {change >= 0 ? '+' : ''}{change}%
              </span>
              <span className="text-xs text-slate-500">{changeLabel}</span>
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
