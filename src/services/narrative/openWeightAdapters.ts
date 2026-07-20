import type { AccessibilityAnalyzer, AccessibilityAnalyzerInput, AccessibilityGraph, NarrativeGraph, NarrativeProcessor, NarrativeProcessorInput, VisualAnalyzer, VisualSceneData } from './types'

export type OpenWeightModel = 'qwen3-vl' | 'internvl' | 'deepseek-v3' | 'qwen-instruct'
export type OfflineModelExecutor = <Input, Output>(request: { model: OpenWeightModel; task: string; input: Input }) => Promise<Output>

export class OpenWeightVisualAnalyzer implements VisualAnalyzer {
  constructor(private readonly execute: OfflineModelExecutor, private readonly model: OpenWeightModel = 'qwen3-vl') {}
  analyzeFrames(input: Parameters<VisualAnalyzer['analyzeFrames']>[0]) {
    return this.execute<typeof input, VisualSceneData[]>({ model: this.model, task: 'visual-scene-analysis', input })
  }
}

export class OpenWeightNarrativeProcessor implements NarrativeProcessor {
  constructor(private readonly execute: OfflineModelExecutor, private readonly model: OpenWeightModel = 'deepseek-v3') {}
  createNarrativeGraph(input: NarrativeProcessorInput) {
    return this.execute<NarrativeProcessorInput, NarrativeGraph>({ model: this.model, task: 'narrative-graph-extraction', input })
  }
}

export class OpenWeightAccessibilityAnalyzer implements AccessibilityAnalyzer {
  constructor(private readonly execute: OfflineModelExecutor, private readonly model: OpenWeightModel = 'qwen-instruct') {}
  createAccessibilityGraph(input: AccessibilityAnalyzerInput) {
    return this.execute<AccessibilityAnalyzerInput, AccessibilityGraph>({ model: this.model, task: 'accessibility-graph-analysis', input })
  }
}
