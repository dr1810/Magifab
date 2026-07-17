import { isAiGatewayConfigured, openAIConfig } from '../../config/openai'
import type { DetectedScene, ExtractedFrame, MovieMediaSource, TranscriptSegment } from './types'

/** Delegates server-side scene-boundary detection for an imported movie. */
export class SceneDetectionService {
  /** Detects scene ranges using source media, visual frames, and transcript cues. */
  public async detect(source: MovieMediaSource, frames: ExtractedFrame[], transcript: TranscriptSegment[]): Promise<DetectedScene[]> {
    if (!isAiGatewayConfigured()) throw new Error('Scene detection requires the configured MagiFab API gateway.')
    const response = await fetch(`${openAIConfig.apiBaseUrl}/api/movies/preprocess/scenes`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source, frames, transcript }),
    })
    if (!response.ok) throw new Error('Scene detection request failed.')
    return response.json() as Promise<DetectedScene[]>
  }
}

export const sceneDetectionService = new SceneDetectionService()
