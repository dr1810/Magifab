import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type Settings = {
  fontSize: 'Small' | 'Medium' | 'Large' | 'Extra Large'
  fontFamily: 'Default' | 'OpenDyslexic' | 'Atkinson Hyperlegible' | 'Lexend' | 'Inter'
  letterSpacing: number; lineHeight: number; readingWidth: number
  theme: 'Light' | 'Dark' | 'System'; contrast: 'Normal' | 'High Contrast'
  colorBlindPalette: boolean; reduceBrightColors: boolean; reduceTransparency: boolean
  reduceMotion: boolean; disableAnimations: boolean; reduceHoverEffects: boolean; reduceDistractions: boolean
  subtitleSize: number; subtitlePosition: 'Bottom' | 'Top'; subtitleBackground: 'Transparent' | 'Semi Transparent' | 'Solid'; subtitleWidth: number; subtitleRadius: number
  promptPosition: 'Left' | 'Right' | 'Bottom'; promptSize: number; promptTransparency: number; promptAnimation: 'Fade' | 'Slide' | 'None'; autoHidePrompts: boolean
  highlightStyle: 'Glow' | 'Outline' | 'Pulse' | 'Arrow' | 'Underline' | 'None'; highlightThickness: number; highlightDuration: number
  voiceAssistance: boolean; voiceSpeed: number; voiceVolume: number; readPrompts: boolean
  cursorSize: 'Normal' | 'Large' | 'Extra Large'; keyboardNavigation: boolean; focusIndicator: boolean; stickyNavigation: boolean
  movieSize: number; promptPanelWidth: number; componentSpacing: number; roundedCorners: number
}

export const defaults: Settings = {
  fontSize: 'Medium', fontFamily: 'Default', letterSpacing: 0, lineHeight: 1.5, readingWidth: 68,
  theme: 'Light', contrast: 'Normal', colorBlindPalette: false, reduceBrightColors: false, reduceTransparency: false,
  reduceMotion: false, disableAnimations: false, reduceHoverEffects: false, reduceDistractions: false,
  subtitleSize: 18, subtitlePosition: 'Bottom', subtitleBackground: 'Semi Transparent', subtitleWidth: 82, subtitleRadius: 10,
  promptPosition: 'Right', promptSize: 15, promptTransparency: 90, promptAnimation: 'Fade', autoHidePrompts: false,
  highlightStyle: 'Glow', highlightThickness: 3, highlightDuration: 4,
  voiceAssistance: false, voiceSpeed: 1, voiceVolume: 75, readPrompts: false,
  cursorSize: 'Normal', keyboardNavigation: true, focusIndicator: true, stickyNavigation: true,
  movieSize: 100, promptPanelWidth: 290, componentSpacing: 16, roundedCorners: 14,
}

type ContextValue = { settings: Settings; update: <K extends keyof Settings>(key: K, value: Settings[K]) => void; restore: () => void; save: () => void }
const AccessibilityContext = createContext<ContextValue | null>(null)
const storageKey = 'magifab-accessibility-preferences'

export function AccessibilityProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(() => {
    try { return { ...defaults, ...JSON.parse(localStorage.getItem(storageKey) || '{}') } } catch { return defaults }
  })
  useEffect(() => { document.documentElement.style.fontSize = settings.fontSize === 'Small' ? '14px' : settings.fontSize === 'Large' ? '18px' : settings.fontSize === 'Extra Large' ? '20px' : '16px' }, [settings.fontSize])
  const value = useMemo<ContextValue>(() => ({
    settings,
    update: (key, setting) => setSettings((current) => ({ ...current, [key]: setting })),
    restore: () => setSettings(defaults),
    save: () => localStorage.setItem(storageKey, JSON.stringify(settings)),
  }), [settings])
  return <AccessibilityContext.Provider value={value}>{children}</AccessibilityContext.Provider>
}

export function useAccessibility() {
  const context = useContext(AccessibilityContext)
  if (!context) throw new Error('useAccessibility must be inside AccessibilityProvider')
  return context
}

export const presets: Record<string, Partial<Settings>> = {
  Default: defaults,
  'Low Vision': { fontSize: 'Extra Large', contrast: 'High Contrast', letterSpacing: 1.2, lineHeight: 1.9, subtitleSize: 25, highlightStyle: 'Outline', highlightThickness: 5, cursorSize: 'Large', focusIndicator: true },
  'Dyslexia Friendly': { fontFamily: 'OpenDyslexic', fontSize: 'Large', letterSpacing: 1.4, lineHeight: 1.9, readingWidth: 55, reduceDistractions: true, promptAnimation: 'None' },
  'Reduced Motion': { reduceMotion: true, disableAnimations: true, reduceHoverEffects: true, reduceDistractions: true, promptAnimation: 'None' },
  'High Contrast': { theme: 'Dark', contrast: 'High Contrast', colorBlindPalette: true, reduceTransparency: true, subtitleBackground: 'Solid' },
  'Minimal Interface': { autoHidePrompts: true, promptTransparency: 65, reduceDistractions: true, componentSpacing: 24, roundedCorners: 6, highlightStyle: 'Outline' },
}
