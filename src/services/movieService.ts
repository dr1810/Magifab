import { demoMovies, getSceneAtTimestamp, movieById } from '../movie-data/index'
import type { MovieData, MovieId, SceneData } from '../types/movie'

export async function getMovies(): Promise<MovieData[]> {
  // ===============================
  // BACKEND INTEGRATION POINT
  // ===============================
  // Replace this mock data with API response
  // Endpoint expected: GET /api/movies
  // Request: no body
  // Expected response:
  // {
  //   movies: MovieData[]
  // }
  return Promise.resolve(demoMovies)
}

export async function getMovie(id: MovieId, signal?: AbortSignal): Promise<MovieData | null> {
  // ===============================
  // BACKEND INTEGRATION POINT
  // ===============================
  // Replace this mock data with API response
  // Endpoint expected: GET /api/movies/:id
  // Request: path param id
  // Expected response:
  // {
  //   movie: MovieData | null
  // }
  if (signal?.aborted) throw new DOMException('Movie request cancelled', 'AbortError')
  return movieById[id] ?? null
}

export async function getScene(movieId: MovieId, timestamp: number, signal?: AbortSignal): Promise<SceneData | null> {
  // ===============================
  // BACKEND INTEGRATION POINT
  // ===============================
  // Replace this mock data with API response
  // Endpoint expected: GET /api/movies/:id/scene?timestamp=:seconds
  // Request: movieId + timestamp query
  // Expected response:
  // {
  //    sceneId,
  //    prompts,
  //    explanations,
  //    diagrams,
  //    companionPosition,
  //    subtitles
  // }
  if (signal?.aborted) throw new DOMException('Scene request cancelled', 'AbortError')
  const movie = movieById[movieId]
  if (!movie) {
    return null
  }

  return getSceneAtTimestamp(movie, timestamp)
}
