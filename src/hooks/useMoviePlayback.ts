import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getMovie, getScene } from '../services/movieService'
import { movieAnalysisService } from '../services/gpt/MovieAnalysisService'
import type { MovieData, MovieId, SceneData } from '../types/movie'

export function useMoviePlayback(movieId: MovieId) {
  const [movie, setMovie] = useState<MovieData | null>(null)
  const [scene, setScene] = useState<SceneData | null>(null)
  const [loading, setLoading] = useState(true)
  const sceneRef = useRef<SceneData | null>(null)
  const sceneTimerRef = useRef<number | null>(null)
  const sceneRequestIdRef = useRef(0)
  const pendingTimestampRef = useRef(0)

  useEffect(() => {
    let mounted = true
    setLoading(true)

    void getMovie(movieId).then((response) => {
      if (!mounted) return
      if (response) movieAnalysisService.ensureMovieKnowledge(response)
      setMovie(response)
      setScene(response?.scenes[0] ?? null)
      sceneRef.current = response?.scenes[0] ?? null
      setLoading(false)
    })

    return () => {
      mounted = false
    }
  }, [movieId])

  useEffect(() => () => {
    if (sceneTimerRef.current !== null) window.clearTimeout(sceneTimerRef.current)
    sceneRequestIdRef.current += 1
  }, [movieId])

  const updateScene = useCallback((timestamp: number, immediate = false) => {
    pendingTimestampRef.current = timestamp
    const requestId = ++sceneRequestIdRef.current
    const resolveScene = (timestampToResolve: number, resolutionRequestId: number) => {
      void getScene(movieId, timestampToResolve).then((nextScene) => {
        if (resolutionRequestId !== sceneRequestIdRef.current || !nextScene || nextScene.sceneId === sceneRef.current?.sceneId) return
        sceneRef.current = nextScene
        setScene(nextScene)
      })
    }

    if (immediate) {
      if (sceneTimerRef.current !== null) window.clearTimeout(sceneTimerRef.current)
      sceneTimerRef.current = null
      resolveScene(timestamp, requestId)
      return
    }

    // Coalesce frequent timeupdate/slider events into one lookup. A seeked event
    // bypasses this delay so the UI settles immediately at the final timestamp.
    if (sceneTimerRef.current !== null) return
    sceneTimerRef.current = window.setTimeout(() => {
      sceneTimerRef.current = null
      resolveScene(pendingTimestampRef.current, sceneRequestIdRef.current)
    }, 300)
  }, [movieId])

  const totalDuration = useMemo(() => movie?.scenes.at(-1)?.timestamp ?? 0, [movie])

  return {
    movie,
    scene,
    loading,
    totalDuration,
    updateScene,
  }
}
