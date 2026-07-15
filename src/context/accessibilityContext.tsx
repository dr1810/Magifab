import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getAccessibilitySettings, saveAccessibilitySettings } from '../services/userService'
import { accessibilityPresets, defaultSettings, type Settings } from '../types/accessibility'

type ContextValue = {
  settings: Settings
  update: <K extends keyof Settings>(key: K, value: Settings[K]) => void
  restore: () => void
  save: () => void
  presets: Record<string, Partial<Settings>>
}

const AccessibilityContext = createContext<ContextValue | null>(null)

export function AccessibilityProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(defaultSettings)

  useEffect(() => {
    void getAccessibilitySettings().then((stored) => {
      setSettings(stored)
    })
  }, [])

  useEffect(() => {
    document.documentElement.style.fontSize =
      settings.fontSize === 'Small'
        ? '14px'
        : settings.fontSize === 'Large'
          ? '18px'
          : settings.fontSize === 'Extra Large'
            ? '20px'
            : '16px'
  }, [settings.fontSize])

  const value = useMemo<ContextValue>(
    () => ({
      settings,
      update: (key, setting) => setSettings((current) => ({ ...current, [key]: setting })),
      restore: () => setSettings(defaultSettings),
      save: () => {
        void saveAccessibilitySettings(settings)
      },
      presets: accessibilityPresets,
    }),
    [settings],
  )

  return <AccessibilityContext.Provider value={value}>{children}</AccessibilityContext.Provider>
}

export function useAccessibility() {
  const context = useContext(AccessibilityContext)
  if (!context) {
    throw new Error('useAccessibility must be used inside AccessibilityProvider')
  }
  return context
}

export type { Settings }
export const defaults = defaultSettings
export const presets = accessibilityPresets
