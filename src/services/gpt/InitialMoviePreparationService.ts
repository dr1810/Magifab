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
 * Presentation-only loading milestones. The backend companion pipeline owns all
 * perception, semantic memory, retrieval, and accessibility reasoning.
 */
export class InitialMoviePreparationService {
  async prepare(report: ProgressReporter, signal?: AbortSignal): Promise<void> {
    const milestones: PreparationMilestoneId[] = [
      'story-exploration', 'characters', 'relationships', 'scenes', 'objects',
      'accessibility-explanations', 'semantic-memory',
    ]
    for (const milestone of milestones) {
      if (signal?.aborted) throw new DOMException('Preparation cancelled', 'AbortError')
      report({ milestone, status: 'active' })
      await presentationPause()
      report({ milestone, status: 'complete' })
      await presentationPause()
    }

    report({ milestone: 'personalized-guidance', status: 'active' })
    await presentationPause()
    // The viewer's actual readiness gate is the backend presentation response.
    report({ milestone: 'personalized-guidance', status: 'complete', readyForPlayback: true })
  }
}

export const initialMoviePreparationService = new InitialMoviePreparationService()
