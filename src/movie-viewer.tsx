import { useEffect, useMemo, useState, type FocusEvent } from 'react'
import { Loader2 } from 'lucide-react'
import { TopBar } from './components/TopBar'
import { MoviePlayer } from './components/MoviePlayer'
import { PromptPanel } from './components/PromptPanel'
import { VisualDrawer } from './components/VisualDrawer'
import { FloatingBubble } from './components/FloatingBubble'
import { CompanionWidget } from './components/CompanionWidget'
import { useAccessibility } from './accessibility-context'
import { useMoviePlayback } from './hooks/useMoviePlayback'
import { useCompanionProfile } from './hooks/useCompanionProfile'
import { askAssistant } from './services/assistantService'
import { speakText, stopSpeech } from './services/speechService'
import type { MovieId, PromptQuestion } from './types/movie'

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
  const [assistantText, setAssistantText] = useState('Select a prompt to get a simple explanation for this scene.')

  const prompts = scene?.prompts ?? []
  const [selectedPromptId, setSelectedPromptId] = useState<string>('')

  useEffect(() => {
    if (prompts.length > 0) {
      setSelectedPromptId((current) => current || prompts[0].id)
    }
  }, [prompts])

  const selectedPrompt = useMemo(
    () => prompts.find((prompt) => prompt.id === selectedPromptId) ?? prompts[0],
    [prompts, selectedPromptId],
  )

  useEffect(() => {
    if (!selectedPrompt || !scene) return
    void askAssistant(scene.sceneId, selectedPrompt.question).then((result) => {
      setAssistantText(result.answer)
      if (settings.voiceAssistance || settings.readPrompts) {
        void speakText({
          text: result.answer,
          rate: settings.voiceSpeed,
          volume: Math.min(1, settings.voiceVolume / 100),
        })
      }
    })

    return () => {
      void stopSpeech()
    }
  }, [scene, selectedPrompt, settings.voiceAssistance, settings.readPrompts, settings.voiceSpeed, settings.voiceVolume])

  const selectPrompt = (prompt: PromptQuestion) => {
    setSelectedPromptId(prompt.id)
    setWidgetOpen(true)
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
        onBack={onBack}
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
            setPromptOpen(false)
            setDrawerOpen(false)
          }}
          onOpenAccessibilitySettings={onOpenAccessibilitySettings}
          reduceMotion={settings.reduceMotion || settings.disableAnimations}
          overlays={
            <>
              <FloatingBubble
                scene={scene}
                theme={movieData.companionTheme}
                reduceMotion={settings.reduceMotion || settings.disableAnimations}
                onClick={() => setWidgetOpen((value) => !value)}
              />
              <CompanionWidget
                open={widgetOpen}
                name={profile?.name || 'Lumi'}
                message={assistantText}
                theme={movieData.companionTheme}
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
