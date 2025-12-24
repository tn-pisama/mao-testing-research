'use client'

import { useEffect, useState } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { clsx } from 'clsx'

interface DataPoint {
  name: string
  value: number
  color?: string
  [key: string]: any
}

interface AnimatedBarChartProps {
  data: DataPoint[]
  dataKey?: string
  color?: string
  colors?: string[]
  height?: number
  showGrid?: boolean
  showAxis?: boolean
  animate?: boolean
  layout?: 'horizontal' | 'vertical'
  className?: string
}

const defaultColors = [
  '#6366f1',
  '#8b5cf6',
  '#d946ef',
  '#ec4899',
  '#f43f5e',
  '#f97316',
  '#eab308',
  '#22c55e',
  '#14b8a6',
  '#06b6d4',
]

export function AnimatedBarChart({
  data,
  dataKey = 'value',
  color,
  colors = defaultColors,
  height = 200,
  showGrid = true,
  showAxis = true,
  animate = true,
  layout = 'vertical',
  className,
}: AnimatedBarChartProps) {
  const [animatedData, setAnimatedData] = useState<DataPoint[]>(
    animate ? data.map((d) => ({ ...d, [dataKey]: 0 })) : data
  )

  useEffect(() => {
    if (animate) {
      const timer = setTimeout(() => {
        setAnimatedData(data)
      }, 100)
      return () => clearTimeout(timer)
    }
  }, [data, animate, dataKey])

  return (
    <div className={clsx('w-full', className)} style={{ height }}>
      <ResponsiveContainer>
        <BarChart
          data={animatedData}
          layout={layout}
          margin={{ top: 5, right: 5, bottom: 5, left: showAxis ? 60 : 0 }}
        >
          {showGrid && (
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(71, 85, 105, 0.3)"
              horizontal={layout === 'vertical'}
              vertical={layout === 'horizontal'}
            />
          )}
          {showAxis && layout === 'vertical' && (
            <>
              <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#94a3b8', fontSize: 12 }}
                width={55}
              />
            </>
          )}
          {showAxis && layout === 'horizontal' && (
            <>
              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#64748b', fontSize: 11 }}
              />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
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
            cursor={{ fill: 'rgba(99, 102, 241, 0.1)' }}
          />
          <Bar
            dataKey={dataKey}
            radius={[4, 4, 4, 4]}
            animationDuration={800}
            animationEasing="ease-out"
          >
            {animatedData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.color || color || colors[index % colors.length]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
