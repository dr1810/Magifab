import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react'
import type { ReactNode } from 'react'
import type { MovieData, SceneData } from '../types/movie'
import { SubtitleOverlay } from './SubtitleOverlay'
import { PlaybackControls } from './PlaybackControls'
import { captureVideoFrame, type CapturedVideoFrame } from '../services/ai/VideoFrameCaptureService'

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
  onSeeking?: () => void
  onSeekComplete?: (timestamp: number) => void
  onVideoFrameCaptureReady?: (capture: (() => Promise<CapturedVideoFrame>) | null) => void
  promptOpen: boolean
  onTogglePromptPanel: () => void
  onOpenVisualDrawer: () => void
  onOpenPromptPanel: () => void
  onCloseOverlays: () => void
  onOpenAccessibilitySettings: () => void
  onCloseBubbles: () => void
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
  onSeeking,
  onSeekComplete,
  onVideoFrameCaptureReady,
  promptOpen,
  onTogglePromptPanel,
  onOpenVisualDrawer,
  onOpenPromptPanel,
  onCloseOverlays,
  onOpenAccessibilitySettings,
  onCloseBubbles,
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
  const pendingResumeTimestampRef = useRef<number | null>(null)
  const wasPlayingBeforeSeekRef = useRef(false)
  const isSeekingRef = useRef(false)
  const lastReportedTimeRef = useRef(0)
  const eventStateRef = useRef({ currentTime, playing, onTimeChange, onDurationChange, onSeekComplete, onSeeking, onPlayToggle })
  eventStateRef.current = { currentTime, playing, onTimeChange, onDurationChange, onSeekComplete, onSeeking, onPlayToggle }

  const logPlayback = (event: string, details: Record<string, unknown>) => {
    if (import.meta.env.DEV) console.debug(`[MagiFab playback] ${event}`, { movieId: movie.id, ...details })
  }

  const applyPendingResume = (video: HTMLVideoElement, phase: string) => {
    const timestamp = pendingResumeTimestampRef.current
    if (timestamp === null || timestamp <= 0) return
    pendingResumeTimestampRef.current = timestamp
    logPlayback('applying resume timestamp', { phase, requestedTimestamp: timestamp, currentTimeBefore: video.currentTime, readyState: video.readyState })
    video.currentTime = timestamp
  }

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

  useEffect(() => {
    const video = videoRef.current
    if (!video || currentTime <= 0 || Math.abs(video.currentTime - currentTime) < .35) return
    if (video.readyState < HTMLMediaElement.HAVE_METADATA) {
      pendingResumeTimestampRef.current = currentTime
      logPlayback('queued resume before metadata', { requestedTimestamp: currentTime, currentTimeBefore: video.currentTime, readyState: video.readyState })
      return
    }
    pendingResumeTimestampRef.current = currentTime
    applyPendingResume(video, 'react-state')
  }, [currentTime, movie.id])

  useEffect(() => {
    logPlayback('video source mounted', { videoSrc: movie.videoSrc, currentTime })
  }, [movie.id, movie.videoSrc])

  useEffect(() => () => {
    clearClickTimer()
    if (feedbackTimerRef.current !== null) window.clearTimeout(feedbackTimerRef.current)
  }, [])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const handleTimeUpdate = () => {
      const nextTime = video.currentTime
      if (nextTime >= lastReportedTimeRef.current && nextTime - lastReportedTimeRef.current < 0.1) return
      lastReportedTimeRef.current = nextTime
      eventStateRef.current.onTimeChange(nextTime)
    }
    const beginSeek = () => {
      if (isSeekingRef.current) return
      isSeekingRef.current = true
      wasPlayingBeforeSeekRef.current = eventStateRef.current.playing && !video.ended
      eventStateRef.current.onSeeking?.()
    }
    const handleLoadedMetadata = () => {
      logPlayback('loadedmetadata', { duration: video.duration, currentTimeBefore: video.currentTime, pendingResumeTimestamp: pendingResumeTimestampRef.current, requestedCurrentTime: eventStateRef.current.currentTime })
      eventStateRef.current.onDurationChange(video.duration)
      applyPendingResume(video, 'loadedmetadata')
    }
    const handleCanPlay = () => applyPendingResume(video, 'canplay')
    const handleSeeked = () => {
      logPlayback('resume seeked', { currentTimeAfter: video.currentTime, pendingResumeTimestamp: pendingResumeTimestampRef.current })
      if (pendingResumeTimestampRef.current !== null && Math.abs(video.currentTime - pendingResumeTimestampRef.current) < .35) {
        pendingResumeTimestampRef.current = null
      }
      isSeekingRef.current = false
      lastReportedTimeRef.current = video.currentTime
      eventStateRef.current.onSeekComplete?.(video.currentTime)
      if (wasPlayingBeforeSeekRef.current && eventStateRef.current.playing) void video.play().catch(() => undefined)
      wasPlayingBeforeSeekRef.current = false
    }
    const handleEnded = () => eventStateRef.current.onPlayToggle()
    const handleError = () => setVideoFailed(true)

    video.addEventListener('timeupdate', handleTimeUpdate)
    video.addEventListener('seeking', beginSeek)
    video.addEventListener('seeked', handleSeeked)
    video.addEventListener('loadedmetadata', handleLoadedMetadata)
    video.addEventListener('canplay', handleCanPlay)
    video.addEventListener('ended', handleEnded)
    video.addEventListener('error', handleError)

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate)
      video.removeEventListener('seeking', beginSeek)
      video.removeEventListener('seeked', handleSeeked)
      video.removeEventListener('loadedmetadata', handleLoadedMetadata)
      video.removeEventListener('canplay', handleCanPlay)
      video.removeEventListener('ended', handleEnded)
      video.removeEventListener('error', handleError)
    }
  }, [])

  useEffect(() => {
    onVideoFrameCaptureReady?.(() => captureVideoFrame(videoRef.current))
    return () => onVideoFrameCaptureReady?.(null)
  }, [onVideoFrameCaptureReady])

  const seek = (value: number) => {
    const video = videoRef.current
    if (video && !isSeekingRef.current) {
      isSeekingRef.current = true
      wasPlayingBeforeSeekRef.current = playing && !video.ended
      onSeeking?.()
    }
    if (video) {
      pendingResumeTimestampRef.current = null
      lastReportedTimeRef.current = value
      video.currentTime = value
    }
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
          crossOrigin="anonymous"
          src={movie.videoSrc}
          poster={movie.posterUrl}
          playsInline
          preload="metadata"
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
        onCloseBubbles={onCloseBubbles}
        isFullscreen={isFullscreen}
        onFullscreen={toggleFullscreen}
      />
    </section>
  )
}
