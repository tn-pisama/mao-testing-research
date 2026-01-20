'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

export type UserType = 'n8n_user' | 'developer' | null

interface UserPreferences {
  userType: UserType
  developerMode: boolean
}

interface UserPreferencesContextType {
  preferences: UserPreferences
  setUserType: (type: UserType) => void
  setDeveloperMode: (enabled: boolean) => void
  isN8nUser: boolean
  showAdvancedFeatures: boolean
}

const defaultPreferences: UserPreferences = {
  userType: null,
  developerMode: false,
}

const UserPreferencesContext = createContext<UserPreferencesContextType | undefined>(undefined)

const STORAGE_KEY = 'mao_user_preferences'

export function UserPreferencesProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState<UserPreferences>(defaultPreferences)
  const [isLoaded, setIsLoaded] = useState(false)

  // Load preferences from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        setPreferences({
          userType: parsed.userType || null,
          developerMode: parsed.developerMode || false,
        })
      }
    } catch (e) {
      console.error('Failed to load user preferences:', e)
    }
    setIsLoaded(true)
  }, [])

  // Save preferences to localStorage when they change
  useEffect(() => {
    if (isLoaded) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences))
      } catch (e) {
        console.error('Failed to save user preferences:', e)
      }
    }
  }, [preferences, isLoaded])

  const setUserType = (type: UserType) => {
    setPreferences(prev => ({
      ...prev,
      userType: type,
      // Developers get developer mode enabled by default
      developerMode: type === 'developer' ? true : prev.developerMode,
    }))
  }

  const setDeveloperMode = (enabled: boolean) => {
    setPreferences(prev => ({ ...prev, developerMode: enabled }))
  }

  // Helper computed values
  const isN8nUser = preferences.userType === 'n8n_user'
  const showAdvancedFeatures = preferences.userType === 'developer' || preferences.developerMode

  const value = {
    preferences,
    setUserType,
    setDeveloperMode,
    isN8nUser,
    showAdvancedFeatures,
  }

  return (
    <UserPreferencesContext.Provider value={value}>
      {children}
    </UserPreferencesContext.Provider>
  )
}

export function useUserPreferences() {
  const context = useContext(UserPreferencesContext)
  if (context === undefined) {
    throw new Error('useUserPreferences must be used within a UserPreferencesProvider')
  }
  return context
}
