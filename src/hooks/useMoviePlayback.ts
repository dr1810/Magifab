import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getMovie, getScene } from '../services/movieService'
import { moviePreprocessingBackendService } from '../services/backend/MoviePreprocessingBackendService'
import type { MovieData, MovieId, SceneData } from '../types/movie'
import type { SceneState } from '../services/scene/SceneState'

export function useMoviePlayback(movieId: MovieId) {
  const [movie, setMovie] = useState<MovieData | null>(null)
  const [scene, setScene] = useState<SceneData | null>(null)
  const [storedSceneState, setStoredSceneState] = useState<SceneState | null>(null)
  const [loading, setLoading] = useState(true)
  const sceneRef = useRef<SceneData | null>(null)
  const sceneTimerRef = useRef<number | null>(null)
  const sceneRequestIdRef = useRef(0)
  const movieRequestIdRef = useRef(0)
  const movieControllerRef = useRef<AbortController | null>(null)
  const sceneControllerRef = useRef<AbortController | null>(null)
  const pendingTimestampRef = useRef(0)

  useEffect(() => {
    const requestId = ++movieRequestIdRef.current
    movieControllerRef.current?.abort()
    sceneControllerRef.current?.abort()
    const controller = new AbortController()
    movieControllerRef.current = controller
    setLoading(true)
    setMovie(null)
    setScene(null)
    setStoredSceneState(null)
    sceneRef.current = null
    pendingTimestampRef.current = 0

    void getMovie(movieId, controller.signal).then((response) => {
      if (controller.signal.aborted || requestId !== movieRequestIdRef.current) return
      setMovie(response)
      setScene(response?.scenes[0] ?? null)
      sceneRef.current = response?.scenes[0] ?? null
      setLoading(false)
    }).catch((error: unknown) => {
      if (controller.signal.aborted || requestId !== movieRequestIdRef.current) return
      console.warn('[MagiFab] movie load failed', error)
      setLoading(false)
    })

    return () => {
      controller.abort()
    }
  }, [movieId])

  useEffect(() => () => {
    if (sceneTimerRef.current !== null) window.clearTimeout(sceneTimerRef.current)
    sceneControllerRef.current?.abort()
    sceneRequestIdRef.current += 1
  }, [movieId])

  useEffect(() => {
    if (movie?.source !== 'backend' || movie.processingStatus === 'completed' || movie.processingStatus === 'partial' || movie.processingStatus === 'failed') return
    let cancelled = false
    const refresh = async () => {
      try {
        await moviePreprocessingBackendService.status(movieId)
        const nextMovie = await getMovie(movieId)
        if (!cancelled && nextMovie) setMovie(nextMovie)
      } catch (error) {
        if (!cancelled) console.warn('[MagiFab] movie preprocessing status failed', error)
      }
    }
    const timer = window.setInterval(() => { void refresh() }, 3_000)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [movie?.processingStatus, movie?.source, movieId])

  const updateScene = useCallback((timestamp: number, immediate = false) => {
    pendingTimestampRef.current = timestamp
    const requestId = ++sceneRequestIdRef.current
    const resolveScene = (timestampToResolve: number, resolutionRequestId: number) => {
      sceneControllerRef.current?.abort()
      const controller = new AbortController()
      sceneControllerRef.current = controller
      void getScene(movieId, timestampToResolve, controller.signal).then((next) => {
        if (controller.signal.aborted) return
        if (resolutionRequestId !== sceneRequestIdRef.current || !next || next.scene.sceneId === sceneRef.current?.sceneId) return
        sceneRef.current = next.scene
        setScene(next.scene)
        setStoredSceneState(next.sceneState)
      }).catch((error: unknown) => {
        if (!controller.signal.aborted) console.warn('[MagiFab] scene lookup failed', error)
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

  useEffect(() => {
    if (movie?.source === 'backend' && movie.processingStatus === 'completed' && !storedSceneState) {
      updateScene(pendingTimestampRef.current, true)
    }
  }, [movie?.processingStatus, movie?.source, storedSceneState, updateScene])

  const totalDuration = useMemo(() => movie?.scenes.at(-1)?.timestamp ?? 0, [movie])

  return {
    movie,
    scene,
    storedSceneState,
    loading,
    totalDuration,
    updateScene,
  }
}
