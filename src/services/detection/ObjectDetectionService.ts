import { isAiGatewayConfigured, openAIConfig } from '../../config/openai'
import type { CapturedVideoFrame } from '../ai/VideoFrameCaptureService'

export type DetectionBox = { x: number; y: number; width: number; height: number }

export type ObjectDetection = {
  id: string
  className: string
  confidence: number
  /** Percentages of the source frame. x/y are the centre of the box. */
  bbox: DetectionBox
}

export type ObjectDetectionResult = {
  available: boolean
  model?: string
  detections: ObjectDetection[]
}

export interface ObjectDetectionService {
  detect(frame: CapturedVideoFrame): Promise<ObjectDetectionResult>
}

/**
 * A transport adapter for any Hugging Face detector hosted behind MagiFab's API.
 * The browser never receives a Hugging Face token or a model credential.
 */
export class HuggingFaceObjectDetectionService implements ObjectDetectionService {
  async detect(frame: CapturedVideoFrame): Promise<ObjectDetectionResult> {
    if (!isAiGatewayConfigured()) return { available: false, detections: [] }
    try {
      const response = await fetch(`${openAIConfig.apiBaseUrl}/api/vision/detect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: frame.dataUrl, timestamp: frame.timestamp }),
      })
      if (!response.ok) return { available: false, detections: [] }
      const data = await response.json() as Partial<ObjectDetectionResult>
      if (!Array.isArray(data.detections)) return { available: false, detections: [] }
      return {
        available: true,
        model: typeof data.model === 'string' ? data.model : undefined,
        detections: data.detections.filter(isDetection),
      }
    } catch {
      return { available: false, detections: [] }
    }
  }
}

function isDetection(value: unknown): value is ObjectDetection {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  const box = item.bbox as Record<string, unknown> | undefined
  return typeof item.id === 'string' && typeof item.className === 'string'
    && typeof item.confidence === 'number' && Boolean(box)
    && ['x', 'y', 'width', 'height'].every((key) => typeof box?.[key] === 'number')
}

export const objectDetectionService: ObjectDetectionService = new HuggingFaceObjectDetectionService()
