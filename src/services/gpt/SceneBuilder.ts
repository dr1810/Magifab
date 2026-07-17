import type { DetectedScene, ExtractedFrame, StructuredSceneRepresentation, TranscriptSegment } from './types'

/** Combines preprocessing outputs into the GPT-ready structured scene representation. */
export class SceneBuilder {
  /** Groups frames and transcript segments into their detected timestamp ranges. */
  public build(scenes: DetectedScene[], frames: ExtractedFrame[], transcript: TranscriptSegment[]): StructuredSceneRepresentation[] {
    return scenes.map((scene) => ({
      sceneId: scene.id,
      range: scene.range,
      frames: frames.filter((frame) => frame.timestamp >= scene.range.start && frame.timestamp < scene.range.end),
      transcript: transcript.filter((segment) => segment.start < scene.range.end && segment.end >= scene.range.start),
    }))
  }
}

export const sceneBuilder = new SceneBuilder()
