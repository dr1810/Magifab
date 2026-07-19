import { useCallback, useEffect, useMemo, useRef, useState, type FocusEvent } from 'react'
import { TopBar } from './components/TopBar'
import { MoviePlayer } from './components/MoviePlayer'
import { PromptPanel } from './components/PromptPanel'
import { VisualDrawer } from './components/VisualDrawer'
import { FloatingBubble, type PromptBubbleContent } from './components/FloatingBubble'
import { CompanionWidget } from './components/CompanionWidget'
import { useAccessibility } from './accessibility-context'
import { useMoviePlayback } from './hooks/useMoviePlayback'
import { useCompanionProfile } from './hooks/useCompanionProfile'
import { useExperiencePreparation } from './hooks/useExperiencePreparation'
import { ExperiencePreparationScreen } from './components/ExperiencePreparationScreen'
import type { CapturedVideoFrame } from './services/ai/VideoFrameCaptureService'
import { companionBackendService, type IntervalState } from './services/backend/CompanionBackendService'
import { speakText, stopSpeech } from './services/speechService'
import { getPlaybackTimestamp, savePlaybackTimestamp } from './services/playbackSessionService'
import { getScene } from './services/movieService'
import type { MovieId, PromptQuestion, SceneData } from './types/movie'

type MovieViewerProps = {
  movie: MovieId
  onBack: () => void
  onOpenAccessibilitySettings?: () => void
}

