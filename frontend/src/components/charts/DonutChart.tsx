'use client'

import { useEffect, useState } from 'react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { clsx } from 'clsx'

interface DataPoint {
  name: string
  value: number
  color?: string
}

interface DonutChartProps {
  data: DataPoint[]
  colors?: string[]
  size?: number
  innerRadius?: number
  outerRadius?: number
  centerLabel?: string
  centerValue?: string | number
  animate?: boolean
  className?: string
}

const defaultColors = [
  '#6366f1',
  '#8b5cf6',
  '#d946ef',
  '#ec4899',
  '#f43f5e',
  '#f97316',
]

export function DonutChart({
  data,
  colors = defaultColors,
  size = 200,
  innerRadius = 60,
  outerRadius = 80,
  centerLabel,
  centerValue,
  animate = true,
  className,
}: DonutChartProps) {
  const [animationComplete, setAnimationComplete] = useState(!animate)

  useEffect(() => {
    if (animate) {
      const timer = setTimeout(() => setAnimationComplete(true), 1000)
      return () => clearTimeout(timer)
    }
  }, [animate])

  return (
    <div className={clsx('relative', className)} style={{ width: size, height: size }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            paddingAngle={2}
            dataKey="value"
            animationBegin={0}
            animationDuration={800}
            animationEasing="ease-out"
          >
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.color || colors[index % colors.length]}
                stroke="transparent"
              />
            ))}
          </Pie>
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
        </PieChart>
      </ResponsiveContainer>

      {(centerLabel || centerValue) && (
        <div
          className={clsx(
            'absolute inset-0 flex flex-col items-center justify-center pointer-events-none',
            animationComplete ? 'opacity-100' : 'opacity-0',
            'transition-opacity duration-300'
          )}
        >
          {centerValue && (
            <span className="text-2xl font-bold text-white">{centerValue}</span>
          )}
          {centerLabel && (
            <span className="text-xs text-slate-400 mt-1">{centerLabel}</span>
          )}
        </div>
      )}
    </div>
  )
}
