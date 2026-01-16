'use client'

import {
  AreaChart as RechartsAreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

interface DataPoint {
  [key: string]: string | number
}

interface AreaChartProps {
  data: DataPoint[]
  xKey: string
  yKey: string
  color?: string
  gradient?: boolean
  height?: number
  showGrid?: boolean
  showAxis?: boolean
}

export function AreaChart({
  data,
  xKey,
  yKey,
  color = '#3b82f6',
  gradient = true,
  height = 200,
  showGrid = true,
  showAxis = true,
}: AreaChartProps) {
  const gradientId = `gradient-${yKey}`

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsAreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        {gradient && (
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
        )}
        {showGrid && (
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
        )}
        {showAxis && (
          <>
            <XAxis
              dataKey={xKey}
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              width={40}
            />
          </>
        )}
        <Tooltip
          contentStyle={{
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '8px',
            color: '#f1f5f9',
          }}
        />
        <Area
          type="monotone"
          dataKey={yKey}
          stroke={color}
          strokeWidth={2}
          fill={gradient ? `url(#${gradientId})` : color}
          fillOpacity={gradient ? 1 : 0.2}
        />
      </RechartsAreaChart>
    </ResponsiveContainer>
  )
}
