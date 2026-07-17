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
import { askCompanion } from './services/assistantService'
import { companionAIService } from './services/ai/CompanionAIService'
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
  const [assistantText, setAssistantText] = useState('Select a prompt to get a simple explanation for this scene.')

  const prompts = scene?.prompts ?? []
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

  const buildPromptBubble = useCallback((sceneData: SceneData, prompt: PromptQuestion, target?: { kind: string; label: string; anchor: { x: number; y: number } }): PromptBubbleContent => {
    const normalizedQuestion = prompt.question.trim().toLowerCase()
    const promptLabel = prompt.label.trim().toLowerCase()
    const questionType = normalizedQuestion.includes('who') || promptLabel.includes('who')
      ? 'Who is that?'
      : normalizedQuestion.includes('what') && normalizedQuestion.includes('happened')
        ? 'What just happened?'
        : normalizedQuestion.includes('why') && normalizedQuestion.includes('sad')
          ? 'Why are they sad?'
          : normalizedQuestion.includes('object') || promptLabel.includes('object')
            ? 'What is this object?'
            : normalizedQuestion.includes('why') && normalizedQuestion.includes('matter')
              ? 'Why does it matter?'
              : 'Why did they do that?'

    const knownCharacter = sceneData.characterList.find((character) => {
      const name = character.name.toLowerCase()
      return normalizedQuestion.includes(name) || prompt.explanation.toLowerCase().includes(name)
    }) ?? sceneData.characterList[0]

    const relationship = knownCharacter
      ? sceneData.relationshipGraph.find((edge) => edge.from.includes(knownCharacter.name) || edge.to.includes(knownCharacter.name))
      : undefined

    const title = target?.label || (questionType === 'Who is that?' && knownCharacter
      ? knownCharacter.name
      : prompt.label)

    return {
      id: `${sceneData.sceneId}:${prompt.id}`,
      question: questionType,
      title,
      relationship: target?.kind === 'object' ? sceneData.highlightObject.reason : questionType === 'Who is that?'
        ? relationship?.label ?? knownCharacter?.role ?? 'Character context'
        : sceneData.emotion,
      explanation: prompt.explanation,
      anchor: target?.anchor ?? { x: sceneData.companionPosition.x, y: Math.max(14, Math.min(76, sceneData.companionPosition.y)) },
      highlightTarget: target?.kind === 'character' || target?.kind === 'object' || questionType === 'Who is that?',
    }
  }, [])

  const selectPrompt = (prompt: PromptQuestion) => {
    if (!scene || !movieData) return
    setSelectedPromptId(prompt.id)
    setPromptOpen(false)
    setDrawerOpen(false)
    setWidgetOpen(false)
    setActiveBubble(null)

    const isCharacterQuestion = /\bwho\b/i.test(prompt.question) || /\bwho\b/i.test(prompt.label)
    const requestId = ++explanationRequestIdRef.current

    if (isCharacterQuestion) {
      const loadingBubble = buildPromptBubble(scene, prompt)
      setActiveBubble({
        ...loadingBubble,
        title: 'Looking closely',
        relationship: '',
        explanation: '',
        highlightTarget: false,
        loading: true,
      })

      void companionAIService.explainCharacter(scene, prompt.question)
        .then((result) => {
          if (requestId !== explanationRequestIdRef.current || currentSceneIdRef.current !== scene.sceneId) return
          const bubble = buildPromptBubble(scene, prompt)
          setActiveBubble({
            ...bubble,
            title: result.character,
            relationship: result.emotion,
            explanation: result.explanation,
          })
          setAssistantText(result.explanation)
          if (settings.voiceAssistance || settings.readPrompts) {
            void speakText({ text: result.explanation, rate: settings.voiceSpeed, volume: Math.min(1, settings.voiceVolume / 100) })
          }
        })
        .catch(() => {
          if (requestId !== explanationRequestIdRef.current || currentSceneIdRef.current !== scene.sceneId) return
          // Preserve the existing local companion path when Supabase is unavailable during development.
          void askCompanion(movieData, scene.timestamp, prompt.question).then((result) => {
            if (requestId !== explanationRequestIdRef.current || currentSceneIdRef.current !== scene.sceneId) return
            setActiveBubble(buildPromptBubble(scene, prompt, result.target))
            setAssistantText(result.answer)
            if (settings.voiceAssistance || settings.readPrompts) {
              void speakText({ text: result.answer, rate: settings.voiceSpeed, volume: Math.min(1, settings.voiceVolume / 100) })
            }
          }).catch(() => {
            setActiveBubble(null)
            setAssistantText('I’m still preparing this explanation. You can try the prompt again in a moment.')
          })
        })
      return
    }

    void askCompanion(movieData, scene.timestamp, prompt.question)
      .then((result) => {
        if (currentSceneIdRef.current !== scene.sceneId) return
        setActiveBubble(buildPromptBubble(scene, prompt, result.target))
        setAssistantText(result.answer)
        if (settings.voiceAssistance || settings.readPrompts) {
          void speakText({
            text: result.answer,
            rate: settings.voiceSpeed,
            volume: Math.min(1, settings.voiceVolume / 100),
          })
        }
      })
      .catch(() => {
        setAssistantText('I’m still preparing this explanation. You can try the prompt again in a moment.')
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
    setActiveBubble(null)
    setWidgetOpen(false)
    setPromptOpen(false)
    void stopSpeech()
  }

  const openCompanionFromBubble = useCallback(() => {
    setWidgetOpen(true)
  }, [])

  const closePromptBubble = useCallback(() => {
    explanationRequestIdRef.current += 1
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
