'use client'

import { useEffect, useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts'
import { clsx } from 'clsx'

interface DataPoint {
  name: string
  value: number
  [key: string]: any
}

interface AnimatedLineChartProps {
  data: DataPoint[]
  dataKey?: string
  color?: string
  gradientFrom?: string
  gradientTo?: string
  height?: number
  showGrid?: boolean
  showAxis?: boolean
  animate?: boolean
  className?: string
}

export function AnimatedLineChart({
  data,
  dataKey = 'value',
  color = '#6366f1',
  gradientFrom = 'rgba(99, 102, 241, 0.3)',
  gradientTo = 'rgba(99, 102, 241, 0)',
  height = 200,
  showGrid = true,
  showAxis = true,
  animate = true,
  className,
}: AnimatedLineChartProps) {
  const [animatedData, setAnimatedData] = useState<DataPoint[]>([])

  useEffect(() => {
    if (animate) {
      setAnimatedData([])
      data.forEach((point, index) => {
        setTimeout(() => {
          setAnimatedData((prev) => [...prev, point])
        }, index * 50)
      })
    } else {
      setAnimatedData(data)
    }
  }, [data, animate])

  const gradientId = `gradient-${Math.random().toString(36).substring(7)}`

  return (
    <div className={clsx('w-full', className)} style={{ height }}>
      <ResponsiveContainer>
        <AreaChart data={animatedData} margin={{ top: 5, right: 5, bottom: 5, left: showAxis ? 0 : -20 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={gradientFrom} />
              <stop offset="100%" stopColor={gradientTo} />
            </linearGradient>
          </defs>
          {showGrid && (
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(71, 85, 105, 0.3)" vertical={false} />
          )}
          {showAxis && (
            <>
              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#64748b', fontSize: 11 }}
                dy={10}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#64748b', fontSize: 11 }}
                width={40}
              />
            </>
          )}
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '8px',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3)',
            }}
            labelStyle={{ color: '#f1f5f9', fontWeight: 600 }}
            itemStyle={{ color: '#94a3b8' }}
          />
          <Area
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={2}
            fill={`url(#${gradientId})`}
            animationDuration={500}
            dot={false}
            activeDot={{
              r: 4,
              fill: color,
              stroke: '#0f172a',
              strokeWidth: 2,
            }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
