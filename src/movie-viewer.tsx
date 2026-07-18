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
import { companionBackendService, type AccessibilityPresentation, type ScenePreparationResponse } from './services/backend/CompanionBackendService'
import { speakText, stopSpeech } from './services/speechService'
import { getPlaybackTimestamp, savePlaybackTimestamp } from './services/playbackSessionService'
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
  const currentSceneIdRef = useRef<string>('')
  const explanationRequestIdRef = useRef(0)
  const promptAbortControllerRef = useRef<AbortController | null>(null)
  const frameCaptureRef = useRef<(() => Promise<CapturedVideoFrame>) | null>(null)
  const preparedFrameRef = useRef<CapturedVideoFrame | null>(null)
  const preparedSceneIdsRef = useRef<Set<string>>(new Set())
  const preparationEffectCountRef = useRef(0)
  const latestPreparationInputsRef = useRef({ settings, profile })
  const [frameCaptureAvailable, setFrameCaptureAvailable] = useState(false)
  const isSeekingRef = useRef(false)
  const [assistantText, setAssistantText] = useState('Select a prompt to get a simple explanation for this scene.')
  const [accessibilityPresentation, setAccessibilityPresentation] = useState<AccessibilityPresentation | null>(null)
  const [preparedScene, setPreparedScene] = useState<ScenePreparationResponse | null>(null)
  latestPreparationInputsRef.current = { settings, profile }

  useEffect(() => {
    if (import.meta.env.DEV) console.debug('[MagiFab companion] MovieViewer mounted', { movieId: movie })
    return () => { if (import.meta.env.DEV) console.debug('[MagiFab companion] MovieViewer unmounted', { movieId: movie }) }
  }, [movie])

  const backendPrompts = useMemo<PromptQuestion[]>(() => {
    if (preparedScene?.presentation.prompt_bubbles) {
      return preparedScene.presentation.prompt_bubbles.map((prompt) => ({
        id: `backend:${prompt.id}`,
        label: prompt.label,
        question: prompt.question,
        explanation: '',
      }))
    }
    return accessibilityPresentation?.prompt_bubbles.map((prompt) => ({
      id: `backend:${prompt.id}`,
      label: prompt.label,
      question: prompt.question,
      explanation: '',
    })) ?? []
  }, [preparedScene, accessibilityPresentation])
  const prompts = backendPrompts
  const [selectedPromptId, setSelectedPromptId] = useState<string>('')

  useEffect(() => {
    if (prompts.length > 0) {
      setSelectedPromptId((current) => current || prompts[0].id)
    }
  }, [prompts])

  useEffect(() => {
    const sceneId = scene?.sceneId ?? ''
    currentSceneIdRef.current = sceneId
    setActiveBubble((bubble) => bubble?.id.startsWith(`${sceneId}:`) ? bubble : null)
    setCompanionReady(false)
  }, [scene?.sceneId])

  useEffect(() => {
    // The Loading Experience owns the opening-scene result for the selected
    // movie. Scene updates from the mounted video must not erase its prompts.
    setAccessibilityPresentation(null)
    setPreparedScene(null)
    preparedSceneIdsRef.current.delete(movie)
  }, [movie])

  useEffect(() => {
    const effectCount = ++preparationEffectCountRef.current
    if (import.meta.env.DEV) console.debug('[MagiFab companion] prepare effect', { effectCount, movieId: movieData?.id, sceneId: scene?.sceneId, frameCaptureAvailable })
    // Prepare belongs to the Loading Experience gate; canplay only makes the
    // already-owned frame capture available.
    if (preparation.phase !== 'preparing' || !movieData || !scene || !frameCaptureAvailable || preparedSceneIdsRef.current.has(movieData.id)) return
    const capture = frameCaptureRef.current
    if (!capture) return
    preparedSceneIdsRef.current.add(movieData.id)
    let requestStarted = false
    const startTimer = window.setTimeout(() => {
      requestStarted = true
      console.info('[MagiFab] Preparation started', { movieId: movieData.id, sceneId: scene.sceneId })
      void capture().then((frame) => {
      preparedFrameRef.current = frame
      const inputs = latestPreparationInputsRef.current
      return companionBackendService.prepareScene({ movieId: movieData.id, scene, frame, settings: inputs.settings, companion: inputs.profile })
    }).then((result) => {
      if (!result) return
      setPreparedScene(result)
      setAccessibilityPresentation(result.presentation)
      setCompanionReady(true)
      console.info('[MagiFab] Preparation complete', { movieId: movieData.id, sceneId: scene.sceneId })
      console.info('[MagiFab] Prompt bubbles received:', result.presentation.prompt_bubbles.length)
    }).catch((error: unknown) => {
      if (import.meta.env.DEV) console.debug('[MagiFab companion] prepare() failed', { movieId: movieData.id, sceneId: scene.sceneId, error })
      preparedSceneIdsRef.current.delete(movieData.id)
    })
    }, 0)
    return () => {
      window.clearTimeout(startTimer)
      // React Strict Mode deliberately runs an effect cleanup before its second
      // development mount. That cleanup happens before the deferred request
      // begins, so it must not consume this movie's one preparation slot.
      if (!requestStarted) preparedSceneIdsRef.current.delete(movieData.id)
      // Rerenders, overlays, and Strict Mode cleanup must not cancel a running
      // prepare request. It is owned by the Loading Experience until it settles.
    }
  }, [movieData?.id, scene?.sceneId, frameCaptureAvailable, preparation.phase])

  useEffect(() => {
    const savedTimestamp = getPlaybackTimestamp(movie)
    if (import.meta.env.DEV) console.debug('[MagiFab playback] viewer resume request', { movieId: movie, currentTimeBeforeResume: currentTime, savedTimestamp })
    setCurrentTime(savedTimestamp)
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

  const buildPromptBubble = useCallback((sceneData: SceneData, prompt: PromptQuestion, result: Awaited<ReturnType<typeof companionBackendService.respond>>): PromptBubbleContent => {
    const card = result.presentation.character_cards[0]
    const emotion = result.presentation.emotion_summaries[0]?.summary
    return {
      id: `${sceneData.sceneId}:${prompt.id}:${result.knowledge_revision}`,
      question: prompt.question,
      title: card?.name ?? prompt.label,
      relationship: emotion ?? result.presentation.scene_explanation,
      explanation: result.response.response,
      anchor: sceneData.companionPosition,
      highlightTarget: false,
    }
  }, [])

  const selectPrompt = async (prompt: PromptQuestion) => {
    if (!scene || !movieData || isSeekingRef.current) return
    setSelectedPromptId(prompt.id)
    setPromptOpen(false)
    setDrawerOpen(false)
    setWidgetOpen(false)
    setActiveBubble(null)

    promptAbortControllerRef.current?.abort()
    const abortController = new AbortController()
    promptAbortControllerRef.current = abortController
    const requestId = ++explanationRequestIdRef.current
    const loadingAnchor = { x: scene.companionPosition.x, y: scene.companionPosition.y }
    setActiveBubble({ id: `${scene.sceneId}:${prompt.id}:loading`, question: prompt.question, title: 'Preparing help', relationship: '', explanation: '', anchor: loadingAnchor, highlightTarget: false, loading: true })
    const frame = preparedFrameRef.current
    if (!frame || !accessibilityPresentation) {
      setActiveBubble({ id: `${scene.sceneId}:${prompt.id}:not-prepared`, question: prompt.question, title: 'Preparing this scene', relationship: '', explanation: 'Please wait a moment while this scene is prepared.', anchor: loadingAnchor, highlightTarget: false, loading: true })
      return
    }
    try {
      const result = await companionBackendService.respond({ movieId: movieData.id, scene, question: prompt.question, timestamp: frame.timestamp, settings, companion: profile, signal: abortController.signal })
      if (requestId !== explanationRequestIdRef.current || currentSceneIdRef.current !== scene.sceneId || isSeekingRef.current) return
      setAccessibilityPresentation(result.presentation)
      setActiveBubble(buildPromptBubble(scene, prompt, result))
      setAssistantText(result.response.response)
      if (settings.voiceAssistance || settings.readPrompts) void speakText({ text: result.response.response, rate: settings.voiceSpeed, volume: Math.min(1, settings.voiceVolume / 100) })
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      if (requestId !== explanationRequestIdRef.current || currentSceneIdRef.current !== scene.sceneId || isSeekingRef.current) return
      const message = error instanceof Error ? error.message : 'The companion is unavailable. Please try again.'
      setActiveBubble({ id: `${scene.sceneId}:${prompt.id}:request-error`, question: prompt.question, title: 'Companion unavailable', relationship: '', explanation: message, anchor: loadingAnchor, highlightTarget: false })
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

  const handleFrameCaptureReady = useCallback((capture: (() => Promise<CapturedVideoFrame>) | null) => {
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

  if (loading || !movieData || !scene) return <ExperiencePreparationScreen milestones={preparation.milestones} phase={preparation.phase === 'ready' ? 'transitioning' : preparation.phase} reduceMotion={settings.reduceMotion || settings.disableAnimations} />

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
            setCurrentTime(next)
            void updateScene(next)
          }}
          onTimeChange={(next) => {
            setCurrentTime(next)
            void updateScene(next)
          }}
          onDurationChange={setDuration}
          onSeeking={handleSeeking}
          onSeekComplete={(timestamp) => {
            isSeekingRef.current = false
            setCurrentTime(timestamp)
            updateScene(timestamp, true)
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
              scene={scene}
              presentation={accessibilityPresentation}
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
