'use client'

import { useState, useEffect, useRef } from 'react'
import { clsx } from 'clsx'
import {
  Activity,
  Cpu,
  MemoryStick,
  Wifi,
  Clock,
  Zap,
  TrendingUp,
  TrendingDown,
  Circle,
  PlayCircle,
  PauseCircle,
  RefreshCw,
} from 'lucide-react'

interface MonitoringData {
  timestamp: number
  cpu: number
  memory: number
  latency: number
  tokensPerSec: number
  activeConnections: number
}

interface AgentMonitoringPanelProps {
  isLive?: boolean
}

function generateDataPoint(): MonitoringData {
  return {
    timestamp: Date.now(),
    cpu: Math.floor(Math.random() * 40) + 20,
    memory: Math.floor(Math.random() * 30) + 40,
    latency: Math.floor(Math.random() * 200) + 50,
    tokensPerSec: Math.floor(Math.random() * 500) + 100,
    activeConnections: Math.floor(Math.random() * 10) + 2,
  }
}

export function AgentMonitoringPanel({ isLive: initialIsLive = true }: AgentMonitoringPanelProps) {
  const [isLive, setIsLive] = useState(initialIsLive)
  const [data, setData] = useState<MonitoringData[]>([])
  const [currentData, setCurrentData] = useState<MonitoringData>(generateDataPoint())
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (isLive) {
      const interval = setInterval(() => {
        const newPoint = generateDataPoint()
        setCurrentData(newPoint)
        setData((prev) => [...prev.slice(-60), newPoint])
      }, 1000)
      return () => clearInterval(interval)
    }
  }, [isLive])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || data.length < 2) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const width = canvas.width
    const height = canvas.height

    ctx.clearRect(0, 0, width, height)

    ctx.strokeStyle = 'rgba(71, 85, 105, 0.3)'
    ctx.lineWidth = 1
    for (let i = 0; i <= 4; i++) {
      const y = (height / 4) * i
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(width, y)
      ctx.stroke()
    }

    const drawLine = (values: number[], color: string, maxValue: number) => {
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.beginPath()

      values.forEach((value, index) => {
        const x = (index / (values.length - 1)) * width
        const y = height - (value / maxValue) * height

        if (index === 0) {
          ctx.moveTo(x, y)
        } else {
          ctx.lineTo(x, y)
        }
      })
      ctx.stroke()
    }

    drawLine(data.map((d) => d.cpu), '#6366f1', 100)
    drawLine(data.map((d) => d.memory), '#8b5cf6', 100)
    drawLine(data.map((d) => d.latency), '#22c55e', 500)
  }, [data])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={clsx(
            'p-2 rounded-lg',
            isLive ? 'bg-emerald-500/20' : 'bg-slate-700'
          )}>
            <Activity size={20} className={isLive ? 'text-emerald-400' : 'text-slate-400'} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">Real-time Monitoring</h2>
            <div className="flex items-center gap-2 text-xs text-slate-400">
              {isLive && (
                <span className="flex items-center gap-1">
                  <Circle size={8} className="text-emerald-400 fill-emerald-400 animate-pulse" />
                  Live
                </span>
              )}
              <span>Updated every 1s</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsLive(!isLive)}
            className={clsx(
              'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all',
              isLive
                ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            )}
          >
            {isLive ? <PauseCircle size={16} /> : <PlayCircle size={16} />}
            {isLive ? 'Pause' : 'Resume'}
          </button>
          <button
            onClick={() => setData([])}
            className="p-2 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-4">
        <MetricCard
          icon={Cpu}
          label="CPU Usage"
          value={`${currentData.cpu}%`}
          trend={currentData.cpu > 60 ? 'warning' : 'normal'}
          color="text-indigo-400"
          bgColor="bg-indigo-500/20"
        />
        <MetricCard
          icon={MemoryStick}
          label="Memory"
          value={`${currentData.memory}%`}
          trend={currentData.memory > 80 ? 'warning' : 'normal'}
          color="text-purple-400"
          bgColor="bg-purple-500/20"
        />
        <MetricCard
          icon={Clock}
          label="Latency"
          value={`${currentData.latency}ms`}
          trend={currentData.latency > 200 ? 'warning' : 'normal'}
          color="text-emerald-400"
          bgColor="bg-emerald-500/20"
        />
        <MetricCard
          icon={Zap}
          label="Tokens/sec"
          value={currentData.tokensPerSec.toString()}
          trend="normal"
          color="text-amber-400"
          bgColor="bg-amber-500/20"
        />
        <MetricCard
          icon={Wifi}
          label="Connections"
          value={currentData.activeConnections.toString()}
          trend="normal"
          color="text-cyan-400"
          bgColor="bg-cyan-500/20"
        />
      </div>

      <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-white">Performance Graph</h3>
          <div className="flex items-center gap-4">
            <Legend color="#6366f1" label="CPU" />
            <Legend color="#8b5cf6" label="Memory" />
            <Legend color="#22c55e" label="Latency" />
          </div>
        </div>
        <div className="relative h-48 bg-slate-900/50 rounded-lg overflow-hidden">
          <canvas
            ref={canvasRef}
            width={800}
            height={200}
            className="w-full h-full"
          />
          {data.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center text-slate-500 text-sm">
              Waiting for data...
            </div>
          )}
        </div>
        <div className="flex justify-between mt-2 text-xs text-slate-500">
          <span>60s ago</span>
          <span>30s ago</span>
          <span>Now</span>
        </div>
      </div>
    </div>
  )
}

interface MetricCardProps {
  icon: typeof Cpu
  label: string
  value: string
  trend: 'normal' | 'warning' | 'critical'
  color: string
  bgColor: string
}

function MetricCard({ icon: Icon, label, value, trend, color, bgColor }: MetricCardProps) {
  return (
    <div className={clsx(
      'p-4 rounded-xl border transition-all',
      trend === 'warning' ? 'border-amber-500/30 bg-amber-500/5' :
      trend === 'critical' ? 'border-red-500/30 bg-red-500/5' :
      'border-slate-700 bg-slate-800/50'
    )}>
      <div className="flex items-center gap-2 mb-2">
        <div className={clsx('p-1.5 rounded-lg', bgColor)}>
          <Icon size={14} className={color} />
        </div>
        <span className="text-xs text-slate-400">{label}</span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xl font-bold text-white">{value}</span>
        {trend === 'warning' && (
          <TrendingUp size={14} className="text-amber-400" />
        )}
      </div>
    </div>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-3 h-0.5 rounded" style={{ backgroundColor: color }} />
      <span className="text-xs text-slate-400">{label}</span>
    </div>
  )
}
