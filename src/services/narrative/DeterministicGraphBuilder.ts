import type { NarrativeGraph, VisualSceneData } from './types'

export class DeterministicGraphBuilder {
  applyVisualGrounding(graph: NarrativeGraph, visualScenes: VisualSceneData[]): NarrativeGraph {
    const visualByScene = new Map(visualScenes.map((scene) => [scene.sceneId, scene]))
    return {
      ...graph,
      scenes: graph.scenes.map((scene) => {
        const visual = visualByScene.get(scene.sceneId)
        if (!visual) return scene
        const visible = new Set(visual.visibleEntityIds)
        return {
          ...scene,
          visualGrounding: {
            visibleEntityIds: visual.visibleEntityIds,
            missingEntityIds: graph.characters.filter((character) => !visible.has(character.id)).map((character) => character.id),
            confidence: visual.confidence,
            evidence: Object.fromEntries(visual.visibleEntityIds.map((entityId) => [entityId, [`visual scene analysis: ${visual.visualContext}`]])),
            visibleObjects: visual.visibleObjects,
          },
          objects: visual.visibleObjects,
        }
      }),
    }
  }
}
