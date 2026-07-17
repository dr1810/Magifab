import { isAiGatewayConfigured, openAIConfig } from '../../config/openai'
import type { MovieMediaSource, TranscriptSegment } from './types'

/** Delegates server-side transcript extraction for an imported movie. */
export class TranscriptExtractionService {
  /** Extracts speaker-aware transcript segments for later scene building. */
  public async extract(source: MovieMediaSource): Promise<TranscriptSegment[]> {
    if (!isAiGatewayConfigured()) throw new Error('Transcript extraction requires the configured MagiFab API gateway.')
    const response = await fetch(`${openAIConfig.apiBaseUrl}/api/movies/preprocess/transcript`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source }),
    })
    if (!response.ok) throw new Error('Transcript extraction request failed.')
    return response.json() as Promise<TranscriptSegment[]>
  }
}

export const transcriptExtractionService = new TranscriptExtractionService()
