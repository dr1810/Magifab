import type { AccessibilityAnalyzer, NarrativeGraph, NarrativeProcessor, NarrativeProcessorInput, VisionAnalyzer } from './types'

export type PreprocessingDependencies = {
  narrative: NarrativeProcessor
  accessibility: AccessibilityAnalyzer
  vision?: VisionAnalyzer
}

export async function preprocessNarrative(input: NarrativeProcessorInput, dependencies: PreprocessingDependencies): Promise<NarrativeGraph> {
  const graph = await dependencies.narrative.analyzeContent(input)
  const scenes = await Promise.all(graph.scenes.map(async (scene) => ({ ...scene, accessibility: await dependencies.accessibility.analyzeScene(scene, graph) })))
  return { ...graph, scenes }
}
