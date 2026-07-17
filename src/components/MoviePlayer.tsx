import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react'
import type { ReactNode } from 'react'
import type { MovieData, SceneData } from '../types/movie'
import { SubtitleOverlay } from './SubtitleOverlay'
import { PlaybackControls } from './PlaybackControls'

type MoviePlayerProps = {
  movie: MovieData
  scene: SceneData
  playing: boolean
  muted: boolean
  volume: number
  currentTime: number
  totalTime: number
  onPlayToggle: () => void
  onMuteToggle: () => void
  onVolumeChange: (value: number) => void
  onSeek: (value: number) => void
  onTimeChange: (value: number) => void
  onDurationChange: (value: number) => void
  promptOpen: boolean
  onTogglePromptPanel: () => void
  onOpenVisualDrawer: () => void
  onOpenPromptPanel: () => void
  onCloseOverlays: () => void
  onOpenAccessibilitySettings: () => void
  overlays: ReactNode
  drawerOverlay?: ReactNode
  reduceMotion: boolean
}

export function MoviePlayer({
  movie,
  scene,
  playing,
  muted,
  volume,
  currentTime,
  totalTime,
  onPlayToggle,
  onMuteToggle,
  onVolumeChange,
  onSeek,
  onTimeChange,
  onDurationChange,
  promptOpen,
  onTogglePromptPanel,
  onOpenVisualDrawer,
  onOpenPromptPanel,
  onCloseOverlays,
  onOpenAccessibilitySettings,
  overlays,
  drawerOverlay,
  reduceMotion,
}: MoviePlayerProps) {
  const rootRef = useRef<HTMLDivElement | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [videoFailed, setVideoFailed] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [playbackFeedback, setPlaybackFeedback] = useState<'play' | 'pause' | null>(null)
  const clickTimerRef = useRef<number | null>(null)
  const feedbackTimerRef = useRef<number | null>(null)

  const clearClickTimer = () => {
    if (clickTimerRef.current !== null) {
      window.clearTimeout(clickTimerRef.current)
      clickTimerRef.current = null
    }
  }

  const showPlaybackFeedback = (nextPlaying: boolean) => {
    if (feedbackTimerRef.current !== null) window.clearTimeout(feedbackTimerRef.current)
    setPlaybackFeedback(nextPlaying ? 'play' : 'pause')
    feedbackTimerRef.current = window.setTimeout(() => setPlaybackFeedback(null), 650)
  }

  const togglePlayback = () => {
    showPlaybackFeedback(!playing)
    onPlayToggle()
  }

  useEffect(() => {
    const syncFullscreen = () => {
      setIsFullscreen(document.fullscreenElement === rootRef.current)
    }

    syncFullscreen()
    document.addEventListener('fullscreenchange', syncFullscreen)
    return () => document.removeEventListener('fullscreenchange', syncFullscreen)
  }, [])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    if (playing) void video.play().catch(() => undefined)
    else video.pause()
  }, [playing, movie.videoSrc])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    video.muted = muted
    video.volume = Math.max(0, Math.min(1, volume / 100))
  }, [muted, volume])

  useEffect(() => () => {
    clearClickTimer()
    if (feedbackTimerRef.current !== null) window.clearTimeout(feedbackTimerRef.current)
  }, [])

  const seek = (value: number) => {
    const video = videoRef.current
    if (video) video.currentTime = value
    onSeek(value)
  }

  const toggleFullscreen = () => {
    if (document.fullscreenElement === rootRef.current) {
      void document.exitFullscreen()
      return
    }
    if (rootRef.current?.requestFullscreen) {
      void rootRef.current.requestFullscreen()
    }
  }

  const isInteractiveTarget = (target: EventTarget | null) => {
    if (!(target instanceof Element)) return false
    return Boolean(target.closest('button, input, select, textarea, [contenteditable="true"], .prompt-panel, .visual-drawer, .companion-widget, .floating-bubble'))
  }

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const playerIsActive = document.fullscreenElement === rootRef.current || rootRef.current?.contains(document.activeElement)
      if (!playerIsActive) return

      if (event.key === 'Escape') {
        if (document.fullscreenElement === rootRef.current) {
          void document.exitFullscreen()
        } else {
          onCloseOverlays()
        }
        return
      }

      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey || isInteractiveTarget(event.target)) return

      switch (event.key.toLowerCase()) {
        case ' ':
        case 'spacebar':
          event.preventDefault()
          togglePlayback()
          break
        case 'arrowleft':
          event.preventDefault()
          seek(Math.max(0, currentTime - 10))
          break
        case 'arrowright':
          event.preventDefault()
          seek(Math.min(totalTime, currentTime + 10))
          break
        case 'arrowup':
          event.preventDefault()
          if (muted) onMuteToggle()
          onVolumeChange(Math.min(100, volume + 5))
          break
        case 'arrowdown':
          event.preventDefault()
          if (muted) onMuteToggle()
          onVolumeChange(Math.max(0, volume - 5))
          break
        case 'm':
          event.preventDefault()
          onMuteToggle()
          break
        case 'f':
          event.preventDefault()
          toggleFullscreen()
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [currentTime, muted, onCloseOverlays, onMuteToggle, onPlayToggle, onVolumeChange, playing, totalTime, volume])

  const handleVideoClick = () => {
    clearClickTimer()
    clickTimerRef.current = window.setTimeout(() => {
      togglePlayback()
      clickTimerRef.current = null
    }, 220)
  }

  const handleVideoDoubleClick = () => {
    clearClickTimer()
    toggleFullscreen()
  }

  return (
    <section className="movie-player" ref={rootRef}>
      <div className="player-canvas" aria-label={`${movie.title} video player`}>
        <video
          ref={videoRef}
          className="movie-video"
          src={movie.videoSrc}
          poster={movie.posterUrl}
          playsInline
          preload="metadata"
          onTimeUpdate={(event) => onTimeChange(event.currentTarget.currentTime)}
          onLoadedMetadata={(event) => onDurationChange(event.currentTarget.duration)}
          onEnded={onPlayToggle}
          onError={() => setVideoFailed(true)}
          aria-label={`Playing ${movie.title}`}
          tabIndex={0}
          onPointerDown={() => videoRef.current?.focus()}
          onClick={handleVideoClick}
          onDoubleClick={handleVideoDoubleClick}
        >
          {movie.subtitleSrc && <track kind="captions" src={movie.subtitleSrc} srcLang="en" label="English" default />}
        </video>
        <div className={`playback-feedback ${playbackFeedback ? 'visible' : ''} ${reduceMotion ? 'reduced-motion' : ''}`} aria-live="polite" aria-label={playbackFeedback === 'play' ? 'Playing' : playbackFeedback === 'pause' ? 'Paused' : undefined}>
          {playbackFeedback === 'play' && <Play fill="currentColor" size={36} aria-hidden="true" />}
          {playbackFeedback === 'pause' && <Pause fill="currentColor" size={36} aria-hidden="true" />}
        </div>
        {videoFailed && <div className="video-notice" role="status">This browser cannot play this video format. Try Sprite Fright, or open Big Buck Bunny in a browser that supports its MOV codec.</div>}
        {overlays}
        {drawerOverlay}
        <SubtitleOverlay subtitle={scene.subtitle} />
        <button
          type="button"
          className="prompt-sidebar-toggle"
          aria-label={promptOpen ? 'Collapse Prompt Panel' : 'Expand Prompt Panel'}
          aria-controls="prompt-panel"
          aria-expanded={promptOpen}
          onClick={onTogglePromptPanel}
        >
          {promptOpen ? <ChevronRight size={18}/> : <ChevronLeft size={18}/>} 
        </button>
      </div>

      <PlaybackControls
        playing={playing}
        onPlayToggle={togglePlayback}
        muted={muted}
        onMuteToggle={onMuteToggle}
        volume={volume}
        onVolumeChange={onVolumeChange}
        currentTime={currentTime}
        totalTime={totalTime}
        onSeek={seek}
        onOpenVisualDrawer={onOpenVisualDrawer}
        onOpenPromptPanel={onOpenPromptPanel}
        onOpenAccessibilitySettings={onOpenAccessibilitySettings}
        isFullscreen={isFullscreen}
        onFullscreen={toggleFullscreen}
      />
    </section>
  )
}
