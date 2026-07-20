import type { NarrativeGraph, NarrativeScene, PreprocessingInterval, StoryBeat, StoryBeatPhase, VisualSceneData } from './types'

export type BeatBoundarySignal = { timestamp: number; kind: 'speaker_change' | 'camera_change' | 'emotion_shift' | 'location_change' | 'combat_start' | 'combat_end' | 'relationship_change' | 'object_introduced' }

export class StoryBeatBuilder {
  build(scene: NarrativeScene, signals: BeatBoundarySignal[] = [], visualScenes: VisualSceneData[] = []): StoryBeat[] {
    const boundaries = [scene.startTime, ...signals.map((signal) => signal.timestamp).filter((timestamp) => timestamp > scene.startTime && (scene.endTime === null || timestamp < scene.endTime)), scene.endTime].filter((timestamp): timestamp is number => timestamp !== null).sort((left, right) => left - right)
    if (!boundaries.length) return [fallbackBeat(scene)]
    return boundaries.slice(0, -1).map((startTime, index) => {
      const endTime = boundaries[index + 1]
      const visual = visualScenes.find((item) => item.startTime <= startTime && item.endTime >= startTime)
      return {
        ...fallbackBeat(scene, `${scene.sceneId}:beat:${index + 1}`, startTime, endTime),
        phase: phaseFromSignals(signals.filter((signal) => signal.timestamp <= startTime)),
        visualGrounding: visual ? {
          visibleEntityIds: visual.visibleEntityIds,
          missingEntityIds: scene.visualGrounding.missingEntityIds,
          confidence: visual.confidence,
          evidence: scene.visualGrounding.evidence,
          visibleObjects: visual.visibleObjects,
        } : scene.visualGrounding,
        visibleEntityIds: visual?.visibleEntityIds ?? scene.visualGrounding.visibleEntityIds,
        objects: visual?.visibleObjects ?? scene.objects,
      }
    })
  }

  createPreprocessingIntervals(graph: NarrativeGraph, intervalSeconds = 30): PreprocessingInterval[] {
    const beats = graph.scenes.flatMap((scene) => scene.storyBeats?.length ? scene.storyBeats : [fallbackBeat(scene)])
    const duration = Math.max(0, ...beats.map((beat) => beat.endTime ?? beat.startTime + intervalSeconds))
    return Array.from({ length: Math.ceil(duration / intervalSeconds) }, (_, intervalNumber) => {
      const startTime = intervalNumber * intervalSeconds
      const endTime = startTime + intervalSeconds
      return {
        id: `${graph.movie.id}:interval:${intervalNumber}`,
        startTime,
        endTime,
        storyBeatIds: beats.filter((beat) => beat.startTime < endTime && (beat.endTime === null || beat.endTime > startTime)).map((beat) => beat.id),
      }
    })
  }
}

export function fallbackBeat(scene: NarrativeScene, id = `${scene.sceneId}:beat:1`, startTime = scene.startTime, endTime = scene.endTime): StoryBeat {
  return {
    id, startTime, endTime, phase: 'setup', summary: scene.summary, visibleEntityIds: scene.visualGrounding.visibleEntityIds,
    relationships: scene.relationships, emotions: scene.emotions, objects: scene.objects, causeEffect: scene.causeEffect,
    memory: scene.memoryCheckpoint, promptCandidates: scene.accessibility.prompts,
    drawerState: { conversationSummary: scene.conversationSummary, timelinePosition: scene.timelinePosition, support: scene.accessibility.support },
    confidence: 1, visualGrounding: scene.visualGrounding,
  }
}

function phaseFromSignals(signals: BeatBoundarySignal[]): StoryBeatPhase {
  const latest = signals.at(-1)?.kind
  if (latest === 'combat_start') return 'climax'
  if (latest === 'combat_end') return 'resolution'
  if (latest === 'relationship_change' || latest === 'emotion_shift') return 'rising_action'
  return 'setup'
}
