import { getAIProfile, getCompanionProfile, saveAIProfile, saveCompanionProfile } from './userService'
import type { AccessibilityProfile } from '../types/accessibility-profile'
import type { AIProfile, CompanionProfile } from '../types/user'

const PROFILE_STORAGE_KEY = 'magifab-accessibility-profile'

function readProfile(): AccessibilityProfile | null {
  try {
    const saved = localStorage.getItem(PROFILE_STORAGE_KEY)
    return saved ? (JSON.parse(saved) as AccessibilityProfile) : null
  } catch {
    return null
  }
}

export async function getAccessibilityProfile(): Promise<AccessibilityProfile | null> {
  const saved = readProfile()
  if (saved) return saved

  const [aiProfile, companionProfile] = await Promise.all([getAIProfile(), getCompanionProfile()])
  if (!aiProfile || !companionProfile) return null

  const migrated: AccessibilityProfile = {
    aiProfile,
    companionProfile,
    completedAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }
  localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(migrated))
  return migrated
}

export async function saveAccessibilityProfile({ aiProfile, companionProfile }: Pick<AccessibilityProfile, 'aiProfile' | 'companionProfile'>): Promise<AccessibilityProfile> {
  // TODO BACKEND
  // Replace with a single user accessibility profile endpoint.
  await Promise.all([saveAIProfile(aiProfile), saveCompanionProfile(companionProfile)])
  const existing = readProfile()
  const now = new Date().toISOString()
  const profile: AccessibilityProfile = {
    aiProfile,
    companionProfile,
    completedAt: existing?.completedAt ?? now,
    updatedAt: now,
  }
  localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile))
  return profile
}

export type AccessibilityProfileInput = { aiProfile: AIProfile; companionProfile: CompanionProfile }
