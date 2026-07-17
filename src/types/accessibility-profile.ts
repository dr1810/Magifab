import type { AIProfile, CompanionProfile } from './user'

export type AccessibilityProfile = {
  aiProfile: AIProfile
  companionProfile: CompanionProfile
  completedAt: string
  updatedAt: string
}