export function MovieViewer({ movie, onBack, onOpenAccessibilitySettings = () => undefined }: MovieViewerProps) {
  const { movie: movieData, scene, loading, totalDuration, updateScene } = useMoviePlayback(movie)
  const { profile, loading: companionProfileLoading } = useCompanionProfile()
  const { settings } = useAccessibility()
  const [companionReady, setCompanionReady] = useState(false)
  const preparation = useExperiencePreparation(movieData, companionProfileLoading, companionReady)

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
  const frameCaptureRef = useRef<((timestamp: number) => Promise<CapturedVideoFrame>) | null>(null)
  // These snapshots are the playback source of truth. They are populated in
  // chronological order before the video is allowed to play.
  const intervalStatesRef = useRef<Map<number, IntervalState>>(new Map())
  const activeIntervalRef = useRef<number | null>(null)
  const restoredIntervalIdsRef = useRef<Set<string>>(new Set())
  const currentPlaybackTimeRef = useRef(0)
  const preprocessingStartedRef = useRef(false)
  const preparationEffectCountRef = useRef(0)
  const latestPreparationInputsRef = useRef({ settings, profile })
  const [frameCaptureAvailable, setFrameCaptureAvailable] = useState(false)
  const isSeekingRef = useRef(false)
  const [assistantText, setAssistantText] = useState('Select a prompt to get a simple explanation for this scene.')
  const [intervalState, setIntervalState] = useState<IntervalState | null>(null)
  latestPreparationInputsRef.current = { settings, profile }

  useEffect(() => {
    if (import.meta.env.DEV) console.debug('[MagiFab companion] MovieViewer mounted', { movieId: movie })
    return () => { if (import.meta.env.DEV) console.debug('[MagiFab companion] MovieViewer unmounted', { movieId: movie }) }
  }, [movie])

  const backendPrompts = useMemo<PromptQuestion[]>(() => {
    return intervalState?.prompts.prompt_bubbles.map((prompt) => ({
      id: `backend:${prompt.id}`,
      label: prompt.label,
      question: prompt.question,
      explanation: '',
    })) ?? []
  }, [intervalState])
  const prompts = backendPrompts
  const [selectedPromptId, setSelectedPromptId] = useState<string>('')

  useEffect(() => {
    // PromptSet ownership is interval-scoped. Selecting an item in a new
    // interval must not carry an id from the previous PromptSet.
    setSelectedPromptId(prompts[0]?.id ?? '')
  }, [intervalState?.metadata.interval_id])

  const traceInterval = useCallback((event: 'INTERVAL_LOADED' | 'INTERVAL_UNLOADED' | 'INTERVAL_RESTORED' | 'SEEK_TO_INTERVAL' | 'PROMPTSET_RESTORED' | 'VISUALDRAWER_RESTORED', details: Record<string, unknown>) => {
    console.info(`[MagiFab] ${event}`, { movieId: movie, ...details })
  }, [movie])

  /**
   * The complete playback runtime: resolve timestamp -> retrieve snapshot ->
   * render that exact object. This function intentionally has no backend or
   * reasoning dependency.
   */
  const loadIntervalState = useCallback((timestamp: number, mode: 'playback' | 'seek' | 'restore' = 'playback', force = false) => {
    const interval = Math.floor(timestamp / 10)
    const previousInterval = activeIntervalRef.current
    if (mode === 'seek') traceInterval('SEEK_TO_INTERVAL', { timestamp, intervalNumber: interval })
    if (!force && previousInterval === interval) return

    if (previousInterval !== null) {
      const previous = intervalStatesRef.current.get(previousInterval)
      traceInterval('INTERVAL_UNLOADED', {
        intervalNumber: previousInterval,
        intervalId: previous?.metadata.interval_id ?? null,
      })
    }

    const next = intervalStatesRef.current.get(interval)
    activeIntervalRef.current = interval
    setIntervalState(next ?? null)
    if (!next) {
      // Playback never fills a cache miss: preprocessing is the only writer.
      console.warn('[MagiFab] INTERVAL_MISSING', { movieId: movie, timestamp, intervalNumber: interval })
      return
    }

    const restored = restoredIntervalIdsRef.current.has(next.metadata.interval_id)
    restoredIntervalIdsRef.current.add(next.metadata.interval_id)
    traceInterval(restored || mode === 'restore' ? 'INTERVAL_RESTORED' : 'INTERVAL_LOADED', {
      intervalNumber: interval,
      intervalId: next.metadata.interval_id,
      startTime: next.metadata.start_time,
      endTime: next.metadata.end_time,
    })
    traceInterval('PROMPTSET_RESTORED', {
      intervalId: next.metadata.interval_id,
      promptIds: next.prompts.prompt_bubbles.map((prompt) => prompt.id),
    })
    traceInterval('VISUALDRAWER_RESTORED', { intervalId: next.metadata.interval_id })
  }, [movie, traceInterval])

  useEffect(() => {
    setIntervalState(null)
    intervalStatesRef.current.clear()
    activeIntervalRef.current = null
    restoredIntervalIdsRef.current.clear()
    preprocessingStartedRef.current = false
    setCompanionReady(false)
  }, [movie])

  useEffect(() => {
    const effectCount = ++preparationEffectCountRef.current
    if (import.meta.env.DEV) console.debug('[MagiFab companion] prepare effect', { effectCount, movieId: movieData?.id, frameCaptureAvailable })
    if (preprocessingStartedRef.current || !movieData || !frameCaptureAvailable || !duration) return
    const capture = frameCaptureRef.current
    if (!capture) return
    preprocessingStartedRef.current = true
    let cancelled = false
    const startTimer = window.setTimeout(() => {
      void (async () => {
        const intervalCount = Math.ceil(duration / 10)
        console.info('[MagiFab] Interval preprocessing started', { movieId: movieData.id, intervalCount })
        for (let interval = 0; interval < intervalCount; interval += 1) {
          if (cancelled) return
          const start = interval * 10
          // The final chapter keeps the same fixed range; its sample remains
          // clamped to the available video frame above.
          const end = start + 10
          const sampleTime = Math.min(Math.max(start + 1, 1), Math.max(1, duration - .2))
          const frame = await capture(sampleTime)
          // Catalog scene data is optional enrichment only. Intervals remain
          // valid and continue preprocessing even when it is absent.
          const intervalScene = await getScene(movieData.id, start)
          const inputs = latestPreparationInputsRef.current
          const result = await companionBackendService.prepareInterval({
            movieId: movieData.id,
            scene: intervalScene ?? scene,
            catalogScene: intervalScene,
            intervalNumber: interval,
            intervalStart: start,
            intervalEnd: end,
            frame,
            settings: inputs.settings,
            companion: inputs.profile,
          })
          intervalStatesRef.current.set(interval, result)
        }
        if (cancelled) return
        await companionBackendService.completeMoviePreprocessing(movieData.id, intervalCount)
        loadIntervalState(
          currentPlaybackTimeRef.current,
          currentPlaybackTimeRef.current > 0 ? 'restore' : 'playback',
          true,
        )
        setCompanionReady(true)
        console.info('[MagiFab] Interval preprocessing complete', { movieId: movieData.id, intervalCount })
      })().catch((error: unknown) => {
        preprocessingStartedRef.current = false
        if (import.meta.env.DEV) console.debug('[MagiFab companion] interval preprocessing failed', error)
      })
    }, 0)
    return () => {
      window.clearTimeout(startTimer)
      cancelled = true
    }
  }, [movieData?.id, duration, frameCaptureAvailable, loadIntervalState])

  useEffect(() => {
    const savedTimestamp = getPlaybackTimestamp(movie)
    if (import.meta.env.DEV) console.debug('[MagiFab playback] viewer resume request', { movieId: movie, currentTimeBeforeResume: currentTime, savedTimestamp })
    setCurrentTime(savedTimestamp)
    currentPlaybackTimeRef.current = savedTimestamp
    if (savedTimestamp > 0) void updateScene(savedTimestamp)
    setActiveBubble(null)
    setWidgetOpen(false)
  }, [movie])

  useEffect(() => {
    if (preparation.phase === 'ready') setPlaying(true)
  }, [preparation.phase])

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
    const promptIntervalId = intervalState?.metadata.interval_id
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
    setActiveBubble({ id: `${intervalState?.metadata.interval_id ?? 'interval'}:${prompt.id}:loading`, question: prompt.question, title: 'Preparing help', relationship: '', explanation: '', anchor: loadingAnchor, highlightTarget: false, loading: true })
    if (!intervalState) {
      setActiveBubble({ id: `interval:${prompt.id}:not-prepared`, question: prompt.question, title: 'Preparing this interval', relationship: '', explanation: 'Please wait a moment while this interval is prepared.', anchor: loadingAnchor, highlightTarget: false, loading: true })
      return
    }
    try {
      const result = await companionBackendService.respond({ movieId: movieData.id, scene, question: prompt.question, timestamp: currentTime, settings, companion: profile, signal: abortController.signal })
      if (
        requestId !== explanationRequestIdRef.current
        || isSeekingRef.current
        || activeIntervalRef.current !== intervalState?.metadata.interval_number
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
    currentPlaybackTimeRef.current = timestamp
    setCurrentTime(timestamp)
    // Scene metadata only drives native captions and the bubble anchor. It is
    // not companion reasoning; every companion surface reads IntervalState.
    void updateScene(timestamp)
    loadIntervalState(timestamp)
  }, [loadIntervalState, updateScene])

  const seekToPlaybackTime = useCallback((timestamp: number) => {
    currentPlaybackTimeRef.current = timestamp
    setCurrentTime(timestamp)
    void updateScene(timestamp, true)
    loadIntervalState(timestamp, 'seek', true)
  }, [loadIntervalState, updateScene])

  const handleFrameCaptureReady = useCallback((capture: ((timestamp: number) => Promise<CapturedVideoFrame>) | null) => {
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

  if (loading || !movieData) return <ExperiencePreparationScreen milestones={preparation.milestones} phase={preparation.phase === 'ready' ? 'transitioning' : preparation.phase} reduceMotion={settings.reduceMotion || settings.disableAnimations} />

  return (
    <main className={`movie-experience viewer-page ${preparation.phase === 'ready' ? 'playback-ready' : ''}`}>
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
              intervalState={intervalState}
              onClose={() => setDrawerOpen(false)}
              onMouseEnter={() => setDrawerOpen(true)}
              onMouseLeave={() => setDrawerOpen(false)}
              onFocus={() => setDrawerOpen(true)}
              onBlur={(event: FocusEvent<HTMLElement>) => {
                if (!event.currentTarget.contains(event.relatedTarget)) setDrawerOpen(false)
              }}
            />
          }
        />
      </div>
      {preparation.phase !== 'ready' && <ExperiencePreparationScreen milestones={preparation.milestones} phase={preparation.phase} reduceMotion={settings.reduceMotion || settings.disableAnimations} />}
    </main>
  )
}
