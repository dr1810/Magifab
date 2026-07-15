import { findingNemoData } from './findingNemo'
import { insideOutData } from './insideOut'
import type { MovieData, MovieId, SceneData } from '../types/movie'

export const demoMovies: MovieData[] = [findingNemoData, insideOutData]

export const movieById: Record<MovieId, MovieData> = {
  findingNemo: findingNemoData,
  insideOut: insideOutData,
}

export function getSceneAtTimestamp(movie: MovieData, timestamp: number): SceneData {
  const sorted = [...movie.scenes].sort((a, b) => a.timestamp - b.timestamp)
  const match = sorted.filter((scene) => scene.timestamp <= timestamp).at(-1)
  return match ?? sorted[0]
}
