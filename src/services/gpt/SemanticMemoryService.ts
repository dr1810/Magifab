import type { AccessibilityKnowledge, SemanticMovieMemory, SemanticScene } from './types'

const storageKey = (movieId: string) => `magifab-semantic-memory:${movieId}`

/** Stores and retrieves timestamp-indexed semantic movie memory. */
export class SemanticMemoryService {
  private readonly cache = new Map<string, SemanticMovieMemory>()

  /** Saves memory locally now; replace this persistence boundary with the backend database later. */
  public save(memory: SemanticMovieMemory): void {
    this.cache.set(memory.movieId, memory)
    localStorage.setItem(storageKey(memory.movieId), JSON.stringify(memory))
  }

  /** Gets semantic memory for a movie, if it has been analysed. */
  public get(movieId: string): SemanticMovieMemory | null {
    const cached = this.cache.get(movieId)
    if (cached) return cached
    try {
      const raw = localStorage.getItem(storageKey(movieId))
      if (!raw) return null
      const memory = JSON.parse(raw) as SemanticMovieMemory
      this.cache.set(movieId, memory)
      return memory
    } catch {
      return null
    }
  }

  /** Finds the scene containing a playback timestamp. */
  public getScene(memory: SemanticMovieMemory, timestamp: number): SemanticScene {
    return memory.scenes.find((scene) => timestamp >= scene.range.start && timestamp < scene.range.end)
      ?? memory.scenes.at(-1)
      ?? { sceneId: 'unknown', range: { start: 0, end: 0 }, summary: '', dialogue: [], emotions: [], importantEvents: [], characterIds: [], visibleCharacters: [], objectIds: [], location: 'Unknown', keyFrameTimestamps: [], accessibilityMetadata: [], confusionPoints: [], companionAnchor: { x: 50, y: 38 } }
  }

  /** Returns accessibility guidance associated with the current scene timestamp. */
  public getAccessibilityKnowledge(memory: SemanticMovieMemory, timestamp: number): AccessibilityKnowledge | null {
    return memory.accessibilityKnowledge?.find((item) => timestamp >= item.range.start && timestamp < item.range.end) ?? null
  }
}

export const semanticMemoryService = new SemanticMemoryService()
