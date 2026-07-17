import type { CompanionProfile, RuntimeContext, SemanticMovieMemory } from './types'
import { semanticMemoryService } from './SemanticMemoryService'

/** Builds the minimal, relevant context payload for a runtime companion request. */
export class ContextBuilder {
  /** Selects scene-local memory and a short timeline window for the current playback position. */
  public build(memory: SemanticMovieMemory, timestamp: number, question: string, profile: CompanionProfile): RuntimeContext {
    const scene = semanticMemoryService.getScene(memory, timestamp)
    return {
      movieId: memory.movieId,
      timestamp,
      scene,
      recentTimeline: memory.timeline.filter((item) => item.timestamp <= timestamp).slice(-5),
      relevantRelationships: memory.relationships.filter((relationship) =>
        scene.characterIds.includes(relationship.fromCharacterId) || scene.characterIds.includes(relationship.toCharacterId)),
      accessibilityKnowledge: semanticMemoryService.getAccessibilityKnowledge(memory, timestamp),
      profile,
      question,
    }
  }
}

export const contextBuilder = new ContextBuilder()
