import { bigBuckBunnyData } from './bigBuckBunny'
import { spriteFrightData } from './spriteFright'
import type { MovieData, MovieId, SceneData } from '../types/movie'

export const demoMovies: MovieData[] = [bigBuckBunnyData, spriteFrightData]

export const movieById: Partial<Record<MovieId, MovieData>> = {
  bigBuckBunny: bigBuckBunnyData,
  spriteFright: spriteFrightData,
}

export function getSceneAtTimestamp(movie: MovieData, timestamp: number): SceneData {
  const sorted = [...movie.scenes].sort((a, b) => a.timestamp - b.timestamp)
  const match = sorted.filter((scene) => scene.timestamp <= timestamp).at(-1)
  return match ?? sorted[0]
}
