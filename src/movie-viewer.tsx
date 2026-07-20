import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { TopBar } from './components/TopBar'
import { MoviePlayer } from './components/MoviePlayer'
import { VisualDrawer } from './components/VisualDrawer'
import { FloatingBubble } from './components/FloatingBubble'
import { useAccessibility } from './accessibility-context'
import { useMoviePlayback } from './hooks/useMoviePlayback'
import { useAccessibilityProfile } from './hooks/useAccessibilityProfile'
import { answerPrompt, StoryResolver } from './services/narrative/StoryResolver'
import { getMovieNarrativeGraph } from './services/narrative/NarrativeRepository'
import { useStoryContextObserver } from './services/narrative/StoryContextObserver'
import { usePromptLifecycle } from './services/narrative/usePromptLifecycle'
import { createStoryCompanionPromptContext, type StoryCompanionPromptContext } from './services/narrative/StoryCompanionNavigation'
import { speakText, stopSpeech } from './services/speechService'
import { getPlaybackTimestamp, savePlaybackTimestamp } from './services/playbackSessionService'
import type { MovieId } from './types/movie'

type MovieViewerProps = { movie: MovieId; onBack: () => void; onOpenAccessibilitySettings?: () => void }
type ScenePrompt = { id: string; kind: string; label: string; question: string; priority: number }

