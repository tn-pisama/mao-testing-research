# Frontend Component Patterns

Complete templates for PISAMA frontend development.

---

## UI Component Template

```typescript
'use client'

import { forwardRef } from 'react'
import { clsx } from 'clsx'
import type { VariantProps } from 'class-variance-authority'

// Define variants (optional, can use plain object)
const variants = {
  variant: {
    default: 'bg-slate-700 text-white hover:bg-slate-600',
    primary: 'bg-primary-500 text-white hover:bg-primary-600',
    secondary: 'bg-slate-800 text-slate-200 hover:bg-slate-700',
    ghost: 'bg-transparent hover:bg-slate-800',
    danger: 'bg-danger-500 text-white hover:bg-danger-600',
    warning: 'bg-warning-500 text-white hover:bg-warning-600',
    success: 'bg-success-500 text-white hover:bg-success-600',
  },
  size: {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-base',
    lg: 'px-6 py-3 text-lg',
  },
}

interface ComponentProps extends React.HTMLAttributes<HTMLElement> {
  variant?: keyof typeof variants.variant
  size?: keyof typeof variants.size
  isLoading?: boolean
}

const Component = forwardRef<HTMLElement, ComponentProps>(
  ({ variant = 'default', size = 'md', isLoading, className, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={clsx(
          'base-styles transition-colors',
          variants.variant[variant],
          variants.size[size],
          isLoading && 'opacity-50 cursor-not-allowed',
          className
        )}
        {...props}
      >
        {isLoading ? 'Loading...' : children}
      </div>
    )
  }
)

Component.displayName = 'Component'

export { Component }
export type { ComponentProps }
```

---

## Domain Component Template

```typescript
'use client'

import { useQuery } from '@tanstack/react-query'
import { createApiClient } from '@/lib/api'
import { useSafeAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import type { DomainEntity } from '@/types'

interface DomainComponentProps {
  entityId: string
  onAction?: (entity: DomainEntity) => void
}

export function DomainComponent({ entityId, onAction }: DomainComponentProps) {
  const { getToken } = useSafeAuth()
  const { tenantId } = useTenant()

  // Fetch data
  const { data: entity, isLoading, error } = useQuery({
    queryKey: ['entity', entityId, tenantId],
    queryFn: async () => {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      return api.getEntity(entityId)
    },
    enabled: !!entityId && !!tenantId,
  })

  // Loading state
  if (isLoading) {
    return (
      <Card className="animate-pulse">
        <CardContent>
          <div className="h-20 bg-slate-700 rounded" />
        </CardContent>
      </Card>
    )
  }

  // Error state
  if (error) {
    return (
      <Card>
        <CardContent className="text-danger-500">
          Error: {error.message}
        </CardContent>
      </Card>
    )
  }

  // No data state
  if (!entity) {
    return (
      <Card>
        <CardContent className="text-slate-400">
          No data found
        </CardContent>
      </Card>
    )
  }

  // Success state
  return (
    <Card>
      <CardHeader>
        <CardTitle>{entity.name}</CardTitle>
        <Badge variant={entity.status === 'active' ? 'success' : 'default'}>
          {entity.status}
        </Badge>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-slate-400 mb-4">{entity.description}</p>
        
        {onAction && (
          <Button onClick={() => onAction(entity)}>
            Take Action
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
```

---

## Custom Hook Template

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { createApiClient } from '@/lib/api'
import { useSafeAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'

// Fetch hook
export function useEntities() {
  const { getToken } = useSafeAuth()
  const { tenantId } = useTenant()

  return useQuery({
    queryKey: ['entities', tenantId],
    queryFn: async () => {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      return api.getEntities()
    },
    enabled: !!tenantId,
    staleTime: 60000, // 60 seconds
    refetchOnWindowFocus: false,
  })
}

// Mutation hook
export function useCreateEntity() {
  const queryClient = useQueryClient()
  const { getToken } = useSafeAuth()
  const { tenantId } = useTenant()

  return useMutation({
    mutationFn: async (data: CreateEntityData) => {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      return api.createEntity(data)
    },
    onSuccess: () => {
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: ['entities', tenantId] })
    },
    onError: (error) => {
      console.error('Failed to create entity:', error)
    },
  })
}

// Usage in component:
function EntityManager() {
  const { data: entities, isLoading } = useEntities()
  const createEntity = useCreateEntity()

  const handleCreate = () => {
    createEntity.mutate({ name: 'New Entity' })
  }

  return (
    <div>
      {entities?.map(entity => <EntityCard key={entity.id} entity={entity} />)}
      <Button onClick={handleCreate} isLoading={createEntity.isPending}>
        Create
      </Button>
    </div>
  )
}
```

---

## Page Template (App Router)

```typescript
// /app/entities/page.tsx
'use client'

import { useState } from 'react'
import { useEntities } from '@/hooks/useEntities'
import { EntityList } from '@/components/entities/EntityList'
import { EntityFilters } from '@/components/entities/EntityFilters'
import { Button } from '@/components/ui/Button'
import { PlusIcon } from 'lucide-react'

