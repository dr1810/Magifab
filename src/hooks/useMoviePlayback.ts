import { useEffect, useMemo, useState } from 'react'
import { getMovie, getScene } from '../services/movieService'
import type { MovieData, MovieId, SceneData } from '../types/movie'

export function useMoviePlayback(movieId: MovieId) {
  const [movie, setMovie] = useState<MovieData | null>(null)
  const [scene, setScene] = useState<SceneData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    setLoading(true)

    void getMovie(movieId).then((response) => {
      if (!mounted) return
      setMovie(response)
      setScene(response?.scenes[0] ?? null)
      setLoading(false)
    })

    return () => {
      mounted = false
    }
  }, [movieId])

  const updateScene = async (timestamp: number) => {
    const currentScene = await getScene(movieId, timestamp)
    setScene(currentScene)
    return currentScene
  }

  const totalDuration = useMemo(() => movie?.scenes.at(-1)?.timestamp ?? 0, [movie])

  return {
    movie,
    scene,
    loading,
    totalDuration,
    updateScene,
  }
}
