import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { TopBar } from './components/TopBar'
import { MoviePlayer } from './components/MoviePlayer'
import { PromptPanel } from './components/PromptPanel'
import { VisualDrawer } from './components/VisualDrawer'
import { FloatingBubble, type PromptBubbleContent } from './components/FloatingBubble'
import { CompanionWidget } from './components/CompanionWidget'
import { useAccessibility } from './accessibility-context'
import { useMoviePlayback } from './hooks/useMoviePlayback'
import { useCompanionProfile } from './hooks/useCompanionProfile'
import { INTERVAL_SECONDS, type CapturedVideoFrame } from './services/ai/VideoFrameCaptureService'
import { companionBackendService, type IntervalState } from './services/backend/CompanionBackendService'
import { SceneStateStore } from './services/scene/SceneStateStore'
import { toSceneState, type SceneState } from './services/scene/SceneState'
import { captionPromptAnswer, createCaptionCompanionState } from './services/scene/captionCompanionState'
import { speakText, stopSpeech } from './services/speechService'
import { getPlaybackTimestamp, savePlaybackTimestamp } from './services/playbackSessionService'
import { getScene } from './services/movieService'
import type { MovieId, PromptQuestion, SceneData } from './types/movie'

type MovieViewerProps = {
  movie: MovieId
  onBack: () => void
  onOpenAccessibilitySettings?: () => void
}

const FRAME_CAPTURE_TIMEOUT_MS = 20_000
const METADATA_LOOKUP_TIMEOUT_MS = 5_000
const PREPARE_DIAGNOSTIC_TIMEOUT_MS = 45_000
const DIRECT_INTERVAL_ZERO_DIAGNOSTIC = false

class PreprocessingTimeoutError extends Error {
  constructor(stage: string, timeoutMs: number) {
    super(`${stage} timed out after ${timeoutMs}ms`)
    this.name = 'PreprocessingTimeoutError'
  }
}

function withPreprocessingTimeout<T>(stage: string, timeoutMs: number, operation: Promise<T>, abortController?: AbortController): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = window.setTimeout(() => {
      abortController?.abort()
      reject(new PreprocessingTimeoutError(stage, timeoutMs))
    }, timeoutMs)
    void operation.then(
      (value) => { window.clearTimeout(timer); resolve(value) },
      (error: unknown) => { window.clearTimeout(timer); reject(error) },
    )
  })
}

function validateIntervalSnapshot(snapshot: IntervalState, movieId: string, interval: number, start: number, end: number) {
  const metadata = snapshot.metadata
  const expectedId = `${movieId}:interval:${interval}`
  const hasExpectedBounds = Math.abs(metadata.start_time - start) < 0.001
    && metadata.end_time !== null
    && Math.abs(metadata.end_time - end) < 0.001
  if (metadata.movie_id !== movieId || metadata.interval_id !== expectedId || metadata.interval_number !== interval || !hasExpectedBounds) {
    throw new Error(`Prepared snapshot does not match interval ${interval}.`)
  }
}

