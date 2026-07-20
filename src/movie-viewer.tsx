import { useCallback, useEffect, useMemo, useState } from 'react'
import { TopBar } from './components/TopBar'
import { MoviePlayer } from './components/MoviePlayer'
import { PromptPanel } from './components/PromptPanel'
import { VisualDrawer } from './components/VisualDrawer'
import { FloatingBubble, type PromptBubbleContent } from './components/FloatingBubble'
import { CompanionWidget } from './components/CompanionWidget'
import { useAccessibility } from './accessibility-context'
import { useMoviePlayback } from './hooks/useMoviePlayback'
import { useCompanionProfile } from './hooks/useCompanionProfile'
import { useAccessibilityProfile } from './hooks/useAccessibilityProfile'
import { answerPrompt, StoryResolver } from './services/narrative/StoryResolver'
import { getMovieNarrativeGraph } from './services/narrative/NarrativeRepository'
import { speakText, stopSpeech } from './services/speechService'
import { getPlaybackTimestamp, savePlaybackTimestamp } from './services/playbackSessionService'
import type { MovieId, PromptQuestion } from './types/movie'

type MovieViewerProps = { movie: MovieId; onBack: () => void; onOpenAccessibilitySettings?: () => void }

export function MovieViewer({ movie, onBack, onOpenAccessibilitySettings = () => undefined }: MovieViewerProps) {
  const { movie: movieData, scene, loading, totalDuration, updateScene } = useMoviePlayback(movie)
  const { profile } = useCompanionProfile()
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
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [widgetOpen, setWidgetOpen] = useState(false)
  const [activeBubble, setActiveBubble] = useState<PromptBubbleContent | null>(null)
  const [assistantText, setAssistantText] = useState('Select a prompt to get a simple explanation for this scene.')

  const sceneState = useMemo(() => resolver?.resolveTime(currentTime, accessibilityProfile?.aiProfile ?? null) ?? null, [accessibilityProfile?.aiProfile, currentTime, resolver])
  const prompts = useMemo<PromptQuestion[]>(() => sceneState?.promptBubbles.map((prompt) => ({ id: prompt.id, label: prompt.label, question: prompt.question, explanation: '' })) ?? [], [sceneState])
  const [selectedPromptId, setSelectedPromptId] = useState('')
  const selectedPrompt = prompts.find((prompt) => prompt.id === selectedPromptId) ?? prompts[0]

  useEffect(() => {
    const savedTimestamp = getPlaybackTimestamp(movie)
    setCurrentTime(savedTimestamp)
    void updateScene(savedTimestamp, true)
    setActiveBubble(null)
    setWidgetOpen(false)
  }, [movie, updateScene])

  useEffect(() => { setSelectedPromptId(prompts[0]?.id ?? '') }, [sceneState?.sceneId])
  useEffect(() => { if (sceneState) { setPromptOpen(true); setDrawerOpen(true) } }, [sceneState?.sceneId])
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

  const selectPrompt = useCallback((prompt: PromptQuestion) => {
    if (!sceneState) return
    const answer = answerPrompt(sceneState, prompt.question)
    setSelectedPromptId(prompt.id)
    setPromptOpen(false)
    setDrawerOpen(false)
    setWidgetOpen(false)
    setActiveBubble({ id: `${sceneState.sceneId}:${prompt.id}`, question: prompt.question, title: prompt.label, relationship: sceneState.emotions[0]?.summary ?? '', explanation: answer, anchor: scene?.companionPosition ?? { x: 84, y: 74 }, highlightTarget: false })
    setAssistantText(answer)
    if (settings.voiceAssistance || settings.readPrompts) void speakText({ text: answer, rate: settings.voiceSpeed, volume: Math.min(1, settings.voiceVolume / 100) })
  }, [scene?.companionPosition, sceneState, settings])

  const closeBubbles = useCallback(() => {
    setActiveBubble(null); setWidgetOpen(false); setPromptOpen(false); void stopSpeech()
  }, [])

  if (loading || !movieData) return <div className="movie-experience viewer-page" aria-busy="true" />
  return <main className="movie-experience viewer-page playback-ready">
    <TopBar movie={movieData} onBack={() => { savePlaybackTimestamp(movie, currentTime, duration || totalDuration); onBack() }} onOpenPrompts={() => { setDrawerOpen(false); setPromptOpen(true) }} onOpenDrawer={() => { setPromptOpen(false); setDrawerOpen(true) }} />
    <div className="viewer-layout" style={{ position: 'relative' }}>
      <MoviePlayer movie={movieData} scene={scene} subtitle={sceneState?.subtitle ?? scene?.subtitle ?? ''} playing={playing} muted={muted} volume={volume} currentTime={currentTime} totalTime={duration || totalDuration} onPlayToggle={() => setPlaying((value) => !value)} onMuteToggle={() => setMuted((value) => !value)} onVolumeChange={setVolume} onSeek={(timestamp) => applyTime(timestamp, true)} onTimeChange={applyTime} onDurationChange={setDuration} onSeeking={closeBubbles} onSeekComplete={(timestamp) => applyTime(timestamp, true)} promptOpen={promptOpen} onTogglePromptPanel={() => { setDrawerOpen(false); setPromptOpen((open) => !open) }} onOpenVisualDrawer={() => { setPromptOpen(false); setDrawerOpen(true) }} onOpenPromptPanel={() => { setDrawerOpen(false); setPromptOpen(true) }} onCloseOverlays={closeBubbles} onOpenAccessibilitySettings={onOpenAccessibilitySettings} onCloseBubbles={closeBubbles} reduceMotion={settings.reduceMotion || settings.disableAnimations}
        overlays={<><FloatingBubble content={activeBubble} theme={movieData.companionTheme} reduceMotion={settings.reduceMotion || settings.disableAnimations} visible={Boolean(activeBubble)} onOpenCompanion={() => setWidgetOpen(true)} onClose={() => setActiveBubble(null)} /><CompanionWidget open={widgetOpen} name={profile?.name || 'Lumi'} message={assistantText} theme={movieData.companionTheme} onClose={() => setWidgetOpen(false)} reduceMotion={settings.reduceMotion || settings.disableAnimations} /><PromptPanel open={promptOpen} prompts={prompts} selectedPromptId={selectedPrompt?.id ?? ''} onSelectPrompt={selectPrompt} onClose={() => setPromptOpen(false)} /></>}
        drawerOverlay={<VisualDrawer open={drawerOpen} sceneState={sceneState} onClose={() => setDrawerOpen(false)} />}
      />
    </div>
  </main>
}
