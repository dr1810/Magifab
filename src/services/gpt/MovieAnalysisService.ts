import type { MovieData } from '../../types/movie'
import { openAIConfig, isAiGatewayConfigured } from '../../config/openai'
import { semanticMemoryService } from './SemanticMemoryService'
import { moviePreprocessingService } from './MoviePreprocessingService'
import type { MovieAnalysisInput, MoviePreprocessingResult, SemanticMovieMemory } from './types'

/** Runs the one-time import analysis pipeline and persists its semantic result. */
export class MovieAnalysisService {
  /** Runs preprocessing followed by one-time server-side semantic analysis for imported media. */
  public async analyseImportedMovie(input: MovieAnalysisInput): Promise<SemanticMovieMemory> {
    const preprocessedMovie = await moviePreprocessingService.preprocess(input)
    return this.analyseStructuredMovie(input.title, preprocessedMovie)
  }

  /** Sends the GPT-ready structured movie representation to the semantic-analysis gateway. */
  public async analyseStructuredMovie(title: string, preprocessedMovie: MoviePreprocessingResult): Promise<SemanticMovieMemory> {
    if (!isAiGatewayConfigured()) throw new Error('AI gateway is not configured. Set VITE_MAGIFAB_API_URL after server setup.')
    const response = await fetch(`${openAIConfig.apiBaseUrl}/api/movies/analyse`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, ...preprocessedMovie }),
    })
    if (!response.ok) throw new Error('Movie analysis request failed.')
    const memory = await response.json() as SemanticMovieMemory
    semanticMemoryService.save(memory)
    return memory
  }

  /** Converts existing scene metadata to semantic memory, preserving the current demo experience. */
  public seedFromMovie(movie: MovieData): SemanticMovieMemory {
    const existing = semanticMemoryService.get(movie.id)
    if (existing) return existing
    const memory: SemanticMovieMemory = {
      movieId: movie.id, version: 1, createdAt: new Date().toISOString(),
      characters: movie.scenes.flatMap((scene) => scene.characterList).filter((character, index, all) => all.findIndex((item) => item.id === character.id) === index).map((character) => ({ ...character, traits: [character.emotionalState] })),
      relationships: movie.scenes.flatMap((scene) => scene.relationshipGraph.map((relationship) => ({ fromCharacterId: relationship.from, toCharacterId: relationship.to, description: relationship.label, timestamps: [{ start: scene.timestamp, end: scene.timestamp + 60 }] }))),
      objects: movie.scenes.map((scene) => ({ id: `${scene.sceneId}-object`, name: scene.highlightObject.name, significance: scene.highlightObject.reason, timestamps: [{ start: scene.timestamp, end: scene.timestamp + 60 }] })),
      timeline: movie.scenes.flatMap((scene) => scene.timelineData.map((item) => ({ timestamp: scene.timestamp, event: item.label }))),
      scenes: movie.scenes.map((scene, index, all) => ({ sceneId: scene.sceneId, range: { start: scene.timestamp, end: all[index + 1]?.timestamp ?? Number.MAX_SAFE_INTEGER }, summary: scene.voiceNarration, dialogue: scene.subtitle ? [scene.subtitle] : [], emotions: [scene.emotion], importantEvents: [scene.causeEffectData.action], characterIds: scene.characterList.map((character) => character.id), objectIds: [`${scene.sceneId}-object`], accessibilityMetadata: movie.accessibilityTags, confusionPoints: scene.prompts.map((prompt) => ({ timestamp: scene.timestamp, reason: prompt.explanation, suggestedQuestion: prompt.question })), companionAnchor: scene.companionPosition })),
      accessibilityKnowledge: movie.scenes.map((scene, index, all) => ({ sceneId: scene.sceneId, range: { start: scene.timestamp, end: all[index + 1]?.timestamp ?? Number.MAX_SAFE_INTEGER }, metadata: movie.accessibilityTags, description: scene.voiceNarration })),
    }
    semanticMemoryService.save(memory)
    return memory
  }
}

export const movieAnalysisService = new MovieAnalysisService()
