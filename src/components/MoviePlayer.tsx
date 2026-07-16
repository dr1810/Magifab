import { useEffect, useRef, useState } from 'react'
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
  onPromptZoneHover: () => void
  onOpenVisualDrawer: () => void
  overlays: ReactNode
  drawerOverlay?: ReactNode
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
  onPromptZoneHover,
  onOpenVisualDrawer,
  overlays,
  drawerOverlay,
}: MoviePlayerProps) {
  const rootRef = useRef<HTMLDivElement | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [videoFailed, setVideoFailed] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)

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
        >
          {movie.subtitleSrc && <track kind="captions" src={movie.subtitleSrc} srcLang="en" label="English" default />}
        </video>
        {videoFailed && <div className="video-notice" role="status">This browser cannot play this video format. Try Sprite Fright, or open Big Buck Bunny in a browser that supports its MOV codec.</div>}
        {overlays}
        <SubtitleOverlay subtitle={scene.subtitle} />

        <div className="hover-zone right" onMouseEnter={onPromptZoneHover} aria-hidden="true" />
      </div>

      <PlaybackControls
        playing={playing}
        onPlayToggle={onPlayToggle}
        muted={muted}
        onMuteToggle={onMuteToggle}
        volume={volume}
        onVolumeChange={onVolumeChange}
        currentTime={currentTime}
        totalTime={totalTime}
        onSeek={seek}
        onOpenVisualDrawer={onOpenVisualDrawer}
        isFullscreen={isFullscreen}
        onFullscreen={toggleFullscreen}
      />
      {drawerOverlay}
    </section>
  )
}
