import { useRef } from 'react'
import type { SceneState } from '../scene/SceneState'

export type StoryContext = {
  contextVersion: number
  storyBeatId: string | null
  validFrom: number
  validUntil: number
  currentTime: number
}

export class StoryContextObserver {
  private contextVersion = 0
  private storyBeatId: string | null = null

  observe(sceneState: SceneState | null, currentTime: number): StoryContext {
    const nextBeatId = sceneState?.sceneId ?? null
    if (nextBeatId !== this.storyBeatId) {
      this.storyBeatId = nextBeatId
      this.contextVersion += 1
    }
    return {
      contextVersion: this.contextVersion,
      storyBeatId: nextBeatId,
      validFrom: sceneState?.startTime ?? currentTime,
      validUntil: sceneState?.endTime ?? Number.POSITIVE_INFINITY,
      currentTime,
    }
  }
}

export function useStoryContextObserver(sceneState: SceneState | null, currentTime: number) {
  const observer = useRef(new StoryContextObserver())
  return observer.current.observe(sceneState, currentTime)
}
