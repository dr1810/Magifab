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
import { createStoryCompanionPromptContext, type StoryCompanionPromptContext } from './services/narrative/StoryCompanionNavigation'
import { answerCompanionQuestion, createCompanionGreeting } from './services/narrative/CompanionResponder'
import { speakText, stopSpeech } from './services/speechService'
import { getPlaybackTimestamp, savePlaybackTimestamp } from './services/playbackSessionService'
import type { MovieId, PromptQuestion } from './types/movie'
import { useOverlayManager } from './hooks/useOverlayManager'

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
  const [selectedPromptId, setSelectedPromptId] = useState('')
  const [drawerPrompt, setDrawerPrompt] = useState<StoryCompanionPromptContext | null>(null)
  const [promptCard, setPromptCard] = useState<PromptBubbleContent | null>(null)
  const [companionMessages, setCompanionMessages] = useState<CompanionChatMessage[]>([])
  const [companionGreetingSceneId, setCompanionGreetingSceneId] = useState<string | null>(null)
  const resumeAfterDrawerRef = useRef(false)
  const overlays = useOverlayManager()
  const promptGuideOpen = overlays.isOpen('prompt-guide')
  const promptCardOpen = overlays.isOpen('prompt-card')
  const drawerOpen = overlays.isOpen('story-companion')
  const companionOpen = overlays.isOpen('assistant')

  const sceneState = useMemo(() => resolver?.resolveTime(currentTime, accessibilityProfile?.aiProfile ?? null) ?? null, [accessibilityProfile?.aiProfile, currentTime, resolver])
  const prompts = useMemo<ScenePrompt[]>(() => sceneState?.promptBubbles ?? [], [sceneState])
  const panelPrompts = useMemo<PromptQuestion[]>(() => prompts.map((prompt) => ({ id: prompt.id, label: prompt.label, question: prompt.question, explanation: '' })), [prompts])
  const narrativeBanner = sceneState?.phase === 'intro_credits' || !scene?.subtitle ? sceneState?.subtitle ?? '' : ''

  useEffect(() => {
    const savedTimestamp = getPlaybackTimestamp(movie)
    setCurrentTime(savedTimestamp)
    void updateScene(savedTimestamp, true)
  }, [movie, updateScene])

  useEffect(() => {
    overlays.closeAll()
    setPlaying(false)
    setDuration(0)
    setDrawerPrompt(null)
    setPromptCard(null)
    setCompanionMessages([])
    setCompanionGreetingSceneId(null)
    resumeAfterDrawerRef.current = false
    void stopSpeech()
  }, [movie, overlays.closeAll])

  useEffect(() => {
    setDrawerPrompt(null)
    setPromptCard(null)
    overlays.close('prompt-card')
  }, [movie, overlays.close, sceneState?.sceneId])
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

  const applyTime = useCallback((timestamp: number, immediate = false) => {
    setCurrentTime(timestamp)
    void updateScene(timestamp, immediate)
  }, [updateScene])

  const openStoryCompanion = useCallback((promptContext: StoryCompanionPromptContext | null = null) => {
    if (!sceneState?.companionEnabled) return
    resumeAfterDrawerRef.current = playing
    if (playing) setPlaying(false)
    setDrawerPrompt(promptContext)
    setPromptCard(null)
    overlays.open('story-companion')
    if (promptContext && (settings.voiceAssistance || settings.readPrompts)) void speakText({ text: promptContext.answer, rate: settings.voiceSpeed, volume: Math.min(1, settings.voiceVolume / 100) })
  }, [playing, sceneState?.companionEnabled, settings])
  const openStoryCompanionFromBubble = useCallback(() => {
    if (!sceneState || !promptCard) return
    const prompt = prompts.find((item) => item.id === promptCard.id)
    if (!prompt) return
    const answer = promptCard.explanation || answerPrompt(sceneState, prompt.question)
    openStoryCompanion(createStoryCompanionPromptContext(prompt, answer, sceneState))
  }, [openStoryCompanion, promptCard, prompts, sceneState])
  const selectPrompt = useCallback((panelPrompt: PromptQuestion) => {
    if (!sceneState) return
    const prompt = prompts.find((item) => item.id === panelPrompt.id)
    if (!prompt) return
    setSelectedPromptId(prompt.id)
    setPromptCard({ id: prompt.id, question: prompt.question, title: prompt.label, relationship: sceneState.emotions[0]?.summary ?? '', explanation: answerPrompt(sceneState, prompt.question), anchor: { x: 78, y: 34 }, highlightTarget: false, lifecycle: 'completed' })
    overlays.open('prompt-card')
  }, [overlays, prompts, sceneState])
  const expireBubble = useCallback(() => { setPromptCard(null); overlays.close('prompt-card') }, [overlays])
  const closeInteractionUI = useCallback(() => {
    setPromptCard(null); setDrawerPrompt(null); overlays.closeAll(); void stopSpeech()
  }, [overlays])
  const closePromptGuide = useCallback(() => overlays.close('prompt-guide'), [overlays])
  const closeDrawer = useCallback(() => {
    overlays.close('story-companion')
    setDrawerPrompt(null)
    if (resumeAfterDrawerRef.current) setPlaying(true)
    resumeAfterDrawerRef.current = false
  }, [overlays])
  const toggleCompanionChat = useCallback(() => {
    if (companionOpen) {
      overlays.close('assistant')
      return
    }
    const sceneId = sceneState?.sceneId ?? 'opening'
    if (companionGreetingSceneId !== sceneId || companionMessages.length === 0) {
      setCompanionGreetingSceneId(sceneId)
      setCompanionMessages([{ id: `${sceneId}:greeting`, role: 'assistant', text: createCompanionGreeting(sceneState, accessibilityProfile?.companionProfile ?? null) }])
    }
    overlays.open('assistant')
  }, [accessibilityProfile?.companionProfile, companionGreetingSceneId, companionMessages.length, companionOpen, overlays, sceneState])
  const askCompanion = useCallback((question: string) => {
    const answer = answerCompanionQuestion(sceneState, question, accessibilityProfile?.aiProfile ?? null)
    const messageId = `${sceneState?.sceneId ?? 'opening'}:${Date.now()}`
    setCompanionMessages((messages) => [...messages, { id: `${messageId}:question`, role: 'user', text: question }, { id: `${messageId}:answer`, role: 'assistant', text: answer }])
  }, [accessibilityProfile?.aiProfile, sceneState])
  const closeOverlays = useCallback(() => {
    if (drawerOpen) closeDrawer()
    else closeInteractionUI()
  }, [closeDrawer, closeInteractionUI, drawerOpen])
  if (loading || !movieData) return <div className="movie-experience viewer-page" aria-busy="true" />
  return <main className="movie-experience viewer-page playback-ready">
    <TopBar movie={movieData} onBack={() => { closeInteractionUI(); savePlaybackTimestamp(movie, currentTime, duration || totalDuration); onBack() }} onOpenPrompts={() => { if (sceneState?.companionEnabled) overlays.open('prompt-guide') }} onOpenDrawer={() => openStoryCompanion()} />
    <div className="viewer-layout" style={{ position: 'relative' }}>
      <MoviePlayer movie={movieData} scene={scene} subtitle={narrativeBanner} playing={playing} muted={muted} volume={volume} currentTime={currentTime} totalTime={duration || totalDuration} onPlayToggle={() => setPlaying((value) => !value)} onMuteToggle={() => setMuted((value) => !value)} onVolumeChange={setVolume} onSeek={(timestamp) => applyTime(timestamp, true)} onTimeChange={applyTime} onDurationChange={setDuration} onSeeking={expireBubble} onSeekComplete={(timestamp) => applyTime(timestamp, true)} promptOpen={promptGuideOpen} onTogglePromptPanel={() => { if (sceneState?.companionEnabled) promptGuideOpen ? closePromptGuide() : overlays.open('prompt-guide') }} onOpenVisualDrawer={() => openStoryCompanion()} onOpenPromptPanel={() => { if (sceneState?.companionEnabled) overlays.open('prompt-guide') }} onCloseOverlays={closeOverlays} onOpenAccessibilitySettings={onOpenAccessibilitySettings} onCloseBubbles={closeInteractionUI} reduceMotion={settings.reduceMotion || settings.disableAnimations}
        overlays={<><FloatingBubble content={promptCard} theme={movieData.companionTheme} reduceMotion={settings.reduceMotion || settings.disableAnimations} visible={promptCardOpen} onOpenCompanion={openStoryCompanionFromBubble} onClose={expireBubble} /><PromptPanel open={promptGuideOpen} prompts={panelPrompts} selectedPromptId={selectedPromptId} onSelectPrompt={selectPrompt} onClose={closePromptGuide} /></>}
        companionOverlay={<>{!drawerOpen && !promptGuideOpen && <button id="companion-launcher" type="button" className="companion-launcher" onClick={toggleCompanionChat} aria-expanded={companionOpen} aria-controls="companion-chat-panel" aria-label={`${companionOpen ? 'Close' : 'Open'} ${accessibilityProfile?.companionProfile?.name ?? 'Lumi'} companion chat`}><CompanionAvatar appearance={accessibilityProfile?.companionProfile?.appearance} name={accessibilityProfile?.companionProfile?.name ?? 'Lumi'} /><span>{accessibilityProfile?.companionProfile?.name ?? 'Lumi'}</span></button>}<CompanionChatPanel open={companionOpen} name={accessibilityProfile?.companionProfile?.name ?? 'Lumi'} appearance={accessibilityProfile?.companionProfile?.appearance} theme={movieData.companionTheme} messages={companionMessages} onClose={() => overlays.close('assistant')} onSend={askCompanion} reduceMotion={settings.reduceMotion || settings.disableAnimations} drawerOpen={drawerOpen} /></>}
        drawerOverlay={<VisualDrawer open={drawerOpen} sceneState={sceneState} promptContext={drawerPrompt} onClose={closeDrawer} />}
      />
    </div>
  </main>
}
