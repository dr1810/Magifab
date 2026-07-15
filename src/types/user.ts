import type { Settings } from './accessibility'

export type CompanionProfile = {
  name: string
  appearance: string
  personality: string
  voice: string
  voiceSpeed: string
  speakingStyle: string
  interactionMode: string
  conversationStyle: string
  emotionalSupport: string
}

export type AIProfile = {
  difficultyAreas: string[]
  preferredExplanationMethods: string[]
  preferredVisualAssistance: string[]
  promptFrequency: string
  detailLevel: string
  interactionStyle: string
  explanationTone: string
  preferredPromptTypes: string[]
}

export type UserProfile = {
  accessibilitySettings: Settings
  companionProfile: CompanionProfile | null
  aiProfile: AIProfile | null
}
