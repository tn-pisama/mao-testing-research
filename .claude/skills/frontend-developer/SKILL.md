---
name: frontend-developer
description: |
  Patterns for PISAMA frontend development with Next.js, React, and TailwindCSS.
  Use when building UI components, pages, state management, or API integration.
  Ensures consistent patterns with existing codebase conventions.
allowed-tools: Read, Grep, Glob, Write
---

# Frontend Developer Skill

You are developing the PISAMA frontend with Next.js 16, React 18, and TailwindCSS. Your goal is to follow established patterns for components, state management, and API integration.

## Component Architecture

### UI Components vs Domain Components

**UI Components** (`/src/components/ui/`):
- Generic, reusable components (Button, Card, Badge, Tooltip)
- Use variant pattern for styling
- No business logic
- Forward refs for composability

**Domain Components** (`/src/components/{domain}/`):
- Business-specific (AgentCard, TraceTimeline, HealingWorkflow)
- Connect to API via TanStack Query
- Handle domain-specific logic

---

## Component Development Patterns

### Pattern 1: UI Component with Variants

```typescript
'use client'

import { forwardRef } from 'react'
import { clsx } from 'clsx'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', isLoading, className, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={clsx(
          'rounded-md font-medium transition-colors',
          // Variants
          variant === 'primary' && 'bg-primary-500 text-white hover:bg-primary-600',
          variant === 'secondary' && 'bg-slate-700 text-white hover:bg-slate-600',
          variant === 'ghost' && 'bg-transparent hover:bg-slate-800',
          variant === 'danger' && 'bg-danger-500 text-white hover:bg-danger-600',
          // Sizes
          size === 'sm' && 'px-3 py-1.5 text-sm',
          size === 'md' && 'px-4 py-2 text-base',
          size === 'lg' && 'px-6 py-3 text-lg',
          // Loading state
          isLoading && 'opacity-50 cursor-not-allowed',
          className
        )}
        disabled={isLoading || props.disabled}
        {...props}
      >
        {isLoading ? 'Loading...' : children}
      </button>
    )
  }
)

Button.displayName = 'Button'

export { Button }
```

### Pattern 2: Domain Component with API

```typescript
'use client'

import { useQuery } from '@tanstack/react-query'
import { createApiClient } from '@/lib/api'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'

interface AgentCardProps {
  agentId: string
}

export function AgentCard({ agentId }: AgentCardProps) {
  const { data: agent, isLoading } = useQuery({
    queryKey: ['agent', agentId],
    queryFn: async () => {
      const api = createApiClient()
      return api.getAgent(agentId)
    },
  })

  if (isLoading) {
    return <Card className="animate-pulse">Loading...</Card>
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{agent.name}</CardTitle>
        <Badge variant={agent.status === 'active' ? 'success' : 'default'}>
          {agent.status}
        </Badge>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-slate-400">{agent.description}</p>
      </CardContent>
    </Card>
  )
}
```

### Pattern 3: Custom Hook for API

```typescript
import { useQuery } from '@tanstack/react-query'
import { createApiClient } from '@/lib/api'
import { useSafeAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'

export function useTraces() {
  const { getToken } = useSafeAuth()
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: ['traces', tenantId],
    queryFn: async () => {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      return api.getTraces()
    },
    enabled: !!tenantId,
  })
}

// Usage in component:
function TracesPage() {
  const { data: traces, isLoading, error } = useTraces()
  
  if (isLoading) return <div>Loading...</div>
  if (error) return <div>Error: {error.message}</div>
  
  return <TraceList traces={traces} />
}
```

---

## TailwindCSS Conventions

### Custom Classes (in globals.css)

```css
/* Animation */
.animate-fade-in { animation: fadeIn 0.3s ease-in; }
.animate-slide-in-right { animation: slideInRight 0.4s ease-out; }
.animate-pulse-subtle { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }

/* Glass morphism */
.glass {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

/* Text gradient */
.text-gradient {
  background: linear-gradient(135deg, #0ea5e9 0%, #22c55e 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* Custom scrollbar */
.scrollbar-thin::-webkit-scrollbar {
  width: 6px;
}
.scrollbar-thin::-webkit-scrollbar-track {
  background: rgb(15 23 42);
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background: rgb(51 65 85);
  border-radius: 3px;
}
```

### Color Usage

```typescript
// Status colors
<Badge variant="success">Active</Badge>     // Green
<Badge variant="warning">Pending</Badge>     // Amber
<Badge variant="danger">Failed</Badge>       // Red

// Background gradients
<div className="bg-gradient-to-br from-slate-950 to-slate-900">

// Text colors
<p className="text-slate-400">Secondary text</p>
<p className="text-primary-500">Link text</p>
```

---

