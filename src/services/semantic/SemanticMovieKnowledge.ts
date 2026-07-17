import type { MovieData } from '../../types/movie'
import { movieAnalysisService } from '../gpt/MovieAnalysisService'
import { semanticMemoryService } from '../gpt/SemanticMemoryService'
import type { SemanticMovieMemory, SemanticScene, VerifiedSemanticDetection } from '../gpt/types'

/** Stable facade around the stored semantic movie representation. */
export class SemanticMovieKnowledge {
  load(movie: MovieData): SemanticMovieMemory {
    return movieAnalysisService.ensureMovieKnowledge(movie)
  }

  scene(movie: MovieData, timestamp: number): SemanticScene {
    return semanticMemoryService.getScene(this.load(movie), timestamp)
  }

  recordVerifiedObservation(movie: MovieData, sceneId: string, observation: VerifiedSemanticDetection): void {
    const memory = this.load(movie)
    const scene = memory.scenes.find((item) => item.sceneId === sceneId)
    if (!scene) return
    const alreadyStored = scene.knownDetections?.some((item) => item.detectionId === observation.detectionId && item.timestamp === observation.timestamp)
    if (alreadyStored) return
    scene.knownDetections = [...(scene.knownDetections ?? []), observation]
    semanticMemoryService.save(memory)
  }
}

export const semanticMovieKnowledge = new SemanticMovieKnowledge()
