import { isAiGatewayConfigured, openAIConfig } from '../../config/openai'
import type { ExtractedFrame, MovieMediaSource } from './types'

/** Delegates server-side representative-frame extraction for an imported movie. */
export class FrameExtractionService {
  /** Extracts timestamped frames without exposing media-processing work to the browser. */
  public async extract(source: MovieMediaSource): Promise<ExtractedFrame[]> {
    if (!isAiGatewayConfigured()) throw new Error('Frame extraction requires the configured MagiFab API gateway.')
    const response = await fetch(`${openAIConfig.apiBaseUrl}/api/movies/preprocess/frames`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source }),
    })
    if (!response.ok) throw new Error('Frame extraction request failed.')
    return response.json() as Promise<ExtractedFrame[]>
  }
}

export const frameExtractionService = new FrameExtractionService()
