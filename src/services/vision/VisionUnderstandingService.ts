import { isAiGatewayConfigured, openAIConfig } from '../../config/openai'
import type { CapturedVideoFrame } from '../ai/VideoFrameCaptureService'
import type { ObjectDetection } from '../detection/ObjectDetectionService'

export type VisionUnderstanding = {
  available: boolean
  model?: string
  scene: string
  actions: string[]
  emotions: string[]
  interactions: string[]
  context: string[]
}

export interface VisionUnderstandingService {
  understand(frame: CapturedVideoFrame, detections: ObjectDetection[]): Promise<VisionUnderstanding>
}

/** Backend adapter for a Hugging Face VLM (Gemma or another compatible model). */
export class HuggingFaceVisionUnderstandingService implements VisionUnderstandingService {
  async understand(frame: CapturedVideoFrame, detections: ObjectDetection[]): Promise<VisionUnderstanding> {
    if (!isAiGatewayConfigured()) return unavailableUnderstanding()
    try {
      const response = await fetch(`${openAIConfig.apiBaseUrl}/api/vision/understand`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: frame.dataUrl, timestamp: frame.timestamp, detections }),
      })
      if (!response.ok) return unavailableUnderstanding()
      const data = await response.json() as Partial<VisionUnderstanding>
      if (typeof data.scene !== 'string') return unavailableUnderstanding()
      return {
        available: true, model: typeof data.model === 'string' ? data.model : undefined,
        scene: data.scene, actions: strings(data.actions), emotions: strings(data.emotions),
        interactions: strings(data.interactions), context: strings(data.context),
      }
    } catch {
      return unavailableUnderstanding()
    }
  }
}

const strings = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
export const unavailableUnderstanding = (): VisionUnderstanding => ({ available: false, scene: '', actions: [], emotions: [], interactions: [], context: [] })
export const visionUnderstandingService: VisionUnderstandingService = new HuggingFaceVisionUnderstandingService()
