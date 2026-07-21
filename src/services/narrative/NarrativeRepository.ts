import { movieById } from '../../movie-data/index'
import type { MovieData, MovieId } from '../../types/movie'
import bigBuckNarrativeJson from '../../data/movies/big-buck-bunny/narrative.json'
import bigBuckAccessibilityJson from '../../data/movies/big-buck-bunny/accessibility.json'
import exampleBookNarrativeJson from '../../data/books/example-book/narrative.json'
import exampleBookAccessibilityJson from '../../data/books/example-book/accessibility.json'
import { graphFromMovieData } from './graphFactory'
import { StoryBeatBuilder } from './StoryBeatBuilder'
import type { AccessibilityGraph, NarrativeGraph } from './types'

export interface NarrativeGraphStore { get(contentId: string): NarrativeGraph | null }

export class LocalNarrativeGraphStore implements NarrativeGraphStore {
  private readonly graphs = new Map<string, NarrativeGraph>([
    ['bigBuckBunny', withSubScenes(applyAccessibility(bigBuckNarrativeJson as unknown as NarrativeGraph, bigBuckAccessibilityJson.scenes as unknown as Record<string, AccessibilityGraph>))],
    ['example-book', withSubScenes(applyAccessibility(exampleBookNarrativeJson as unknown as NarrativeGraph, exampleBookAccessibilityJson.scenes as unknown as Record<string, AccessibilityGraph>))],
    ...Object.values(movieById).filter((movie): movie is MovieData => movie !== undefined && movie.id !== 'bigBuckBunny').map((movie) => [movie.id, withSubScenes(graphFromMovieData(movie))] as const),
  ])
  get(contentId: string) { return this.graphs.get(contentId) ?? null }
}

export const narrativeGraphStore = new LocalNarrativeGraphStore()
export function getMovieNarrativeGraph(movieId: MovieId) { return narrativeGraphStore.get(movieId) }
export function getContentNarrativeGraph(contentId: string) { return narrativeGraphStore.get(contentId) }

function applyAccessibility(graph: NarrativeGraph, scenes: Record<string, AccessibilityGraph>): NarrativeGraph {
  return { ...graph, scenes: graph.scenes.map((scene) => ({ ...scene, accessibility: scenes[scene.sceneId] ?? scene.accessibility })) }
}

function withSubScenes(graph: NarrativeGraph): NarrativeGraph {
  const beatBuilder = new StoryBeatBuilder()
  return {
    ...graph,
    scenes: graph.scenes.map((scene) => ({
      ...scene,
      storyBeats: scene.storyBeats?.length
        ? beatBuilder.subdivide(scene.storyBeats)
        : beatBuilder.build(scene),
    })),
  }
}
