'use client'

import {
  BarChart as RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'

interface DataPoint {
  [key: string]: string | number
}

interface BarChartProps {
  data: DataPoint[]
  xKey: string
  yKey: string
  color?: string
  colors?: string[]
  height?: number
  showGrid?: boolean
  horizontal?: boolean
}

export function BarChart({
  data,
  xKey,
  yKey,
  color = '#3b82f6',
  colors,
  height = 200,
  showGrid = true,
  horizontal = false,
}: BarChartProps) {
  const ChartComponent = horizontal ? RechartsBarChart : RechartsBarChart

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ChartComponent
        data={data}
        layout={horizontal ? 'vertical' : 'horizontal'}
        margin={{ top: 10, right: 10, left: horizontal ? 80 : 0, bottom: 0 }}
      >
        {showGrid && (
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        )}
        {horizontal ? (
          <>
            <XAxis type="number" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey={xKey} stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} width={80} />
          </>
        ) : (
          <>
            <XAxis dataKey={xKey} stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} width={40} />
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
        <Bar dataKey={yKey} radius={[4, 4, 0, 0]}>
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} fill={colors ? colors[index % colors.length] : color} />
          ))}
        </Bar>
      </ChartComponent>
    </ResponsiveContainer>
  )
}
