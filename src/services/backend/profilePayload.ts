import type { AccessibilityProfile } from '../../types/accessibility-profile'
import type { CompanionProfilePayload } from './MoviePreprocessingBackendService'

export function companionProfilePayload(profile: AccessibilityProfile | null): CompanionProfilePayload {
  const ai = profile?.aiProfile
  return { personality: profile?.companionProfile.personality ?? 'warm', accessibility_needs: ai?.difficultyAreas ?? [], difficulties: ai?.difficultyAreas ?? [], preferred_explanation_style: ai?.detailLevel ?? 'simple' }
}
