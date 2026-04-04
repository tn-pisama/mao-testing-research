'use client'

import { useEffect, useState, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { cn } from '@/lib/utils'
import { Bot, ChevronDown, Activity, AlertTriangle, Wrench } from 'lucide-react'
// Token override is stored in localStorage.pisama_override_token
// and read by useSafeAuth.getToken() before any other auth path

interface SynthTenant {
  id: string
  name: string
  agent_name: string
  traces: number
  detections: number
  healings: number
}

const AGENT_DESCRIPTIONS: Record<string, string> = {
  ava: 'LangGraph pipeline',
  bram: 'SDK integration',
  clara: 'Self-healing',
  diego: 'Evaluator',
  elin: 'Multi-framework',
}

export function TenantSwitcher({ isCollapsed }: { isCollapsed: boolean }) {
  const [tenants, setTenants] = useState<SynthTenant[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [activeTenant, setActiveTenant] = useState<SynthTenant | null>(null)
  const [switching, setSwitching] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  useEffect(() => {
    fetch('/api/synth-tenants')
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        return r.json()
      })
      .then((data) => {
        const list: SynthTenant[] = data.tenants || []
        setTenants(list)
      })
      .catch((err) => {
        setLoadError(err.message)
        console.error('[TenantSwitcher] Failed to fetch synth tenants:', err)
      })
  }, [])

  const switchTenant = useCallback(async (tenant: SynthTenant) => {
    setSwitching(true)
    try {
      const resp = await fetch('/api/synth-tenants', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tenantId: tenant.id }),
      })
      if (!resp.ok) return
      const data = await resp.json()

      // Store token + tenant in localStorage — survives page navigation
      localStorage.setItem('pisama_override_token', data.access_token)
      localStorage.setItem('pisama_last_tenant', data.tenant_id)

      setActiveTenant(tenant)
      setIsOpen(false)

      // Force all queries to refetch with the new token + tenant
      // Navigate to dashboard to trigger a full re-render with new tenant context
      window.location.href = '/dashboard'
    } finally {
      setSwitching(false)
    }
  }, [queryClient])

  if (tenants.length === 0) {
    return (
      <div className="px-3 py-2">
        <div className="flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-zinc-600">
          <Bot size={14} />
          {!isCollapsed && (
            <span>{loadError ? `Err: ${loadError.slice(0, 30)}` : 'Loading agents...'}</span>
          )}
        </div>
      </div>
    )
  }

  if (isCollapsed) {
    return (
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'flex items-center justify-center w-10 h-10 mx-auto rounded-lg transition-colors',
          activeTenant
            ? 'bg-violet-500/20 text-violet-400'
            : 'text-zinc-400 hover:bg-zinc-800'
        )}
        title={activeTenant ? `Viewing: ${activeTenant.agent_name}` : 'Switch tenant'}
      >
        <Bot size={18} />
      </button>
    )
  }

  return (
    <div className="relative px-3 py-2">
      {/* Trigger */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-sm transition-colors',
          activeTenant
            ? 'bg-violet-500/10 border border-violet-500/30 text-violet-300'
            : 'bg-zinc-900 border border-zinc-800 text-zinc-400 hover:border-zinc-700'
        )}
      >
        <Bot size={16} className="shrink-0" />
        <span className="flex-1 text-left truncate">
          {activeTenant
            ? activeTenant.agent_name.charAt(0).toUpperCase() + activeTenant.agent_name.slice(1)
            : 'Synth Agents'}
        </span>
        <ChevronDown size={14} className={cn('transition-transform', isOpen && 'rotate-180')} />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute left-3 right-3 top-full mt-1 z-50 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl overflow-hidden">
          {tenants.map((tenant) => (
            <button
              key={tenant.id}
              onClick={() => switchTenant(tenant)}
              disabled={switching}
              className={cn(
                'w-full flex items-start gap-2.5 px-3 py-2.5 text-left transition-colors',
                activeTenant?.id === tenant.id
                  ? 'bg-violet-500/10 text-violet-300'
                  : 'text-zinc-300 hover:bg-zinc-800'
              )}
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium capitalize">{tenant.agent_name}</div>
                <div className="text-xs text-zinc-500">
                  {AGENT_DESCRIPTIONS[tenant.agent_name] || ''}
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
                  <span className="flex items-center gap-1">
                    <Activity size={10} /> {tenant.traces}
                  </span>
                  <span className="flex items-center gap-1">
                    <AlertTriangle size={10} /> {tenant.detections}
                  </span>
                  <span className="flex items-center gap-1">
                    <Wrench size={10} /> {tenant.healings}
                  </span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
