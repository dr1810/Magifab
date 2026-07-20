import type { NarrativeCharacter, NarrativeScene } from './types'

export type GroundedSceneEntities = {
  visible: NarrativeCharacter[]
  missing: string[]
  rejected: Array<{ entityId: string; reason: 'missing_visual_evidence' | 'not_available_in_timeline' | 'below_confidence_threshold' }>
}

export class VisualGroundingResolver {
  constructor(private readonly entities: NarrativeCharacter[]) {}

  resolve(scene: NarrativeScene): GroundedSceneEntities {
    const visible: NarrativeCharacter[] = []
    const rejected: GroundedSceneEntities['rejected'] = []
    for (const entity of this.entities) {
      const confidence = scene.visualGrounding.confidence[entity.id] ?? 0
      const inTimeline = scene.startTime >= entity.firstAppearance && (entity.lastAppearance === undefined || scene.startTime <= entity.lastAppearance)
      if (!inTimeline) { rejected.push({ entityId: entity.id, reason: 'not_available_in_timeline' }); continue }
      if (!scene.visualGrounding.visibleEntityIds.includes(entity.id)) { rejected.push({ entityId: entity.id, reason: 'missing_visual_evidence' }); continue }
      if (confidence < entity.confidenceThreshold) { rejected.push({ entityId: entity.id, reason: 'below_confidence_threshold' }); continue }
      visible.push(entity)
    }
    return { visible, missing: scene.visualGrounding.missingEntityIds, rejected }
  }
}
