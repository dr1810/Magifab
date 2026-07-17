import type { AssistantAnswer } from '../types/assistant'
import type { MovieData } from '../types/movie'
import { getAccessibilityProfile } from './accessibilityProfileService'
import { companionProfileService } from './gpt/CompanionProfileService'
import { companionReasoningService } from './gpt/CompanionReasoningService'
import { movieAnalysisService } from './gpt/MovieAnalysisService'
import type { CompanionProfile } from './gpt/types'

const assistantAnswers: Record<string, string> = {
  default: 'This moment matters because it changes how the characters trust each other moving forward.',
}

export async function askAssistant(sceneId: string, question: string): Promise<AssistantAnswer> {
  // TODO Backend:
  // Endpoint expected: POST /api/assistant/ask
  // Request: { sceneId: string, question: string }
  // Response: { answer: string, confidence: number, sceneId: string }
  const normalized = `${sceneId}:${question}`.toLowerCase()
  const answer = assistantAnswers[normalized] ?? assistantAnswers.default
  return Promise.resolve({
    sceneId,
    answer,
    confidence: 0.86,
  })
}

const defaultProfile: CompanionProfile = {
  name: 'Lumi', personality: 'Warm and encouraging', appearance: 'Default', voiceStyle: 'Default', explanationStyle: 'Simple and direct', interactionFrequency: 'Only when I ask', detailLevel: 'Just the essentials', accessibilityNeeds: [], conversationStyle: 'Gentle', interactionStyle: 'Gentle bubbles', emotionalSupport: 'Supportive', preferredPromptTypes: [],
}

/**
 * Gets a runtime response using semantic movie memory and the saved onboarding profile.
 * The existing local explanation fallback remains active until the AI gateway is configured.
 */
export async function askCompanion(movie: MovieData, timestamp: number, question: string): Promise<AssistantAnswer> {
  const savedProfile = await getAccessibilityProfile()
  const profile = savedProfile ? companionProfileService.compile(savedProfile) : defaultProfile
  const memory = movieAnalysisService.seedFromMovie(movie)
  const response = await companionReasoningService.respond(memory, timestamp, question, profile)
  return { sceneId: response.sceneId, answer: response.answer, confidence: response.confidence, target: response.target }
}
