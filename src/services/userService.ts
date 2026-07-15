import type { Settings } from '../types/accessibility'
import type { AIProfile, CompanionProfile, UserProfile } from '../types/user'
import { defaultSettings } from '../types/accessibility'

const ACCESSIBILITY_STORAGE_KEY = 'magifab-accessibility-preferences'
const COMPANION_STORAGE_KEY = 'magifab-companion-profile'
const AI_PROFILE_STORAGE_KEY = 'magifab-ai-profile'

function readJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

export async function saveAccessibilitySettings(settings: Settings): Promise<Settings> {
  // TODO Backend:
  // Endpoint expected: PUT /api/users/me/accessibility-settings
  // Request: { settings: Settings }
  // Response: { settings: Settings, updatedAt: string }
  localStorage.setItem(ACCESSIBILITY_STORAGE_KEY, JSON.stringify(settings))
  return Promise.resolve(settings)
}

export async function getAccessibilitySettings(): Promise<Settings> {
  // TODO Backend:
  // Endpoint expected: GET /api/users/me/accessibility-settings
  // Request: no body
  // Response: { settings: Settings }
  const stored = readJson<Settings>(ACCESSIBILITY_STORAGE_KEY)
  return Promise.resolve({ ...defaultSettings, ...(stored ?? {}) })
}

export async function saveCompanionProfile(profile: CompanionProfile): Promise<CompanionProfile> {
  // TODO Backend:
  // Endpoint expected: PUT /api/users/me/companion-profile
  // Request: { profile: CompanionProfile }
  // Response: { profile: CompanionProfile, updatedAt: string }
  localStorage.setItem(COMPANION_STORAGE_KEY, JSON.stringify(profile))
  return Promise.resolve(profile)
}

export async function getCompanionProfile(): Promise<CompanionProfile | null> {
  // TODO Backend:
  // Endpoint expected: GET /api/users/me/companion-profile
  // Request: no body
  // Response: { profile: CompanionProfile | null }
  return Promise.resolve(readJson<CompanionProfile>(COMPANION_STORAGE_KEY))
}

export async function saveAIProfile(profile: AIProfile): Promise<AIProfile> {
  // TODO Backend:
  // Endpoint expected: PUT /api/users/me/assistant-preferences
  // Request: { profile: AIProfile }
  // Response: { profile: AIProfile, updatedAt: string }
  localStorage.setItem(AI_PROFILE_STORAGE_KEY, JSON.stringify(profile))
  return Promise.resolve(profile)
}

export async function getAIProfile(): Promise<AIProfile | null> {
  // TODO Backend:
  // Endpoint expected: GET /api/users/me/assistant-preferences
  // Request: no body
  // Response: { profile: AIProfile | null }
  return Promise.resolve(readJson<AIProfile>(AI_PROFILE_STORAGE_KEY))
}

export async function getUserProfile(): Promise<UserProfile> {
  // TODO Backend:
  // Endpoint expected: GET /api/users/me
  // Request: no body
  // Response: { user: UserProfile }
  const [accessibilitySettings, companionProfile, aiProfile] = await Promise.all([
    getAccessibilitySettings(),
    getCompanionProfile(),
    getAIProfile(),
  ])

  return Promise.resolve({
    accessibilitySettings,
    companionProfile,
    aiProfile,
  })
}
