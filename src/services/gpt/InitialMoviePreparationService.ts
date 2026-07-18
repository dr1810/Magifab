import type { MovieData } from '../../types/movie'
import { movieAnalysisService } from './MovieAnalysisService'
import type { SemanticMovieMemory } from './types'

/** Stable event names for the preparation UI and future backend progress stream. */
export type PreparationMilestoneId =
  | 'accessibility-needs'
  | 'companion-profile'
  | 'story-exploration'
  | 'characters'
  | 'relationships'
  | 'scenes'
  | 'objects'
  | 'accessibility-explanations'
  | 'semantic-memory'
  | 'personalized-guidance'

export type PreparationProgressEvent = {
  milestone: PreparationMilestoneId
  status: 'active' | 'complete'
  /** True only when the first portion of the movie can be supported immediately. */
  readyForPlayback?: boolean
}

type ProgressReporter = (event: PreparationProgressEvent) => void
const presentationPause = () => new Promise<void>((resolve) => window.setTimeout(resolve, 140))

/**
 * Builds and validates the minimum semantic knowledge needed before playback.
 *
 * This is deliberately event-driven: an uploaded-movie backend can emit the same
 * events over SSE/WebSocket without requiring any UI changes.
 */
export class InitialMoviePreparationService {
  async prepare(movie: MovieData, report: ProgressReporter): Promise<SemanticMovieMemory> {
    report({ milestone: 'story-exploration', status: 'active' })
    await presentationPause()
    const memory = movieAnalysisService.ensureMovieKnowledge(movie)
    report({ milestone: 'story-exploration', status: 'complete' })
    await presentationPause()

    const validations: Array<[PreparationMilestoneId, () => boolean]> = [
      ['characters', () => memory.characters.length > 0],
      ['relationships', () => memory.relationships.length > 0],
      ['scenes', () => memory.scenes.length > 0],
      ['objects', () => memory.objects.length > 0],
      ['accessibility-explanations', () => memory.accessibilityKnowledge.length > 0],
      ['semantic-memory', () => memory.scenes.some((scene) => scene.range.start === 0 && scene.confusionPoints.length > 0)],
    ]

    for (const [milestone, isReady] of validations) {
      report({ milestone, status: 'active' })
      await presentationPause()
      if (!isReady()) throw new Error(`Initial semantic knowledge is missing ${milestone}.`)
      report({ milestone, status: 'complete' })
      await presentationPause()
    }

    report({ milestone: 'personalized-guidance', status: 'active' })
    await presentationPause()
    // This is the readiness gate. Later preprocessing can expand this memory in
    // the background, but the opening scene and its guidance are available now.
    report({ milestone: 'personalized-guidance', status: 'complete', readyForPlayback: true })
    return memory
  }
}

export const initialMoviePreparationService = new InitialMoviePreparationService()
