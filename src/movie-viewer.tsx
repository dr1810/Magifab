import { useEffect, useMemo, useState, type FocusEvent, type MouseEvent } from 'react'
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
}

export function MovieViewer({ movie, onBack }: MovieViewerProps) {
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
        onOpenPrompts={() => setPromptOpen(true)}
        onOpenDrawer={() => setDrawerOpen(true)}
      />

      <div
        className="viewer-layout"
        style={{ position: 'relative' }}
        onMouseMove={(event: MouseEvent<HTMLDivElement>) => {
          const target = event.target
          if (target instanceof Element && !target.closest('.visual-drawer, .drawer-hover-trigger, .hover-zone.bottom')) setDrawerOpen(false)
        }}
      >
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
          onPromptZoneHover={() => setPromptOpen(true)}
          onDrawerZoneHover={() => setDrawerOpen(true)}
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
            <>
              <button
                type="button"
                className="drawer-hover-trigger"
                aria-label="Open visual aids drawer"
                onFocus={() => setDrawerOpen(true)}
                onClick={() => setDrawerOpen(true)}
                style={{ position: 'absolute', zIndex: 45, bottom: 0, left: 0, width: '100%', height: 18, opacity: 0 }}
              />
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
            </>
          }
        />
      </div>
    </main>
  )
}
