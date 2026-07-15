import { useRef } from 'react'
import type { ReactNode } from 'react'
import type { SceneData } from '../types/movie'
import { SubtitleOverlay } from './SubtitleOverlay'
import { PlaybackControls } from './PlaybackControls'

type MoviePlayerProps = {
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
  onFullscreen: () => void
  onPromptZoneHover: () => void
  onDrawerZoneHover: () => void
  overlays: ReactNode
}

export function MoviePlayer({
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
  onFullscreen,
  onPromptZoneHover,
  onDrawerZoneHover,
  overlays,
}: MoviePlayerProps) {
  const rootRef = useRef<HTMLDivElement | null>(null)

  return (
    <section className="movie-player" ref={rootRef}>
      <div className="player-canvas" role="img" aria-label="Movie playback canvas">
        <div className="scene-backdrop" />
        <div className="scene-highlight" />
        {overlays}
        <SubtitleOverlay subtitle={scene.subtitle} />

        <div className="hover-zone right" onMouseEnter={onPromptZoneHover} aria-hidden="true" />
        <div className="hover-zone bottom" onMouseEnter={onDrawerZoneHover} aria-hidden="true" />
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
        onSeek={onSeek}
        onFullscreen={() => {
          if (rootRef.current?.requestFullscreen) {
            void rootRef.current.requestFullscreen()
            return
          }
          onFullscreen()
        }}
      />
    </section>
  )
}