export function MovieViewer({ movie, onBack, onOpenAccessibilitySettings = () => undefined }: MovieViewerProps) {
  const { movie: movieData, scene, loading, totalDuration, updateScene } = useMoviePlayback(movie)
  const { profile, loading: companionProfileLoading } = useCompanionProfile()
  const { settings } = useAccessibility()

  const [playing, setPlaying] = useState(false)
  const [muted, setMuted] = useState(false)
  const [volume, setVolume] = useState(72)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [promptOpen, setPromptOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [widgetOpen, setWidgetOpen] = useState(false)
  const [activeBubble, setActiveBubble] = useState<PromptBubbleContent | null>(null)
  const explanationRequestIdRef = useRef(0)
  const promptAbortControllerRef = useRef<AbortController | null>(null)
  const frameCaptureRef = useRef<((intervalStart: number, intervalEnd: number) => Promise<CapturedVideoFrame>) | null>(null)
  // The store is the sole source for every interval-scoped companion surface.
  const sceneStateStoreRef = useRef(new SceneStateStore())
  const [intervalStoreVersion, setIntervalStoreVersion] = useState(0)
  const [companionReady, setCompanionReady] = useState(false)
  const companionReadyRef = useRef(false)
  const preprocessingAbortControllersRef = useRef<Set<AbortController>>(new Set())
  const preparationEffectCountRef = useRef(0)
  const activeIntervalRef = useRef<number | null>(null)
  const currentPlaybackTimeRef = useRef(0)
  const preprocessingStartedRef = useRef(false)
  const preprocessingFailuresRef = useRef<Map<number, { stage: string; error: string }>>(new Map())
  const preprocessingRunIdRef = useRef(0)
  const durationRef = useRef(0)
  const latestPreparationInputsRef = useRef({ settings, profile })
  const [frameCaptureAvailable, setFrameCaptureAvailable] = useState(false)
  const isSeekingRef = useRef(false)
  const [assistantText, setAssistantText] = useState('Select a prompt to get a simple explanation for this scene.')
  const [sceneState, setSceneState] = useState<SceneState | null>(null)
  const [currentPlaybackInterval, setCurrentPlaybackInterval] = useState(0)
  const renderedIntervalIdRef = useRef<string | null>(null)
  const diagnosticResponseConsumedRef = useRef(false)
  latestPreparationInputsRef.current = { settings, profile }
  durationRef.current = duration
  const hasPlayableDuration = duration > 0
  const captionSceneState = useMemo(() => createCaptionCompanionState(movie, scene, scene?.timestamp ?? currentTime), [movie, scene])
  const activeSceneState = captionSceneState ?? sceneState

  useEffect(() => {
    if (import.meta.env.DEV) console.debug('[MagiFab companion] MovieViewer mounted', { movieId: movie })
    return () => { if (import.meta.env.DEV) console.debug('[MagiFab companion] MovieViewer unmounted', { movieId: movie }) }
  }, [movie])

  const backendPrompts = useMemo<PromptQuestion[]>(() => {
    return activeSceneState?.promptBubbles.map((prompt) => ({
      id: `backend:${prompt.id}`,
      label: prompt.label,
      question: prompt.question,
      explanation: '',
    })) ?? []
  }, [activeSceneState])
  const prompts = backendPrompts
  const [selectedPromptId, setSelectedPromptId] = useState<string>('')

  useEffect(() => {
    // PromptSet ownership is interval-scoped. Selecting an item in a new
    // interval must not carry an id from the previous PromptSet.
    setSelectedPromptId(prompts[0]?.id ?? '')
  }, [activeSceneState?.sceneId])

  useEffect(() => {
    if (!activeSceneState) return
    setPromptOpen(true)
    setDrawerOpen(true)
  }, [activeSceneState?.sceneId])

  const traceInterval = useCallback((event: 'INTERVAL_LOADED' | 'INTERVAL_RESTORED' | 'SEEK_TO_INTERVAL' | 'PROMPTSET_RESTORED' | 'VISUALDRAWER_RESTORED' | 'INTERVAL_PRELOADED', details: Record<string, unknown>) => {
    console.info(`[MagiFab] ${event}`, { movieId: movie, ...details })
  }, [movie])

  const tracePreprocessing = useCallback((event: 'QUEUE_CREATED' | 'FRAME_SELECTED' | 'FRAME_REJECTED' | 'INTERVAL_STARTED' | 'INTERVAL_READY' | 'INTERVAL_CACHE_UPDATED' | 'PROMPTS_UPDATED' | 'DRAWER_UPDATED' | 'UI_RENDERED' | 'PREPROCESS_COMPLETE' | 'FAILED_INTERVAL' | 'INTERVAL_GENERATED' | 'INTERVAL_DISPATCH' | 'INTERVAL_RESPONSE' | 'INTERVAL_FAILED' | 'PREPROCESSING_ABORTED' | 'PREPROCESSING_STAGE_TIMEOUT' | 'INTERVAL_SKIPPED' | 'PREPROCESSING_COMPLETE_WITH_FAILURES' | 'PLAYBACK_UNLOCKED', details: Record<string, unknown>) => {
    console.info(`[MagiFab] ${event}`, { movieId: movie, ...details })
  }, [movie])

  /**
   * The complete playback runtime: resolve timestamp -> retrieve snapshot ->
   * render that exact object. This function intentionally has no backend or
   * reasoning dependency.
   */
  const loadIntervalState = useCallback((timestamp: number, mode: 'playback' | 'seek' | 'restore' = 'playback', force = false) => {
    const interval = Math.floor(timestamp / INTERVAL_SECONDS)
    const previousInterval = activeIntervalRef.current
    if (mode === 'seek') traceInterval('SEEK_TO_INTERVAL', { timestamp, intervalNumber: interval })
    if (!force && previousInterval === interval) return

    activeIntervalRef.current = interval
    setCurrentPlaybackInterval(interval)
  }, [traceInterval])

  useEffect(() => sceneStateStoreRef.current.subscribe(() => setIntervalStoreVersion((version) => version + 1)), [])

  useEffect(() => {
    setSceneState(null)
    setCurrentPlaybackInterval(0)
    setCompanionReady(false)
    companionReadyRef.current = false
    setPlaying(false)
    renderedIntervalIdRef.current = null
    diagnosticResponseConsumedRef.current = false
    activeIntervalRef.current = null
    preprocessingFailuresRef.current.clear()
    preprocessingStartedRef.current = false
    preprocessingRunIdRef.current += 1
  }, [movie])

  // A store publication is the only path from preprocessing to rendering.
  // Resolve the exact active interval; never substitute a nearby snapshot.
  useEffect(() => {
    const nextSceneState = sceneStateStoreRef.current.getSnapshot(currentPlaybackInterval)
    if (!nextSceneState) return
    if (nextSceneState.sceneId === renderedIntervalIdRef.current) return
    renderedIntervalIdRef.current = nextSceneState.sceneId
    setSceneState(nextSceneState)
    setPromptOpen(true)
    setDrawerOpen(true)
    tracePreprocessing('UI_RENDERED', { interval: currentPlaybackInterval, intervalId: nextSceneState.sceneId, promptCount: nextSceneState.promptBubbles.length, drawerExists: true, reason: 'active_scene_state_read' })
  }, [currentPlaybackInterval, intervalStoreVersion, tracePreprocessing])

  useEffect(() => {
    const openingSceneState = sceneStateStoreRef.current.getSnapshot(0)
    if (!openingSceneState || companionReadyRef.current) return
    companionReadyRef.current = true
    setCompanionReady(true)
    tracePreprocessing('PLAYBACK_UNLOCKED', {
      reason: 'opening_interval_active',
      intervalId: openingSceneState.sceneId,
      promptCount: openingSceneState.promptBubbles.length,
    })
  }, [intervalStoreVersion, tracePreprocessing])

  /* The previous scheduler used an independent cache and is deliberately
   * disabled while the single IntervalManager scheduler owns runtime state.
  useEffect(() => {
    const effectCount = ++preparationEffectCountRef.current
    if (import.meta.env.DEV) console.debug('[MagiFab companion] prepare effect', { effectCount, movieId: movieData?.id, frameCaptureAvailable })
    // Superseded by the IntervalStore worker immediately below. Kept inert in
    // this change so the former complex scheduler can be deleted separately
    // without mixing a behavioral refactor with a presentation rewrite.
    if (preprocessingStartedRef.current || !movieData || !frameCaptureAvailable || !hasPlayableDuration) return
    const legacyPreprocessingDisabled = true
    if (legacyPreprocessingDisabled) return
    const capture = frameCaptureRef.current
    if (!capture) return
    preprocessingStartedRef.current = true
    const runId = ++preprocessingRunIdRef.current
    // `durationchange` is common with WebM sources. The preprocessing run
    // owns the duration it starts with, rather than being cancelled by a later
    // metadata refinement from the video element.
    const preprocessingDuration = durationRef.current
    const deadline = Date.now() + MOVIE_PREPROCESSING_TIMEOUT_MS
    let cancelled = false
    let completed = false
    const unlockPlayback = (reason: 'opening_interval_ready' | 'opening_interval_failed' | 'opening_snapshot_timeout' | 'queue_complete') => {
      if (companionReadyRef.current) return
      const initialInterval = intervalStatesRef.current.has(0)
        ? 0
        : [...intervalStatesRef.current.keys()].sort((left, right) => left - right)[0]
      if (initialInterval !== undefined) {
        loadIntervalState(initialInterval * INTERVAL_SECONDS, initialInterval > 0 ? 'restore' : 'playback', true)
      }
      companionReadyRef.current = true
      setCompanionReady(true)
      tracePreprocessing('PLAYBACK_UNLOCKED', {
        runId,
        reason,
        restoredInterval: initialInterval ?? null,
        preparedIntervals: intervalStatesRef.current.size,
        failedIntervals: preprocessingFailuresRef.current.size,
      })
    }
    const openingSnapshotTimer = window.setTimeout(() => {
      if (cancelled || companionReadyRef.current) return
      tracePreprocessing('PREPROCESSING_STAGE_TIMEOUT', {
        runId,
        stage: 'opening_snapshot',
        timeoutMs: OPENING_SNAPSHOT_TIMEOUT_MS,
        preparedIntervals: intervalStatesRef.current.size,
      })
      // This is diagnostic only. A slow first interval must not be discarded
      // or replaced by a synthetic snapshot. The bounded movie-level deadline
      // remains the fallback for an all-failure run.
    }, OPENING_SNAPSHOT_TIMEOUT_MS)
    const startTimer = window.setTimeout(() => {
      void (async () => {
        const intervalCount = Math.ceil(preprocessingDuration / INTERVAL_SECONDS)
        console.info('[MagiFab] Interval preprocessing started', { movieId: movieData.id, intervalCount })
        const queue = Array.from({ length: intervalCount }, (_, interval) => {
          const start = interval * INTERVAL_SECONDS
          return {
            interval,
            start,
            end: start + INTERVAL_SECONDS,
            sampleTime: start,
          }
        })
        tracePreprocessing('QUEUE_CREATED', {
          runId,
          intervalCount,
          duration: preprocessingDuration,
          frameCaptureAvailable,
          captureReady: Boolean(capture),
        })

        for (const task of queue) {
          if (Date.now() >= deadline) {
            const error = `movie_preprocessing timed out after ${MOVIE_PREPROCESSING_TIMEOUT_MS}ms`
            preprocessingFailuresRef.current.set(task.interval, { stage: 'movie_preprocessing', error })
            tracePreprocessing('PREPROCESSING_STAGE_TIMEOUT', { runId, stage: 'movie_preprocessing', timeoutMs: MOVIE_PREPROCESSING_TIMEOUT_MS, completedIntervals: intervalStatesRef.current.size, failedIntervals: preprocessingFailuresRef.current.size })
            break
          }
          if (cancelled) {
            tracePreprocessing('PREPROCESSING_ABORTED', { runId, stage: 'before_interval', interval: task.interval })
            return
          }
          tracePreprocessing('INTERVAL_GENERATED', { runId, ...task })
          tracePreprocessing('INTERVAL_STARTED', { runId, ...task })

          let frame: CapturedVideoFrame
          try {
            tracePreprocessing('INTERVAL_DISPATCH', { runId, interval: task.interval, stage: 'frame_capture', sampleTime: task.sampleTime })
            frame = await withPreprocessingTimeout('frame_capture', FRAME_CAPTURE_TIMEOUT_MS, capture(task.start, task.end))
            tracePreprocessing('INTERVAL_RESPONSE', { runId, interval: task.interval, stage: 'frame_capture', timestamp: frame.timestamp, width: frame.width, height: frame.height })
            tracePreprocessing('FRAME_SELECTED', { runId, interval: task.interval, intervalStart: task.start, intervalEnd: task.end, timestamp: frame.timestamp })
            if (cancelled) {
              tracePreprocessing('PREPROCESSING_ABORTED', { runId, stage: 'after_frame_capture', interval: task.interval })
              return
            }
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error)
            preprocessingFailuresRef.current.set(task.interval, { stage: 'frame_capture', error: message })
            if (error instanceof PreprocessingTimeoutError) tracePreprocessing('PREPROCESSING_STAGE_TIMEOUT', { runId, interval: task.interval, stage: 'frame_capture', timeoutMs: FRAME_CAPTURE_TIMEOUT_MS, error: message })
            tracePreprocessing('INTERVAL_FAILED', { runId, interval: task.interval, stage: 'frame_capture', error: message })
            tracePreprocessing('FRAME_REJECTED', { runId, interval: task.interval, intervalStart: task.start, intervalEnd: task.end, error: message })
            tracePreprocessing('FAILED_INTERVAL', { runId, interval: task.interval, stage: 'frame_capture', error: message })
            tracePreprocessing('INTERVAL_SKIPPED', { runId, interval: task.interval, reason: 'frame_capture_failed' })
            continue
          }

          let intervalScene: SceneData | null
          try {
            tracePreprocessing('INTERVAL_DISPATCH', { runId, interval: task.interval, stage: 'metadata_lookup', timestamp: task.start })
            intervalScene = await withPreprocessingTimeout('metadata_lookup', METADATA_LOOKUP_TIMEOUT_MS, getScene(movieData.id, task.start))
            tracePreprocessing('INTERVAL_RESPONSE', { runId, interval: task.interval, stage: 'metadata_lookup', catalogSceneId: intervalScene?.sceneId ?? null })
            if (cancelled) {
              tracePreprocessing('PREPROCESSING_ABORTED', { runId, stage: 'after_metadata_lookup', interval: task.interval })
              return
            }
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error)
            preprocessingFailuresRef.current.set(task.interval, { stage: 'metadata_lookup', error: message })
            if (error instanceof PreprocessingTimeoutError) tracePreprocessing('PREPROCESSING_STAGE_TIMEOUT', { runId, interval: task.interval, stage: 'metadata_lookup', timeoutMs: METADATA_LOOKUP_TIMEOUT_MS, error: message })
            tracePreprocessing('INTERVAL_FAILED', { runId, interval: task.interval, stage: 'metadata_lookup', error: message })
            tracePreprocessing('FAILED_INTERVAL', { runId, interval: task.interval, stage: 'metadata_lookup', error: message })
            tracePreprocessing('INTERVAL_SKIPPED', { runId, interval: task.interval, reason: 'metadata_lookup_failed' })
            continue
          }

          let prepareAbortController: AbortController | null = null
          let prepareRequest: Promise<IntervalState> | null = null
          let commitPreparedInterval: ((result: IntervalState, delivery: 'on_time' | 'late') => void) | null = null
          try {
            const inputs = latestPreparationInputsRef.current
            prepareAbortController = new AbortController()
            preprocessingAbortControllersRef.current.add(prepareAbortController)
            tracePreprocessing('INTERVAL_DISPATCH', { runId, interval: task.interval, stage: 'prepare', intervalId: `${movieData.id}:interval:${task.interval}` })
            prepareRequest = companionBackendService.prepareInterval({
              movieId: movieData.id,
              scene: intervalScene ?? scene,
              catalogScene: intervalScene,
              intervalNumber: task.interval,
              intervalStart: task.start,
              intervalEnd: task.end,
              frame,
              settings: inputs.settings,
              companion: inputs.profile,
              signal: prepareAbortController.signal,
            })
            commitPreparedInterval = (result: IntervalState, delivery: 'on_time' | 'late') => {
              if (cancelled) return
              intervalStatesRef.current.set(task.interval, { ...result, representativeFrame: frame })
              preprocessingFailuresRef.current.delete(task.interval)
              tracePreprocessing('INTERVAL_CACHE_UPDATED', { runId, interval: task.interval, intervalId: result.metadata.interval_id, cacheSize: intervalStatesRef.current.size, delivery })
              tracePreprocessing('PROMPTS_UPDATED', { runId, interval: task.interval, intervalId: result.metadata.interval_id, promptCount: result.prompts.prompt_bubbles.length, delivery })
              tracePreprocessing('DRAWER_UPDATED', { runId, interval: task.interval, intervalId: result.metadata.interval_id, delivery })
              tracePreprocessing('INTERVAL_READY', { runId, interval: task.interval, intervalId: result.metadata.interval_id, delivery })
              tracePreprocessing('INTERVAL_RESPONSE', { runId, interval: task.interval, stage: 'prepare', intervalId: result.metadata.interval_id, delivery })
              window.clearTimeout(openingSnapshotTimer)
              unlockPlayback('opening_interval_ready')
              const activeInterval = Math.floor(currentPlaybackTimeRef.current / INTERVAL_SECONDS)
              if (activeInterval === task.interval || !intervalState) {
                loadIntervalState(activeInterval === task.interval ? currentPlaybackTimeRef.current : task.start, 'restore', true)
                tracePreprocessing('UI_RENDERED', { runId, interval: task.interval, intervalId: result.metadata.interval_id, reason: `${delivery}_interval_cache_update` })
              }
            }
            // A bounded wait is only a scheduling decision. It must never
            // abort or discard a healthy backend response.
            const result = await withPreprocessingTimeout('prepare', PREPARE_INTERVAL_TIMEOUT_MS, prepareRequest)
            commitPreparedInterval(result, 'on_time')
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error)
            if (error instanceof PreprocessingTimeoutError) {
              // Continue the original request in the background. Its eventual
              // success uses the same authoritative cache-and-render commit.
              void prepareRequest?.then(
                (lateResult) => commitPreparedInterval?.(lateResult, 'late'),
                (lateError: unknown) => tracePreprocessing('FAILED_INTERVAL', { runId, interval: task.interval, stage: 'prepare_late_response', error: lateError instanceof Error ? lateError.message : String(lateError) }),
              )
            }
            preprocessingFailuresRef.current.set(task.interval, { stage: 'prepare', error: message })
            if (error instanceof PreprocessingTimeoutError) tracePreprocessing('PREPROCESSING_STAGE_TIMEOUT', { runId, interval: task.interval, stage: 'prepare', timeoutMs: PREPARE_INTERVAL_TIMEOUT_MS, error: message })
            tracePreprocessing('INTERVAL_FAILED', { runId, interval: task.interval, stage: 'prepare', error: message })
            tracePreprocessing('FAILED_INTERVAL', { runId, interval: task.interval, stage: 'prepare', error: message })
            tracePreprocessing('INTERVAL_SKIPPED', { runId, interval: task.interval, reason: 'prepare_failed' })
            continue
          } finally {
            if (prepareAbortController) preprocessingAbortControllersRef.current.delete(prepareAbortController)
          }
        }
        if (cancelled) {
          tracePreprocessing('PREPROCESSING_ABORTED', { runId, stage: 'before_completion' })
          return
        }
        const failures = [...preprocessingFailuresRef.current.entries()].map(([interval, failure]) => ({ interval, ...failure }))
        if (failures.length === 0) {
          try {
            tracePreprocessing('INTERVAL_DISPATCH', { runId, stage: 'preprocessing_completion', intervalCount })
            await withPreprocessingTimeout('preprocessing_completion', PREPROCESSING_COMPLETE_TIMEOUT_MS, companionBackendService.completeMoviePreprocessing(movieData.id, intervalCount))
            tracePreprocessing('INTERVAL_RESPONSE', { runId, stage: 'preprocessing_completion', intervalCount })
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error)
            if (error instanceof PreprocessingTimeoutError) tracePreprocessing('PREPROCESSING_STAGE_TIMEOUT', { runId, stage: 'preprocessing_completion', timeoutMs: PREPROCESSING_COMPLETE_TIMEOUT_MS, error: message })
            tracePreprocessing('INTERVAL_FAILED', { runId, stage: 'preprocessing_completion', error: message })
          }
        } else {
          tracePreprocessing('PREPROCESSING_COMPLETE_WITH_FAILURES', { runId, generatedIntervals: intervalStatesRef.current.size, failedIntervals: failures.length, failures })
        }
        const playbackInterval = intervalStatesRef.current.has(Math.floor(currentPlaybackTimeRef.current / INTERVAL_SECONDS))
          ? Math.floor(currentPlaybackTimeRef.current / INTERVAL_SECONDS)
          : [...intervalStatesRef.current.keys()].sort((left, right) => left - right)[0]
        loadIntervalState(
          playbackInterval === undefined ? currentPlaybackTimeRef.current : playbackInterval * INTERVAL_SECONDS,
          playbackInterval === undefined ? 'playback' : playbackInterval * INTERVAL_SECONDS > 0 ? 'restore' : 'playback',
          true,
        )
        unlockPlayback('queue_complete')
        completed = true
        tracePreprocessing('PREPROCESS_COMPLETE', { runId, intervalCount, preparedIntervals: intervalStatesRef.current.size, failedIntervals: failures.length })
        console.info('[MagiFab] Interval preprocessing complete', { movieId: movieData.id, intervalCount })
      })().catch((error: unknown) => {
        preprocessingStartedRef.current = false
        tracePreprocessing('INTERVAL_FAILED', { runId, stage: 'scheduler', error: error instanceof Error ? error.message : String(error) })
      })
    }, 0)
    return () => {
      window.clearTimeout(startTimer)
      window.clearTimeout(openingSnapshotTimer)
      cancelled = true
      preprocessingAbortControllersRef.current.forEach((controller) => controller.abort())
      preprocessingAbortControllersRef.current.clear()
      if (!completed) tracePreprocessing('PREPROCESSING_ABORTED', { runId, stage: 'effect_cleanup' })
    }
  }, [movieData?.id, hasPlayableDuration, frameCaptureAvailable, loadIntervalState, tracePreprocessing])
  */

  useEffect(() => {
    if (DIRECT_INTERVAL_ZERO_DIAGNOSTIC || !movieData || !frameCaptureAvailable || !hasPlayableDuration || preprocessingStartedRef.current) return
    const capture = frameCaptureRef.current
    if (!capture) return
    preprocessingStartedRef.current = true
    const runId = ++preprocessingRunIdRef.current
    const store = sceneStateStoreRef.current
    const intervalCount = store.reset(durationRef.current, INTERVAL_SECONDS)
    tracePreprocessing('QUEUE_CREATED', { runId, intervalCount, duration: durationRef.current, concurrency: 1, strategy: 'fifo' })
    let cancelled = false
    void store.start(async (task, transition) => {
      transition('CAPTURING')
      tracePreprocessing('INTERVAL_STARTED', { runId, interval: task.interval, start: task.start, end: task.end })
      const frame = await withPreprocessingTimeout('frame_capture', FRAME_CAPTURE_TIMEOUT_MS, capture(task.start, task.end))
      tracePreprocessing('FRAME_SELECTED', { runId, interval: task.interval, timestamp: frame.timestamp })
      const catalogScene = await withPreprocessingTimeout('metadata_lookup', METADATA_LOOKUP_TIMEOUT_MS, getScene(movieData.id, task.start))
      transition('PREPARING')
      const inputs = latestPreparationInputsRef.current
      const result = await companionBackendService.prepareInterval({ movieId: movieData.id, scene: catalogScene ?? scene, catalogScene, intervalNumber: task.interval, intervalStart: task.start, intervalEnd: task.end, frame, settings: inputs.settings, companion: inputs.profile })
      validateIntervalSnapshot(result, movieData.id, task.interval, task.start, task.end)
      tracePreprocessing('INTERVAL_CACHE_UPDATED', { runId, interval: task.interval, intervalId: result.metadata.interval_id })
      tracePreprocessing('PROMPTS_UPDATED', { runId, interval: task.interval, intervalId: result.metadata.interval_id, promptCount: result.prompts.prompt_bubbles.length })
      tracePreprocessing('DRAWER_UPDATED', { runId, interval: task.interval, intervalId: result.metadata.interval_id })
      tracePreprocessing('INTERVAL_READY', { runId, interval: task.interval, intervalId: result.metadata.interval_id })
      return { sceneState: toSceneState(result, catalogScene?.subtitle ?? scene?.subtitle ?? null), representativeFrame: frame }
    }).finally(() => { if (!cancelled) tracePreprocessing('PREPROCESS_COMPLETE', { runId, intervalCount, preparedIntervals: store.readyCount, failedIntervals: store.failedCount }) })
    return () => { cancelled = true; store.stop() }
  }, [movieData?.id, frameCaptureAvailable, hasPlayableDuration, loadIntervalState, tracePreprocessing])

  /* Diagnostic-only direct rendering is intentionally disabled: all UI state
   * must flow through IntervalManager. */
  /*
  useEffect(() => {
    if (!DIRECT_INTERVAL_ZERO_DIAGNOSTIC || !movieData || !frameCaptureAvailable || diagnosticResponseConsumedRef.current) return
    const capture = frameCaptureRef.current
    if (!capture) return
    diagnosticResponseConsumedRef.current = true
    let cancelled = false
    void (async () => {
      const frame = await withPreprocessingTimeout('diagnostic_frame_capture', FRAME_CAPTURE_TIMEOUT_MS, capture(0, INTERVAL_SECONDS))
      const catalogScene = await withPreprocessingTimeout('diagnostic_metadata_lookup', METADATA_LOOKUP_TIMEOUT_MS, getScene(movieData.id, 0))
      const inputs = latestPreparationInputsRef.current
      const result = await companionBackendService.prepareInterval({
        movieId: movieData.id, scene: catalogScene ?? scene, catalogScene,
        intervalNumber: 0, intervalStart: 0, intervalEnd: INTERVAL_SECONDS,
        frame, settings: inputs.settings, companion: inputs.profile,
      })
      if (cancelled) return
      console.info('[MagiFab] DIAGNOSTIC_INTERVAL_ZERO_DIRECT_RENDER', { interval: 0, intervalId: result.metadata.interval_id, promptCount: result.prompts.prompt_bubbles.length, drawerExists: Boolean(result.visualDrawer) })
      setIntervalState(result)
      setPromptOpen(true)
      setDrawerOpen(true)
    })().catch((error: unknown) => console.error('[MagiFab] DIAGNOSTIC_INTERVAL_ZERO_FAILED', error))
    return () => { cancelled = true }
  }, [movieData?.id, frameCaptureAvailable])
  */

  useEffect(() => {
    const savedTimestamp = getPlaybackTimestamp(movie)
    if (import.meta.env.DEV) console.debug('[MagiFab playback] viewer resume request', { movieId: movie, currentTimeBeforeResume: currentTime, savedTimestamp })
    setCurrentTime(savedTimestamp)
    currentPlaybackTimeRef.current = savedTimestamp
    if (savedTimestamp > 0) void updateScene(savedTimestamp)
    loadIntervalState(savedTimestamp, 'restore', true)
    setActiveBubble(null)
    setWidgetOpen(false)
  }, [loadIntervalState, movie, updateScene])

  useEffect(() => {
    if (movieData && hasPlayableDuration) setPlaying(true)
  }, [hasPlayableDuration, movieData])

  useEffect(() => {
    if (!movieData) return
    const timer = window.setTimeout(() => savePlaybackTimestamp(movie, currentTime, duration || totalDuration), 300)
    return () => window.clearTimeout(timer)
  }, [currentTime, duration, movie, movieData, totalDuration])

  const selectedPrompt = useMemo(
    () => prompts.find((prompt) => prompt.id === selectedPromptId) ?? prompts[0],
    [prompts, selectedPromptId],
  )

  const buildPromptBubble = useCallback((sceneData: SceneData | null, prompt: PromptQuestion, result: Awaited<ReturnType<typeof companionBackendService.respond>>): PromptBubbleContent => {
    const card = result.characters[0]
    const emotion = result.accessibilityHints.emotions[0]?.summary
    return {
      id: `${result.metadata.interval_id}:${prompt.id}:${result.metadata.knowledge_revision}`,
      question: prompt.question,
      title: card?.name ?? prompt.label,
      relationship: emotion ?? result.conversationContext.scene_explanation,
      explanation: result.prompts.prompt_answers[0]?.answer ?? result.conversationContext.scene_explanation,
      anchor: sceneData?.companionPosition ?? { x: 84, y: 74 },
      highlightTarget: false,
    }
  }, [])

  const selectPrompt = async (prompt: PromptQuestion) => {
    if (!movieData || isSeekingRef.current) return
    const localState = activeSceneState
    if (localState) {
      const answer = captionPromptAnswer(localState, prompt.question)
      setSelectedPromptId(prompt.id)
      setPromptOpen(false)
      setDrawerOpen(false)
      setWidgetOpen(false)
      setActiveBubble({ id: `${localState.sceneId}:${prompt.id}`, question: prompt.question, title: prompt.label, relationship: localState.emotions[0]?.summary ?? '', explanation: answer, anchor: scene?.companionPosition ?? { x: 84, y: 74 }, highlightTarget: false })
      setAssistantText(answer)
      if (settings.voiceAssistance || settings.readPrompts) void speakText({ text: answer, rate: settings.voiceSpeed, volume: Math.min(1, settings.voiceVolume / 100) })
      return
    }
    const promptIntervalId = sceneState?.sceneId
    setSelectedPromptId(prompt.id)
    setPromptOpen(false)
    setDrawerOpen(false)
    setWidgetOpen(false)
    setActiveBubble(null)

    promptAbortControllerRef.current?.abort()
    const abortController = new AbortController()
    promptAbortControllerRef.current = abortController
    const requestId = ++explanationRequestIdRef.current
    const loadingAnchor = scene?.companionPosition ?? { x: 84, y: 74 }
    setActiveBubble({ id: `${sceneState?.sceneId ?? 'interval'}:${prompt.id}:loading`, question: prompt.question, title: 'Preparing help', relationship: '', explanation: '', anchor: loadingAnchor, highlightTarget: false, loading: true })
    if (!sceneState) {
      setActiveBubble({ id: `interval:${prompt.id}:not-prepared`, question: prompt.question, title: 'Preparing this interval', relationship: '', explanation: 'Please wait a moment while this interval is prepared.', anchor: loadingAnchor, highlightTarget: false, loading: true })
      return
    }
    try {
      const result = await companionBackendService.respond({ movieId: movieData.id, scene, question: prompt.question, timestamp: currentTime, settings, companion: profile, signal: abortController.signal })
      if (
        requestId !== explanationRequestIdRef.current
        || isSeekingRef.current
        || activeIntervalRef.current !== sceneState?.interval
        || result.metadata.interval_id !== promptIntervalId
      ) return
      setActiveBubble(buildPromptBubble(scene, prompt, result))
      const answer = result.prompts.prompt_answers[0]?.answer ?? result.conversationContext.scene_explanation
      setAssistantText(answer)
      if (settings.voiceAssistance || settings.readPrompts) void speakText({ text: answer, rate: settings.voiceSpeed, volume: Math.min(1, settings.voiceVolume / 100) })
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      if (requestId !== explanationRequestIdRef.current || isSeekingRef.current) return
      const message = error instanceof Error ? error.message : 'The companion is unavailable. Please try again.'
      setActiveBubble({ id: `interval:${prompt.id}:request-error`, question: prompt.question, title: 'Companion unavailable', relationship: '', explanation: message, anchor: loadingAnchor, highlightTarget: false })
      setAssistantText(message)
    }
  }
  const openPromptPanel = () => {
    setDrawerOpen(false)
    setPromptOpen(true)
  }
  const togglePromptPanel = () => {
    setDrawerOpen(false)
    setPromptOpen((open) => !open)
  }
  const openVisualDrawer = () => {
    setPromptOpen(false)
    setDrawerOpen(true)
  }
  const closeBubbles = () => {
    explanationRequestIdRef.current += 1
    promptAbortControllerRef.current?.abort()
    setActiveBubble(null)
    setWidgetOpen(false)
    setPromptOpen(false)
    void stopSpeech()
  }

  const handleSeeking = useCallback(() => {
    isSeekingRef.current = true
    explanationRequestIdRef.current += 1
    promptAbortControllerRef.current?.abort()
    setActiveBubble(null)
    setWidgetOpen(false)
    void stopSpeech()
  }, [])

  const applyPlaybackTime = useCallback((timestamp: number) => {
    if (DIRECT_INTERVAL_ZERO_DIAGNOSTIC) return
    currentPlaybackTimeRef.current = timestamp
    setCurrentTime(timestamp)
    // Scene metadata only drives native captions and the bubble anchor. It is
    // not companion reasoning; every companion surface reads IntervalState.
    void updateScene(timestamp)
    loadIntervalState(timestamp)
  }, [loadIntervalState, updateScene])

  const seekToPlaybackTime = useCallback((timestamp: number) => {
    if (DIRECT_INTERVAL_ZERO_DIAGNOSTIC) return
    currentPlaybackTimeRef.current = timestamp
    setCurrentTime(timestamp)
    void updateScene(timestamp, true)
    loadIntervalState(timestamp, 'seek', true)
  }, [loadIntervalState, updateScene])

  const handleFrameCaptureReady = useCallback((capture: ((intervalStart: number, intervalEnd: number) => Promise<CapturedVideoFrame>) | null) => {
    frameCaptureRef.current = capture
    setFrameCaptureAvailable(Boolean(capture))
  }, [])

  const openCompanionFromBubble = useCallback(() => {
    setWidgetOpen(true)
  }, [])

  const closePromptBubble = useCallback(() => {
    explanationRequestIdRef.current += 1
    promptAbortControllerRef.current?.abort()
    setActiveBubble(null)
  }, [])

  if (loading || !movieData) return <div className="movie-experience viewer-page" aria-busy="true" />

  return (
    <main className="movie-experience viewer-page playback-ready">
      <TopBar
        movie={movieData}
        onBack={() => { savePlaybackTimestamp(movie, currentTime, duration || totalDuration); onBack() }}
        onOpenPrompts={openPromptPanel}
        onOpenDrawer={openVisualDrawer}
      />

      <div className="viewer-layout" style={{ position: 'relative' }}>
        <MoviePlayer
          movie={movieData}
          scene={scene}
          subtitle={sceneState?.subtitle ?? scene?.subtitle ?? ''}
          playing={playing}
          muted={muted}
          volume={volume}
          currentTime={currentTime}
          totalTime={duration || totalDuration}
          onPlayToggle={() => setPlaying((value) => !value)}
          onMuteToggle={() => setMuted((value) => !value)}
          onVolumeChange={setVolume}
          onSeek={(next) => {
            seekToPlaybackTime(next)
          }}
          onTimeChange={(next) => {
            applyPlaybackTime(next)
          }}
          onDurationChange={setDuration}
          onSeeking={handleSeeking}
          onSeekComplete={(timestamp) => {
            if (DIRECT_INTERVAL_ZERO_DIAGNOSTIC) return
            isSeekingRef.current = false
            currentPlaybackTimeRef.current = timestamp
            setCurrentTime(timestamp)
            updateScene(timestamp, true)
            loadIntervalState(timestamp, 'seek')
          }}
          onVideoFrameCaptureReady={handleFrameCaptureReady}
          promptOpen={promptOpen}
          onTogglePromptPanel={togglePromptPanel}
          onOpenVisualDrawer={openVisualDrawer}
          onOpenPromptPanel={openPromptPanel}
          onCloseOverlays={() => {
            explanationRequestIdRef.current += 1
            setPromptOpen(false)
            setDrawerOpen(false)
            setActiveBubble(null)
          }}
          onOpenAccessibilitySettings={onOpenAccessibilitySettings}
          onCloseBubbles={closeBubbles}
          reduceMotion={settings.reduceMotion || settings.disableAnimations}
          overlays={
            <>
              <FloatingBubble
                content={activeBubble}
                theme={movieData.companionTheme}
                reduceMotion={settings.reduceMotion || settings.disableAnimations}
                visible={Boolean(activeBubble)}
                onOpenCompanion={openCompanionFromBubble}
                onClose={closePromptBubble}
              />
              <CompanionWidget
                open={widgetOpen}
                name={profile?.name || 'Lumi'}
                message={assistantText}
                theme={movieData.companionTheme}
                onClose={() => setWidgetOpen(false)}
                reduceMotion={settings.reduceMotion || settings.disableAnimations}
              />
              <PromptPanel
                open={promptOpen}
                prompts={prompts}
                selectedPromptId={selectedPrompt?.id ?? ''}
                onSelectPrompt={selectPrompt}
                onClose={() => setPromptOpen(false)}
              />
            </>
          }
          drawerOverlay={
            <VisualDrawer
              open={drawerOpen}
              sceneState={activeSceneState}
              onClose={() => setDrawerOpen(false)}
            />
          }
        />
      </div>
    </main>
  )
}
