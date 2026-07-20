import type { AccessibilityAnalyzer, NarrativeGraph, NarrativeProcessor, NarrativeProcessorInput, VisualAnalyzer } from './types'
import { DeterministicGraphBuilder } from './DeterministicGraphBuilder'
import { StoryBeatBuilder, type BeatBoundarySignal } from './StoryBeatBuilder'

export type PreprocessingDependencies = {
  narrative: NarrativeProcessor
  accessibility: AccessibilityAnalyzer
  visual?: VisualAnalyzer
}

export type BeatAwareNarrativeInput = NarrativeProcessorInput & { beatBoundarySignals?: Record<string, BeatBoundarySignal[]> }

export async function preprocessNarrative(input: BeatAwareNarrativeInput, dependencies: PreprocessingDependencies): Promise<NarrativeGraph> {
  const ungroundedGraph = await dependencies.narrative.createNarrativeGraph(input)
  const graph = input.visualScenes?.length ? new DeterministicGraphBuilder().applyVisualGrounding(ungroundedGraph, input.visualScenes) : ungroundedGraph
  const beatBuilder = new StoryBeatBuilder()
  const beatGraph = { ...graph, scenes: graph.scenes.map((scene) => ({ ...scene, storyBeats: scene.storyBeats?.length ? scene.storyBeats : beatBuilder.build(scene, input.beatBoundarySignals?.[scene.sceneId], input.visualScenes) })) }
  const scenes = await Promise.all(beatGraph.scenes.map(async (scene) => ({ ...scene, accessibility: await dependencies.accessibility.createAccessibilityGraph({ scene, graph: beatGraph }) })))
  const accessibleGraph = { ...beatGraph, scenes }
  return { ...accessibleGraph, preprocessingIntervals: beatBuilder.createPreprocessingIntervals(accessibleGraph) }
}
