import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UIState {
  sidebarCollapsed: boolean
  selectedTraceId: string | null
  selectedStateId: string | null
  theme: 'light' | 'dark'
  filterPreferences: {
    status?: string
    detectionType?: string
    dateRange?: { start: string; end: string }
  }
  setSidebarCollapsed: (collapsed: boolean) => void
  setSelectedTrace: (id: string | null) => void
  setSelectedState: (id: string | null) => void
  setTheme: (theme: 'light' | 'dark') => void
  setFilterPreferences: (prefs: Partial<UIState['filterPreferences']>) => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      selectedTraceId: null,
      selectedStateId: null,
      theme: 'dark',
      filterPreferences: {},
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      setSelectedTrace: (id) => set({ selectedTraceId: id }),
      setSelectedState: (id) => set({ selectedStateId: id }),
      setTheme: (theme) => set({ theme }),
      setFilterPreferences: (prefs) =>
        set((state) => ({
          filterPreferences: { ...state.filterPreferences, ...prefs },
        })),
    }),
    {
      name: 'mao-ui-storage',
    }
  )
)
