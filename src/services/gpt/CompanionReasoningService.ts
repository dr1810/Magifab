import { isAiGatewayConfigured, openAIConfig } from '../../config/openai'
import { contextBuilder } from './ContextBuilder'
import type { CompanionProfile, CompanionResponse, SemanticMovieMemory } from './types'

/** Produces personalized runtime companion responses from semantic memory. */
export class CompanionReasoningService {
  /** Requests GPT through the server gateway, falling back to semantic local context in demo mode. */
  public async respond(memory: SemanticMovieMemory, timestamp: number, question: string, profile: CompanionProfile): Promise<CompanionResponse> {
    const context = contextBuilder.build(memory, timestamp, question, profile)
    if (isAiGatewayConfigured()) {
      const response = await fetch(`${openAIConfig.apiBaseUrl}/api/companion/respond`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ context }),
      })
      if (!response.ok) throw new Error('Companion reasoning request failed.')
      const responsePayload = await response.json() as CompanionResponse
      return this.normalizePresentation(responsePayload)
    }
    const point = context.scene.confusionPoints.find((item) => item.suggestedQuestion === question)
    const normalizedQuestion = question.toLowerCase()
    const targetKind = normalizedQuestion.includes('object') || normalizedQuestion.includes('this') ? 'object' : normalizedQuestion.includes('sad') ? 'emotion' : normalizedQuestion.includes('who') ? 'character' : 'event'
    const targetId = targetKind === 'object' ? context.scene.objectIds[0] : targetKind === 'character' ? context.scene.characterIds[0] : context.scene.sceneId
    const targetLabel = targetKind === 'character'
      ? memory.characters.find((character) => character.id === targetId)?.name ?? 'Character'
      : targetKind === 'object'
        ? memory.objects.find((object) => object.id === targetId)?.name ?? 'Important object'
        : targetKind === 'emotion'
          ? context.scene.emotions[0] ?? 'Emotion'
          : context.scene.importantEvents[0] ?? 'Important moment'
    return this.normalizePresentation({
      sceneId: context.scene.sceneId,
      answer: point?.reason || context.scene.summary || 'This moment connects to what the characters have experienced so far.',
      confidence: 0.72,
      shouldShowBubble: true,
      target: { id: targetId || context.scene.sceneId, kind: targetKind, label: targetLabel, anchor: context.scene.companionAnchor },
    })
  }

  /** Ensures runtime reasoning always emits directives consumable by the existing React surfaces. */
  private normalizePresentation(response: CompanionResponse): CompanionResponse {
    return {
      ...response,
      presentation: response.presentation ?? {
        companionMessage: response.answer,
        showCharacterCard: response.target?.kind === 'character',
        showPromptBubble: response.shouldShowBubble,
        target: response.target,
      },
    }
  }
}

export const companionReasoningService = new CompanionReasoningService()
