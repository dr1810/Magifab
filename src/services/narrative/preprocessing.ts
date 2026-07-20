import type { AccessibilityAnalyzer, NarrativeGraph, NarrativeProcessor, NarrativeProcessorInput, VisualAnalyzer } from './types'
import { DeterministicGraphBuilder } from './DeterministicGraphBuilder'

export type PreprocessingDependencies = {
  narrative: NarrativeProcessor
  accessibility: AccessibilityAnalyzer
  visual?: VisualAnalyzer
}

export async function preprocessNarrative(input: NarrativeProcessorInput, dependencies: PreprocessingDependencies): Promise<NarrativeGraph> {
  const ungroundedGraph = await dependencies.narrative.createNarrativeGraph(input)
  const graph = input.visualScenes?.length ? new DeterministicGraphBuilder().applyVisualGrounding(ungroundedGraph, input.visualScenes) : ungroundedGraph
  const scenes = await Promise.all(graph.scenes.map(async (scene) => ({ ...scene, accessibility: await dependencies.accessibility.createAccessibilityGraph({ scene, graph }) })))
  return { ...graph, scenes }
}
