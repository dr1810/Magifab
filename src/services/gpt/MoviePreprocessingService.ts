import { frameExtractionService } from './FrameExtractionService'
import { sceneBuilder } from './SceneBuilder'
import { sceneDetectionService } from './SceneDetectionService'
import { transcriptExtractionService } from './TranscriptExtractionService'
import type { MovieAnalysisInput, MoviePreprocessingResult } from './types'

/** Orchestrates the Movie Processing portion of the canonical import architecture. */
export class MoviePreprocessingService {
  /** Produces structured scenes from an imported movie before semantic GPT analysis begins. */
  public async preprocess(input: MovieAnalysisInput): Promise<MoviePreprocessingResult> {
    const [frames, transcript] = await Promise.all([
      frameExtractionService.extract(input.source),
      transcriptExtractionService.extract(input.source),
    ])
    const detectedScenes = await sceneDetectionService.detect(input.source, frames, transcript)
    return { movieId: input.movieId, source: input.source, scenes: sceneBuilder.build(detectedScenes, frames, transcript) }
  }
}

export const moviePreprocessingService = new MoviePreprocessingService()