export function MovieViewer({ movie, onBack, onOpenAccessibilitySettings = () => undefined }: MovieViewerProps) {
  const { movie: movieData, scene, loading, totalDuration, updateScene } = useMoviePlayback(movie)
  const { profile: accessibilityProfile } = useAccessibilityProfile()
  const { settings } = useAccessibility()
  const graph = useMemo(() => getMovieNarrativeGraph(movie), [movie])
  const resolver = useMemo(() => graph ? new StoryResolver(graph) : null, [graph])
  const [playing, setPlaying] = useState(false)
  const [muted, setMuted] = useState(false)
  const [volume, setVolume] = useState(72)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerPrompt, setDrawerPrompt] = useState<StoryCompanionPromptContext | null>(null)
  const [bubblePrompt, setBubblePrompt] = useState<ScenePrompt | null>(null)
  const resumeAfterDrawerRef = useRef(false)

  const sceneState = useMemo(() => resolver?.resolveTime(currentTime, accessibilityProfile?.aiProfile ?? null) ?? null, [accessibilityProfile?.aiProfile, currentTime, resolver])
  const storyContext = useStoryContextObserver(sceneState, currentTime)
  const { activePrompt: activeBubble, start: startPrompt, dismiss: dismissPrompt, cancel: cancelPrompt } = usePromptLifecycle(storyContext)
  const prompts = useMemo<ScenePrompt[]>(() => sceneState?.promptBubbles ?? [], [sceneState])
  const narrativeBanner = sceneState?.phase === 'intro_credits' || !scene?.subtitle ? sceneState?.subtitle ?? '' : ''

  useEffect(() => {
    const savedTimestamp = getPlaybackTimestamp(movie)
    setCurrentTime(savedTimestamp)
    void updateScene(savedTimestamp, true)
  }, [movie, updateScene])

  useEffect(() => {
    if (sceneState?.companionEnabled) return
    dismissPrompt()
    setBubblePrompt(null)
    setDrawerPrompt(null)
    setDrawerOpen(false)
  }, [dismissPrompt, sceneState?.companionEnabled])
  useEffect(() => {
    const prompt = prompts[0]
    if (!sceneState?.companionEnabled || !prompt) return
    const answer = answerPrompt(sceneState, prompt.question)
    setBubblePrompt(prompt)
    void startPrompt({ id: `${sceneState.sceneId}:${prompt.id}`, question: prompt.question, title: prompt.label, relationship: sceneState.emotions[0]?.summary ?? '', explanation: '', anchor: scene?.companionPosition ?? { x: 84, y: 74 }, highlightTarget: false }, async (signal) => {
      if (signal.aborted) throw new DOMException('Prompt request cancelled', 'AbortError')
      return answer
    }, 'This explanation is no longer available. Please choose a prompt for the current story moment.')
  }, [sceneState?.sceneId])
  useEffect(() => { setDrawerPrompt(null) }, [sceneState?.sceneId])
  useEffect(() => { if (movieData && duration > 0) setPlaying(true) }, [duration, movieData])
  useEffect(() => {
    if (!movieData) return
    const timer = window.setTimeout(() => savePlaybackTimestamp(movie, currentTime, duration || totalDuration), 300)
    return () => window.clearTimeout(timer)
  }, [currentTime, duration, movie, movieData, totalDuration])

  const applyTime = useCallback((timestamp: number, immediate = false) => {
    setCurrentTime(timestamp)
    void updateScene(timestamp, immediate)
  }, [updateScene])

  const openStoryCompanion = useCallback((promptContext: StoryCompanionPromptContext | null = null) => {
    if (!sceneState?.companionEnabled) return
    resumeAfterDrawerRef.current = playing
    if (playing) setPlaying(false)
    dismissPrompt()
    setBubblePrompt(null)
    setDrawerPrompt(promptContext)
    setDrawerOpen(true)
    if (promptContext && (settings.voiceAssistance || settings.readPrompts)) void speakText({ text: promptContext.answer, rate: settings.voiceSpeed, volume: Math.min(1, settings.voiceVolume / 100) })
  }, [dismissPrompt, playing, sceneState?.companionEnabled, settings])
  const openStoryCompanionFromBubble = useCallback(() => {
    if (!sceneState || !bubblePrompt || !activeBubble) return
    const answer = activeBubble.explanation || answerPrompt(sceneState, bubblePrompt.question)
    openStoryCompanion(createStoryCompanionPromptContext(bubblePrompt, answer, sceneState))
  }, [activeBubble, bubblePrompt, openStoryCompanion, sceneState])
  const closeBubbles = useCallback(() => {
    dismissPrompt(); setBubblePrompt(null); void stopSpeech()
  }, [dismissPrompt])
  const closeDrawer = useCallback(() => {
    setDrawerOpen(false)
    setDrawerPrompt(null)
    if (resumeAfterDrawerRef.current) setPlaying(true)
    resumeAfterDrawerRef.current = false
  }, [])
  const closeOverlays = useCallback(() => {
    closeBubbles()
    if (drawerOpen) closeDrawer()
  }, [closeBubbles, closeDrawer, drawerOpen])
  const bubbleVisible = Boolean(activeBubble && activeBubble.lifecycle !== 'expired' && activeBubble.lifecycle !== 'dismissed')

  if (loading || !movieData) return <div className="movie-experience viewer-page" aria-busy="true" />
  return <main className="movie-experience viewer-page playback-ready">
    <TopBar movie={movieData} onBack={() => { cancelPrompt(); savePlaybackTimestamp(movie, currentTime, duration || totalDuration); onBack() }} onOpenDrawer={() => openStoryCompanion()} />
    <div className="viewer-layout" style={{ position: 'relative' }}>
      <MoviePlayer movie={movieData} scene={scene} subtitle={narrativeBanner} playing={playing} muted={muted} volume={volume} currentTime={currentTime} totalTime={duration || totalDuration} onPlayToggle={() => setPlaying((value) => !value)} onMuteToggle={() => setMuted((value) => !value)} onVolumeChange={setVolume} onSeek={(timestamp) => applyTime(timestamp, true)} onTimeChange={applyTime} onDurationChange={setDuration} onSeeking={closeBubbles} onSeekComplete={(timestamp) => applyTime(timestamp, true)} onOpenVisualDrawer={() => openStoryCompanion()} onCloseOverlays={closeOverlays} onOpenAccessibilitySettings={onOpenAccessibilitySettings} reduceMotion={settings.reduceMotion || settings.disableAnimations}
        overlays={<FloatingBubble content={activeBubble} theme={movieData.companionTheme} reduceMotion={settings.reduceMotion || settings.disableAnimations} visible={bubbleVisible && !drawerOpen} onOpenCompanion={openStoryCompanionFromBubble} onClose={closeBubbles} />}
        drawerOverlay={<VisualDrawer open={drawerOpen} sceneState={sceneState} promptContext={drawerPrompt} onClose={closeDrawer} />}
      />
    </div>
  </main>
}