## State Management

### Pattern 1: Zustand Store

```typescript
// /src/stores/uiStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UIState {
  sidebarCollapsed: boolean
  selectedTraceId: string | null
  theme: 'light' | 'dark'
  setSidebarCollapsed: (collapsed: boolean) => void
  setSelectedTraceId: (id: string | null) => void
  setTheme: (theme: 'light' | 'dark') => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      selectedTraceId: null,
      theme: 'dark',
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      setSelectedTraceId: (id) => set({ selectedTraceId: id }),
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: 'mao-ui-storage',
    }
  )
)

// Usage:
function Sidebar() {
  const { sidebarCollapsed, setSidebarCollapsed } = useUIStore()
  
  return (
    <div className={clsx('transition-all', sidebarCollapsed ? 'w-16' : 'w-64')}>
      <button onClick={() => setSidebarCollapsed(!sidebarCollapsed)}>
        Toggle
      </button>
    </div>
  )
}
```

### Pattern 2: TanStack Query Mutations

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createApiClient } from '@/lib/api'

export function useDeleteTrace() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (traceId: string) => {
      const api = createApiClient()
      return api.deleteTrace(traceId)
    },
    onSuccess: () => {
      // Invalidate traces query to refetch
      queryClient.invalidateQueries({ queryKey: ['traces'] })
    },
  })
}

// Usage:
function TraceActions({ traceId }: { traceId: string }) {
  const deleteTrace = useDeleteTrace()

  return (
    <Button
      variant="danger"
      onClick={() => deleteTrace.mutate(traceId)}
      isLoading={deleteTrace.isPending}
    >
      Delete
    </Button>
  )
}
```

---

## API Integration

### Pattern 1: API Client with Demo Fallback

```typescript
// /src/hooks/useApiWithFallback.ts
import { useQuery } from '@tanstack/react-query'
import { createApiClient } from '@/lib/api'
import { generateDemoTraces } from '@/lib/demo-data'

export function useTracesWithFallback() {
  return useQuery({
    queryKey: ['traces-with-fallback'],
    queryFn: async () => {
      try {
        const api = createApiClient()
        const traces = await api.getTraces()
        return { traces, isDemoMode: false }
      } catch (error) {
        // Fallback to demo data
        console.warn('API failed, using demo data:', error)
        return { traces: generateDemoTraces(), isDemoMode: true }
      }
    },
  })
}

// Usage:
function TracesPage() {
  const { data } = useTracesWithFallback()
  
  return (
    <div>
      {data?.isDemoMode && (
        <Badge variant="warning">Demo Mode</Badge>
      )}
      <TraceList traces={data?.traces} />
    </div>
  )
}
```

---

## Authentication

### Pattern: Protected Page

```typescript
// Middleware automatically protects routes in /src/middleware.ts
// For components, use useSafeAuth:

'use client'

import { useSafeAuth } from '@/hooks/useSafeAuth'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

export function ProtectedContent() {
  const { isSignedIn, isLoaded } = useSafeAuth()
  const router = useRouter()

  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.push('/sign-in')
    }
  }, [isLoaded, isSignedIn, router])

  if (!isLoaded || !isSignedIn) {
    return <div>Loading...</div>
  }

  return <div>Protected content here</div>
}
```

---

## Testing with Playwright

### Pattern: Page Test

```typescript
// /tests/e2e/authenticated/dashboard.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Dashboard', () => {
  test('shows Live badge for active deployment', async ({ page }) => {
    await page.goto('/dashboard')
    
    // Wait for page to load
    await page.waitForSelector('h1:has-text("Dashboard")')
    
    // Check for Live badge
    const liveBadge = page.locator('text=Live').first()
    await expect(liveBadge).toBeVisible()
  })

  test('loads without 404 errors', async ({ page }) => {
    const responses: string[] = []
    
    page.on('response', response => {
      if (response.status() === 404) {
        responses.push(response.url())
      }
    })
    
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')
    
    expect(responses).toHaveLength(0)
  })
})
```

---

## Component Checklist

- [ ] Uses `'use client'` directive (if interactive)
- [ ] Proper TypeScript interfaces for props
- [ ] Uses `clsx` for conditional classes
- [ ] Forwards ref if composable (UI components)
- [ ] Error boundaries for data-fetching components
- [ ] Loading states for async operations
- [ ] Proper ARIA labels for accessibility
- [ ] Responsive design (mobile-first)
- [ ] Consistent with existing color palette
- [ ] Demo mode fallback (if using API)

---

## Resources

For detailed patterns and templates:
- `resources/component-patterns.md` - Full component templates and examples
- `frontend/src/components/ui/` - Reference UI component implementations
- `frontend/docs/` - Frontend-specific documentation