export default function EntitiesPage() {
  const [filters, setFilters] = useState({ status: 'all' })
  const { data: entities, isLoading, error } = useEntities()

  // Filter entities
  const filteredEntities = entities?.filter(entity => 
    filters.status === 'all' || entity.status === filters.status
  )

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white">Entities</h1>
          <p className="text-slate-400 mt-1">Manage your entities</p>
        </div>
        <Button variant="primary">
          <PlusIcon className="w-4 h-4 mr-2" />
          Create Entity
        </Button>
      </div>

      {/* Filters */}
      <EntityFilters filters={filters} onChange={setFilters} />

      {/* Content */}
      {isLoading && <div className="text-slate-400">Loading...</div>}
      {error && <div className="text-danger-500">Error: {error.message}</div>}
      {filteredEntities && <EntityList entities={filteredEntities} />}
    </div>
  )
}
```

---

## Form Component Template

```typescript
'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'

// Zod schema for validation
const entitySchema = z.object({
  name: z.string().min(3, 'Name must be at least 3 characters'),
  description: z.string().optional(),
  status: z.enum(['active', 'inactive']),
})

type EntityFormData = z.infer<typeof entitySchema>

interface EntityFormProps {
  initialData?: Partial<EntityFormData>
  onSubmit: (data: EntityFormData) => Promise<void>
  onCancel?: () => void
}

export function EntityForm({ initialData, onSubmit, onCancel }: EntityFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<EntityFormData>({
    resolver: zodResolver(entitySchema),
    defaultValues: initialData,
  })

  const onSubmitForm = async (data: EntityFormData) => {
    setIsSubmitting(true)
    try {
      await onSubmit(data)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmitForm)} className="space-y-4">
      {/* Name field */}
      <div>
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          {...register('name')}
          placeholder="Enter name"
        />
        {errors.name && (
          <p className="text-danger-500 text-sm mt-1">{errors.name.message}</p>
        )}
      </div>

      {/* Description field */}
      <div>
        <Label htmlFor="description">Description</Label>
        <Input
          id="description"
          {...register('description')}
          placeholder="Enter description"
        />
      </div>

      {/* Status field */}
      <div>
        <Label htmlFor="status">Status</Label>
        <select
          id="status"
          {...register('status')}
          className="w-full px-3 py-2 bg-slate-700 text-white rounded-md"
        >
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" isLoading={isSubmitting}>
          Submit
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}
```

---

## Modal/Dialog Template

```typescript
'use client'

import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { XIcon } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { clsx } from 'clsx'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl'
}

export function Modal({ isOpen, onClose, title, children, size = 'md' }: ModalProps) {
  // Close on escape key
  useEffect(() => {
    if (!isOpen) return

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  // Prevent body scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = 'unset'
    }
  }, [isOpen])

  if (!isOpen) return null

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div
        className={clsx(
          'relative bg-slate-800 rounded-lg shadow-xl z-10',
          'max-h-[90vh] overflow-y-auto scrollbar-thin',
          size === 'sm' && 'w-full max-w-md',
          size === 'md' && 'w-full max-w-lg',
          size === 'lg' && 'w-full max-w-2xl',
          size === 'xl' && 'w-full max-w-4xl'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-700">
          <h2 className="text-xl font-semibold text-white">{title}</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="text-slate-400 hover:text-white"
          >
            <XIcon className="w-5 h-5" />
          </Button>
        </div>

        {/* Content */}
        <div className="p-6">
          {children}
        </div>
      </div>
    </div>,
    document.body
  )
}

// Usage:
function ExampleComponent() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      <Button onClick={() => setIsOpen(true)}>Open Modal</Button>
      
      <Modal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Modal Title"
        size="md"
      >
        <p>Modal content here</p>
      </Modal>
    </>
  )
}
```

---

## Data Visualization Template (Recharts)

```typescript
'use client'

import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface ChartDataPoint {
  timestamp: string
  value: number
}

interface DataChartProps {
  data: ChartDataPoint[]
  title?: string
}

export function DataChart({ data, title }: DataChartProps) {
  return (
    <div className="bg-slate-800 rounded-lg p-6">
      {title && <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>}
      
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data}>
          {/* Grid */}
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          
          {/* Axes */}
          <XAxis
            dataKey="timestamp"
            stroke="#94a3b8"
            style={{ fontSize: '12px' }}
          />
          <YAxis
            stroke="#94a3b8"
            style={{ fontSize: '12px' }}
          />
          
          {/* Tooltip */}
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '6px',
              color: '#fff',
            }}
          />
          
          {/* Data */}
          <Area
            type="monotone"
            dataKey="value"
            stroke="#0ea5e9"
            fill="url(#colorGradient)"
            strokeWidth={2}
          />
          
          {/* Gradient */}
          <defs>
            <linearGradient id="colorGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.8} />
              <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0.1} />
            </linearGradient>
          </defs>
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
```

---

## Common Patterns Summary

| Pattern | When to Use |
|---------|-------------|
| UI Component | Generic, reusable components |
| Domain Component | Business-specific components with API |
| Custom Hook | Shared data fetching logic |
| Page Template | New page in App Router |
| Form Component | User input with validation |
| Modal/Dialog | Overlay content |
| Data Visualization | Charts and graphs |

All patterns follow PISAMA conventions:
- `'use client'` for interactivity
- Variant-based styling with `clsx`
- TanStack Query for server state
- Zustand for UI state
- TypeScript for type safety
- Consistent color palette
