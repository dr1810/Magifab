import { useCallback, useEffect, useMemo, useRef, useState, type FocusEvent } from 'react'
import { Loader2 } from 'lucide-react'
import { TopBar } from './components/TopBar'
import { MoviePlayer } from './components/MoviePlayer'
import { PromptPanel } from './components/PromptPanel'
import { VisualDrawer } from './components/VisualDrawer'
import { FloatingBubble, type PromptBubbleContent } from './components/FloatingBubble'
import { CompanionWidget } from './components/CompanionWidget'
import { useAccessibility } from './accessibility-context'
import { useMoviePlayback } from './hooks/useMoviePlayback'
import { useCompanionProfile } from './hooks/useCompanionProfile'
import type { CapturedVideoFrame } from './services/ai/VideoFrameCaptureService'
import { companionBackendService, type BackendAccessibilityContent } from './services/backend/CompanionBackendService'
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
  const { profile } = useCompanionProfile()
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
  const currentSceneIdRef = useRef<string>('')
  const explanationRequestIdRef = useRef(0)
  const promptAbortControllerRef = useRef<AbortController | null>(null)
  const frameCaptureRef = useRef<(() => CapturedVideoFrame) | null>(null)
  const isSeekingRef = useRef(false)
  const [assistantText, setAssistantText] = useState('Select a prompt to get a simple explanation for this scene.')
  const [accessibilityContent, setAccessibilityContent] = useState<BackendAccessibilityContent | null>(null)

  const backendPrompts = useMemo<PromptQuestion[]>(() => accessibilityContent?.prompt_bubbles.map((prompt) => ({
    id: `backend:${prompt.id}`,
    label: prompt.label,
    question: prompt.question,
    explanation: '',
  })) ?? [], [accessibilityContent])
  const prompts = backendPrompts.length > 0 ? backendPrompts : scene?.prompts ?? []
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
    setAccessibilityContent(null)
  }, [scene?.sceneId])

  useEffect(() => {
    const savedTimestamp = getPlaybackTimestamp(movie)
    if (import.meta.env.DEV) console.debug('[MagiFab playback] viewer resume request', { movieId: movie, currentTimeBeforeResume: currentTime, savedTimestamp })
    setCurrentTime(savedTimestamp)
    if (savedTimestamp > 0) void updateScene(savedTimestamp)
    setActiveBubble(null)
    setWidgetOpen(false)
  }, [movie])

  useEffect(() => {
    if (!movieData) return
    const timer = window.setTimeout(() => savePlaybackTimestamp(movie, currentTime, duration || totalDuration), 300)
    return () => window.clearTimeout(timer)
  }, [currentTime, duration, movie, movieData, totalDuration])

  const selectedPrompt = useMemo(
    () => prompts.find((prompt) => prompt.id === selectedPromptId) ?? prompts[0],
    [prompts, selectedPromptId],
  )

  const buildPromptBubble = useCallback((sceneData: SceneData, prompt: PromptQuestion, result: Awaited<ReturnType<typeof companionBackendService.respond>>, frame: CapturedVideoFrame): PromptBubbleContent => {
    const match = result.semantic_matches?.characters[0]
    const card = result.accessibility_content.drawer.character_cards[0]
    const bbox = match?.entity?.bounding_box
    const visualAnchor = bbox && frame.width > 0 && frame.height > 0
      ? { x: Math.max(0, Math.min(100, (bbox[0] / frame.width) * 100)), y: Math.max(0, Math.min(100, (bbox[1] / frame.height) * 100)), width: Math.max(4, Math.min(100, (bbox[2] / frame.width) * 100)), height: Math.max(4, Math.min(100, (bbox[3] / frame.height) * 100)) }
      : undefined
    const emotion = result.accessibility_content.drawer.emotion_summaries[0]?.summary
    return {
      id: `${sceneData.sceneId}:${prompt.id}:${result.knowledge_revision}`,
      question: prompt.question,
      title: match?.label ?? card?.name ?? prompt.label,
      relationship: emotion ?? result.accessibility_content.scene_summary,
      explanation: result.response.response,
      anchor: visualAnchor ? { x: visualAnchor.x, y: visualAnchor.y } : sceneData.companionPosition,
      visualAnchor,
      visualAidType: visualAnchor ? 'magnifier' : undefined,
      highlightTarget: Boolean(visualAnchor),
    }
  }, [])

  const selectPrompt = (prompt: PromptQuestion) => {
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
    let frame: CapturedVideoFrame
    try {
      frame = frameCaptureRef.current?.() ?? (() => { throw new Error('Frame capture is unavailable.') })()
    } catch (error) {
      setActiveBubble(null)
      setAssistantText(error instanceof Error ? error.message : 'The current movie frame is not ready yet.')
      return
    }
    void companionBackendService.respond({ movieId: movieData.id, scene, question: prompt.question, frame, settings, companion: profile, signal: abortController.signal }).then((result) => {
      if (requestId !== explanationRequestIdRef.current || currentSceneIdRef.current !== scene.sceneId || isSeekingRef.current) return
      setAccessibilityContent(result.accessibility_content)
      setActiveBubble(buildPromptBubble(scene, prompt, result, frame))
      setAssistantText(result.response.response)
      if (settings.voiceAssistance || settings.readPrompts) void speakText({ text: result.response.response, rate: settings.voiceSpeed, volume: Math.min(1, settings.voiceVolume / 100) })
    }).catch((error: unknown) => {
      if (error instanceof DOMException && error.name === 'AbortError') return
      if (requestId !== explanationRequestIdRef.current || currentSceneIdRef.current !== scene.sceneId || isSeekingRef.current) return
      setActiveBubble(null)
      setAssistantText(error instanceof Error ? error.message : 'The companion is unavailable. Please try again.')
    })
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

  const handleFrameCaptureReady = useCallback((capture: (() => CapturedVideoFrame) | null) => {
    frameCaptureRef.current = capture
  }, [])

  const openCompanionFromBubble = useCallback(() => {
    setWidgetOpen(true)
  }, [])

  const closePromptBubble = useCallback(() => {
    explanationRequestIdRef.current += 1
    promptAbortControllerRef.current?.abort()
    setActiveBubble(null)
  }, [])

  if (loading || !movieData || !scene) {
    return (
      <div className="loading-screen">
        <Loader2 className="spin" /> Preparing viewer...
      </div>
    )
  }

  return (
    <main className="movie-experience viewer-page">
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
              accessibilityContent={accessibilityContent}
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
    </main>
  )
}
