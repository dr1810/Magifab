import type { ObjectDetection } from '../detection/ObjectDetectionService'
import type { VisionUnderstanding } from '../vision/VisionUnderstandingService'
import type { SemanticMovieMemory, SemanticScene } from '../gpt/types'

export type SemanticMatch = {
  characterFound: boolean
  confidence: number
  character?: { id: string; name: string; role: string }
  detectionId?: string
  anchor?: ObjectDetection['bbox']
  reason: string
}

export interface SemanticMatchingService {
  match(input: { detections: ObjectDetection[]; understanding: VisionUnderstanding; memory: SemanticMovieMemory; scene: SemanticScene }): SemanticMatch
}

/** Matches only unambiguous detector labels to verified semantic aliases; it never asks a model to name someone. */
export class ConservativeSemanticMatchingService implements SemanticMatchingService {
  match({ detections, memory, scene }: Parameters<SemanticMatchingService['match']>[0]): SemanticMatch {
    const known = scene.visibleCharacters
      .filter((visible) => visible.confidence === 'known')
      .map((visible) => memory.characters.find((character) => character.id === visible.characterId))
      .filter((character): character is NonNullable<typeof character> => Boolean(character))

    const candidates = detections.flatMap((detection) => known
      .filter((character) => (character.aliases ?? []).some((alias) => alias.toLowerCase() === detection.className.toLowerCase()))
      .map((character) => ({ detection, character })))

    if (candidates.length !== 1 || candidates[0].detection.confidence < 0.8) {
      return { characterFound: false, confidence: candidates[0]?.detection.confidence ?? 0, reason: candidates.length ? 'The visual match is not confident enough.' : 'No verified visual character match exists for this frame.' }
    }
    const { detection, character } = candidates[0]
    return { characterFound: true, confidence: detection.confidence, character: { id: character.id, name: character.name, role: character.role }, detectionId: detection.id, anchor: detection.bbox, reason: 'A detector label matched one verified character alias.' }
  }
}

export const semanticMatchingService: SemanticMatchingService = new ConservativeSemanticMatchingService()
