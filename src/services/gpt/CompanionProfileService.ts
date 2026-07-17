import type { CompanionProfile, StoredOnboardingProfile } from './types'

/** Compiles the existing onboarding records into the profile sent on every AI request. */
export class CompanionProfileService {
  /** Creates a stable provider-agnostic companion profile from onboarding values. */
  public compile({ companionProfile, aiProfile }: StoredOnboardingProfile): CompanionProfile {
    return {
      name: companionProfile.name,
      personality: companionProfile.personality,
      appearance: companionProfile.appearance,
      voiceStyle: `${companionProfile.voice} · ${companionProfile.voiceSpeed}`,
      explanationStyle: aiProfile.explanationTone,
      interactionFrequency: aiProfile.promptFrequency,
      detailLevel: aiProfile.detailLevel,
      accessibilityNeeds: aiProfile.difficultyAreas,
      conversationStyle: companionProfile.conversationStyle || companionProfile.speakingStyle,
      interactionStyle: aiProfile.interactionStyle || companionProfile.interactionMode,
      emotionalSupport: companionProfile.emotionalSupport,
      preferredPromptTypes: aiProfile.preferredPromptTypes,
    }
  }
}

export const companionProfileService = new CompanionProfileService()
