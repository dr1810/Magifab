import type { CapturedVideoFrame } from '../ai/VideoFrameCaptureService'
import type { SceneData } from '../../types/movie'
import type { CompanionInterval, CompanionProvider } from './CompanionInterval'

export type MovieIntervalInput = {
  contentId: string
  intervalNumber: number
  start: number
  end: number
  frame: CapturedVideoFrame
  scene: SceneData | null
}

export class MovieProvider implements CompanionProvider<MovieIntervalInput> {
  createInterval(input: MovieIntervalInput): CompanionInterval {
    return {
      id: `${input.contentId}:interval:${input.intervalNumber}`,
      contentId: input.contentId,
      start: input.start,
      end: input.end,
      timestamp: input.frame.timestamp,
      image: input.frame.dataUrl,
      text: input.scene?.subtitle ?? '',
      metadata: { provider: 'movie', intervalNumber: input.intervalNumber, catalogSceneId: input.scene?.sceneId ?? null },
    }
  }
}
