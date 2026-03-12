import { cn } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  icon: LucideIcon
  label: string
  value: string | number
  color: string
  bgColor: string
}

export function StatCard({ icon: Icon, label, value, color, bgColor }: StatCardProps) {
  return (
    <div className="p-4 rounded-xl bg-zinc-800/50 border border-zinc-700">
      <div className="flex items-center gap-3">
        <div className={cn('p-2 rounded-lg', bgColor)}>
          <Icon size={18} className={color} />
        </div>
        <div>
          <div className="text-2xl font-bold text-white">{value}</div>
          <div className="text-xs text-zinc-400">{label}</div>
        </div>
      </div>
    </div>
  )
}
