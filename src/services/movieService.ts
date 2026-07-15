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

export async function getMovie(id: MovieId): Promise<MovieData | null> {
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
  return Promise.resolve(movieById[id] ?? null)
}

export async function getScene(movieId: MovieId, timestamp: number): Promise<SceneData | null> {
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
  const movie = movieById[movieId]
  if (!movie) {
    return Promise.resolve(null)
  }

  return Promise.resolve(getSceneAtTimestamp(movie, timestamp))
}
