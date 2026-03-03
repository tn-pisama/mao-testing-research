'use client'

import { createContext, useContext, useState, useEffect, ReactNode, useRef, useId, KeyboardEvent, useCallback } from 'react'
import { cn } from '@/lib/utils'

interface TabsContextType {
  value: string
  onValueChange: (value: string) => void
  tabsId: string
  registerTab: (value: string) => void
  getTabIndex: (value: string) => number
  tabs: string[]
}

const TabsContext = createContext<TabsContextType | undefined>(undefined)

interface TabsProps {
  value?: string
  defaultValue?: string
  onValueChange?: (value: string) => void
  children: ReactNode
  className?: string
}

export function Tabs({ value: controlledValue, defaultValue, onValueChange, children, className }: TabsProps) {
  const [uncontrolledValue, setUncontrolledValue] = useState(defaultValue || '')
  const [tabs, setTabs] = useState<string[]>([])
  const tabsId = useId()

  const value = controlledValue ?? uncontrolledValue
  const handleValueChange = (newValue: string) => {
    if (controlledValue === undefined) {
      setUncontrolledValue(newValue)
    }
    onValueChange?.(newValue)
  }

  const registerTab = useCallback((tabValue: string) => {
    setTabs(prev => {
      if (!prev.includes(tabValue)) {
        return [...prev, tabValue]
      }
      return prev
    })
  }, [])

  const getTabIndex = useCallback((tabValue: string) => tabs.indexOf(tabValue), [tabs])

  return (
    <TabsContext.Provider value={{ value, onValueChange: handleValueChange, tabsId, registerTab, getTabIndex, tabs }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  )
}

interface TabsListProps {
  children: ReactNode
  className?: string
}

export function TabsList({ children, className }: TabsListProps) {
  const context = useContext(TabsContext)
  if (!context) throw new Error('TabsList must be used within Tabs')

  const listRef = useRef<HTMLDivElement>(null)

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const { tabs, value, onValueChange } = context
    const currentIndex = tabs.indexOf(value)

    let newIndex = currentIndex
    switch (e.key) {
      case 'ArrowLeft':
        newIndex = currentIndex > 0 ? currentIndex - 1 : tabs.length - 1
        e.preventDefault()
        break
      case 'ArrowRight':
        newIndex = currentIndex < tabs.length - 1 ? currentIndex + 1 : 0
        e.preventDefault()
        break
      case 'Home':
        newIndex = 0
        e.preventDefault()
        break
      case 'End':
        newIndex = tabs.length - 1
        e.preventDefault()
        break
      default:
        return
    }

    if (newIndex !== currentIndex && tabs[newIndex]) {
      onValueChange(tabs[newIndex])
      const buttons = listRef.current?.querySelectorAll('[role="tab"]')
      if (buttons?.[newIndex]) {
        (buttons[newIndex] as HTMLElement).focus()
      }
    }
  }

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-orientation="horizontal"
      onKeyDown={handleKeyDown}
      className={cn('flex gap-1 border-b border-zinc-800', className)}
    >
      {children}
    </div>
  )
}

interface TabsTriggerProps {
  value: string
  children: ReactNode
  className?: string
}

export function TabsTrigger({ value, children, className }: TabsTriggerProps) {
  const context = useContext(TabsContext)
  if (!context) throw new Error('TabsTrigger must be used within Tabs')

  const { value: activeValue, onValueChange, tabsId, registerTab } = context
  const isActive = activeValue === value

  useEffect(() => {
    registerTab(value)
  }, [registerTab, value])

  const tabId = `${tabsId}-tab-${value}`
  const panelId = `${tabsId}-panel-${value}`

  return (
    <button
      id={tabId}
      role="tab"
      aria-selected={isActive}
      aria-controls={panelId}
      tabIndex={isActive ? 0 : -1}
      onClick={() => onValueChange(value)}
      className={cn(
        'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950',
        isActive
          ? 'text-white border-blue-500'
          : 'text-zinc-500 border-transparent hover:text-zinc-300 hover:border-zinc-700',
        className
      )}
    >
      {children}
    </button>
  )
}

interface TabsContentProps {
  value: string
  children: ReactNode
  className?: string
}

export function TabsContent({ value, children, className }: TabsContentProps) {
  const context = useContext(TabsContext)
  if (!context) throw new Error('TabsContent must be used within Tabs')

  const { value: activeValue, tabsId } = context

  if (activeValue !== value) return null

  const tabId = `${tabsId}-tab-${value}`
  const panelId = `${tabsId}-panel-${value}`

  return (
    <div
      id={panelId}
      role="tabpanel"
      aria-labelledby={tabId}
      tabIndex={0}
      className={cn('mt-4 focus:outline-none', className)}
    >
      {children}
    </div>
  )
}
