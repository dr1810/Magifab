import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { TopBar } from './components/TopBar'
import { MoviePlayer } from './components/MoviePlayer'
import { PromptPanel } from './components/PromptPanel'
import { VisualDrawer } from './components/VisualDrawer'
import { FloatingBubble, type PromptBubbleContent } from './components/FloatingBubble'
import { CompanionAvatar } from './components/CompanionAvatar'
import { CompanionChatPanel, type CompanionChatMessage } from './components/CompanionChatPanel'
import { useAccessibility } from './accessibility-context'
import { useMoviePlayback } from './hooks/useMoviePlayback'
import { useAccessibilityProfile } from './hooks/useAccessibilityProfile'
import { answerPrompt, StoryResolver } from './services/narrative/StoryResolver'
import { getMovieNarrativeGraph } from './services/narrative/NarrativeRepository'
import { useStoryContextObserver } from './services/narrative/StoryContextObserver'
import { usePromptLifecycle } from './services/narrative/usePromptLifecycle'
import { createStoryCompanionPromptContext, type StoryCompanionPromptContext } from './services/narrative/StoryCompanionNavigation'
import { answerCompanionQuestion, createCompanionGreeting } from './services/narrative/CompanionResponder'
import { speakText, stopSpeech } from './services/speechService'
import { getPlaybackTimestamp, savePlaybackTimestamp } from './services/playbackSessionService'
import type { MovieId, PromptQuestion } from './types/movie'

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
  const [promptOpen, setPromptOpen] = useState(false)
  const [selectedPromptId, setSelectedPromptId] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerPrompt, setDrawerPrompt] = useState<StoryCompanionPromptContext | null>(null)
  const [bubblePrompt, setBubblePrompt] = useState<ScenePrompt | null>(null)
  const [bubbleDismissedSceneId, setBubbleDismissedSceneId] = useState<string | null>(null)
  const [companionOpen, setCompanionOpen] = useState(false)
  const [companionMessages, setCompanionMessages] = useState<CompanionChatMessage[]>([])
  const [companionGreetingSceneId, setCompanionGreetingSceneId] = useState<string | null>(null)
  const resumeAfterDrawerRef = useRef(false)

  const sceneState = useMemo(() => resolver?.resolveTime(currentTime, accessibilityProfile?.aiProfile ?? null) ?? null, [accessibilityProfile?.aiProfile, currentTime, resolver])
  const storyContext = useStoryContextObserver(sceneState, currentTime)
  const { activePrompt: activeBubble, start: startPrompt, dismiss: dismissPrompt, cancel: cancelPrompt } = usePromptLifecycle(storyContext)
  const prompts = useMemo<ScenePrompt[]>(() => sceneState?.promptBubbles ?? [], [sceneState])
  const panelPrompts = useMemo<PromptQuestion[]>(() => prompts.map((prompt) => ({ id: prompt.id, label: prompt.label, question: prompt.question, explanation: '' })), [prompts])
  const narrativeBanner = sceneState?.phase === 'intro_credits' || !scene?.subtitle ? sceneState?.subtitle ?? '' : ''

  useEffect(() => {
    const savedTimestamp = getPlaybackTimestamp(movie)
    setCurrentTime(savedTimestamp)
    void updateScene(savedTimestamp, true)
  }, [movie, updateScene])

  useEffect(() => {
    if (!sceneState?.companionEnabled) {
      dismissPrompt()
      setBubblePrompt(null)
      setDrawerPrompt(null)
      setDrawerOpen(false)
      setPromptOpen(false)
      return
    }
    setPromptOpen(true)
  }, [dismissPrompt, sceneState?.companionEnabled, sceneState?.sceneId])
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
  useEffect(() => { setBubbleDismissedSceneId(null) }, [sceneState?.sceneId])
  useEffect(() => { setSelectedPromptId(sceneState?.promptBubbles[0]?.id ?? '') }, [sceneState?.sceneId])
  useEffect(() => {
    if (!companionOpen || !sceneState?.sceneId) return
    setCompanionGreetingSceneId(sceneState.sceneId)
    setCompanionMessages([{ id: `${sceneState.sceneId}:greeting`, role: 'assistant', text: createCompanionGreeting(sceneState, accessibilityProfile?.companionProfile ?? null) }])
  }, [accessibilityProfile?.companionProfile, companionOpen, sceneState?.sceneId])
  useEffect(() => { if (movieData && duration > 0) setPlaying(true) }, [duration, movieData])
  useEffect(() => {
    if (!movieData) return
    const timer = window.setTimeout(() => savePlaybackTimestamp(movie, currentTime, duration || totalDuration), 300)
    return () => window.clearTimeout(timer)
  }, [currentTime, duration, movie, movieData, totalDuration])

  const fallbackBubble = useMemo<PromptBubbleContent | null>(() => {
    const prompt = prompts[0]
    if (!sceneState?.companionEnabled || !prompt || bubbleDismissedSceneId === sceneState.sceneId) return null
    return {
      id: `${sceneState.sceneId}:${prompt.id}:suggested`, question: prompt.question, title: prompt.label, relationship: sceneState.emotions[0]?.summary ?? '', explanation: answerPrompt(sceneState, prompt.question), anchor: scene?.companionPosition ?? { x: 84, y: 74 }, highlightTarget: false, lifecycle: 'completed', contextVersion: storyContext.contextVersion, storyBeatId: storyContext.storyBeatId ?? '', timestampCreated: storyContext.currentTime, validFrom: storyContext.validFrom, validUntil: storyContext.validUntil,
    }
  }, [bubbleDismissedSceneId, prompts, scene?.companionPosition, sceneState, storyContext])
  const activeBubbleVisible = Boolean(activeBubble && activeBubble.lifecycle !== 'expired' && activeBubble.lifecycle !== 'dismissed')
  const bubbleContent = activeBubbleVisible ? activeBubble : fallbackBubble

  const applyTime = useCallback((timestamp: number, immediate = false) => {
    setCurrentTime(timestamp)
    void updateScene(timestamp, immediate)
  }, [updateScene])

  const openStoryCompanion = useCallback((promptContext: StoryCompanionPromptContext | null = null) => {
    if (!sceneState?.companionEnabled) return
    resumeAfterDrawerRef.current = playing
    if (playing) setPlaying(false)
    setDrawerPrompt(promptContext)
    setDrawerOpen(true)
    if (promptContext && (settings.voiceAssistance || settings.readPrompts)) void speakText({ text: promptContext.answer, rate: settings.voiceSpeed, volume: Math.min(1, settings.voiceVolume / 100) })
  }, [playing, sceneState?.companionEnabled, settings])
  const openStoryCompanionFromBubble = useCallback(() => {
    const prompt = bubblePrompt ?? prompts[0]
    if (!sceneState || !prompt) return
    const answer = bubbleContent?.explanation || answerPrompt(sceneState, prompt.question)
    openStoryCompanion(createStoryCompanionPromptContext(prompt, answer, sceneState))
  }, [bubbleContent, bubblePrompt, openStoryCompanion, prompts, sceneState])
  const selectPrompt = useCallback((panelPrompt: PromptQuestion) => {
    if (!sceneState) return
    const prompt = prompts.find((item) => item.id === panelPrompt.id)
    if (!prompt) return
    setSelectedPromptId(prompt.id)
    const answer = answerPrompt(sceneState, prompt.question)
    openStoryCompanion(createStoryCompanionPromptContext(prompt, answer, sceneState))
  }, [openStoryCompanion, prompts, sceneState])
  const expireBubble = useCallback(() => {
    dismissPrompt(); setBubblePrompt(null)
  }, [dismissPrompt])
  const closeInteractionUI = useCallback(() => {
    expireBubble(); setBubbleDismissedSceneId(sceneState?.sceneId ?? null); void stopSpeech()
  }, [expireBubble, sceneState?.sceneId])
  const closePromptGuide = useCallback(() => setPromptOpen(false), [])
  const closeDrawer = useCallback(() => {
    setDrawerOpen(false)
    setDrawerPrompt(null)
    if (resumeAfterDrawerRef.current) setPlaying(true)
    resumeAfterDrawerRef.current = false
  }, [])
  const openCompanionChat = useCallback(() => {
    const sceneId = sceneState?.sceneId ?? 'opening'
    if (companionGreetingSceneId !== sceneId || companionMessages.length === 0) {
      setCompanionGreetingSceneId(sceneId)
      setCompanionMessages([{ id: `${sceneId}:greeting`, role: 'assistant', text: createCompanionGreeting(sceneState, accessibilityProfile?.companionProfile ?? null) }])
    }
    setCompanionOpen(true)
  }, [accessibilityProfile?.companionProfile, companionGreetingSceneId, companionMessages.length, sceneState])
  const askCompanion = useCallback((question: string) => {
    const answer = answerCompanionQuestion(sceneState, question, accessibilityProfile?.aiProfile ?? null)
    const messageId = `${sceneState?.sceneId ?? 'opening'}:${Date.now()}`
    setCompanionMessages((messages) => [...messages, { id: `${messageId}:question`, role: 'user', text: question }, { id: `${messageId}:answer`, role: 'assistant', text: answer }])
  }, [accessibilityProfile?.aiProfile, sceneState])
  const closeOverlays = useCallback(() => {
    if (companionOpen) setCompanionOpen(false)
    else if (drawerOpen) closeDrawer()
    else if (promptOpen) closePromptGuide()
    else closeInteractionUI()
  }, [closeDrawer, closeInteractionUI, closePromptGuide, companionOpen, drawerOpen, promptOpen])
  if (loading || !movieData) return <div className="movie-experience viewer-page" aria-busy="true" />
  return <main className="movie-experience viewer-page playback-ready">
    <TopBar movie={movieData} onBack={() => { cancelPrompt(); savePlaybackTimestamp(movie, currentTime, duration || totalDuration); onBack() }} onOpenPrompts={() => { if (sceneState?.companionEnabled) setPromptOpen(true) }} onOpenDrawer={() => openStoryCompanion()} />
    <div className="viewer-layout" style={{ position: 'relative' }}>
      <MoviePlayer movie={movieData} scene={scene} subtitle={narrativeBanner} playing={playing} muted={muted} volume={volume} currentTime={currentTime} totalTime={duration || totalDuration} onPlayToggle={() => setPlaying((value) => !value)} onMuteToggle={() => setMuted((value) => !value)} onVolumeChange={setVolume} onSeek={(timestamp) => applyTime(timestamp, true)} onTimeChange={applyTime} onDurationChange={setDuration} onSeeking={expireBubble} onSeekComplete={(timestamp) => applyTime(timestamp, true)} promptOpen={promptOpen} onTogglePromptPanel={() => { if (sceneState?.companionEnabled) setPromptOpen((open) => !open) }} onOpenVisualDrawer={() => openStoryCompanion()} onOpenPromptPanel={() => { if (sceneState?.companionEnabled) setPromptOpen(true) }} onCloseOverlays={closeOverlays} onOpenAccessibilitySettings={onOpenAccessibilitySettings} onCloseBubbles={closeInteractionUI} reduceMotion={settings.reduceMotion || settings.disableAnimations}
        overlays={<><FloatingBubble content={bubbleContent} theme={movieData.companionTheme} reduceMotion={settings.reduceMotion || settings.disableAnimations} visible={Boolean(bubbleContent)} onOpenCompanion={openStoryCompanionFromBubble} onClose={closeInteractionUI} /><PromptPanel open={promptOpen} prompts={panelPrompts} selectedPromptId={selectedPromptId} onSelectPrompt={selectPrompt} onClose={closePromptGuide} /><button type="button" className={`companion-launcher ${drawerOpen ? 'above-drawer' : ''}`} onClick={openCompanionChat} aria-label={`Open ${accessibilityProfile?.companionProfile?.name ?? 'Lumi'} companion chat`}><CompanionAvatar appearance={accessibilityProfile?.companionProfile?.appearance} name={accessibilityProfile?.companionProfile?.name ?? 'Lumi'} /><span>{accessibilityProfile?.companionProfile?.name ?? 'Lumi'}</span></button><CompanionChatPanel open={companionOpen} name={accessibilityProfile?.companionProfile?.name ?? 'Lumi'} appearance={accessibilityProfile?.companionProfile?.appearance} theme={movieData.companionTheme} messages={companionMessages} onClose={() => setCompanionOpen(false)} onSend={askCompanion} reduceMotion={settings.reduceMotion || settings.disableAnimations} drawerOpen={drawerOpen} /></>}
        drawerOverlay={<VisualDrawer open={drawerOpen} sceneState={sceneState} promptContext={drawerPrompt} onClose={closeDrawer} />}
      />
    </div>
  </main>
}
