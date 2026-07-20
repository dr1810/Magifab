import { movieById } from '../../movie-data/index'
import type { MovieId } from '../../types/movie'
import { graphFromMovieData } from './graphFactory'
import type { NarrativeGraph } from './types'

export interface NarrativeGraphStore { get(contentId: string): NarrativeGraph | null }

/** Development store. Swap this interface for a Supabase/Postgres store without touching the UI. */
export class LocalNarrativeGraphStore implements NarrativeGraphStore {
  private readonly graphs = new Map<string, NarrativeGraph>(Object.values(movieById).map((movie) => [movie.id, graphFromMovieData(movie)]))
  get(contentId: string) { return this.graphs.get(contentId) ?? null }
}

export const narrativeGraphStore = new LocalNarrativeGraphStore()
export function getMovieNarrativeGraph(movieId: MovieId) { return narrativeGraphStore.get(movieId) }
