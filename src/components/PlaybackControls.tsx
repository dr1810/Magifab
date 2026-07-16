import { Maximize2, Minimize2, Pause, Play, Volume2, VolumeX } from 'lucide-react'

type PlaybackControlsProps = {
  playing: boolean
  onPlayToggle: () => void
  muted: boolean
  onMuteToggle: () => void
  volume: number
  onVolumeChange: (value: number) => void
  currentTime: number
  totalTime: number
  onSeek: (value: number) => void
  isFullscreen: boolean
  onFullscreen: () => void
}

function formatTime(value: number) {
  const safe = Math.max(0, Math.floor(value))
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, '0')}`
}

export function PlaybackControls({
  playing,
  onPlayToggle,
  muted,
  onMuteToggle,
  volume,
  onVolumeChange,
  currentTime,
  totalTime,
  onSeek,
  isFullscreen,
  onFullscreen,
}: PlaybackControlsProps) {
  return (
    <section className="playback-controls" aria-label="Playback controls">
      <input
        type="range"
        min={0}
        max={Math.max(totalTime, 1)}
        value={Math.min(currentTime, totalTime)}
        onChange={(event) => onSeek(Number(event.target.value))}
        aria-label="Seek"
      />
      <div className="controls-row">
        <div className="left-cluster">
          <button className="chip-btn" onClick={onPlayToggle}>
            {playing ? <Pause size={15} /> : <Play size={15} />} {playing ? 'Pause' : 'Play'}
          </button>
          <button className="chip-btn" onClick={onMuteToggle}>
            {muted ? <VolumeX size={15} /> : <Volume2 size={15} />} {muted ? 'Muted' : 'Volume'}
          </button>
          <input
            type="range"
            min={0}
            max={100}
            value={volume}
            onChange={(event) => onVolumeChange(Number(event.target.value))}
            aria-label="Volume"
          />
        </div>
        <div className="right-cluster">
          <span>{formatTime(currentTime)} / {formatTime(totalTime)}</span>
          <button
            className="chip-btn"
            onClick={onFullscreen}
            title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
            aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
          >
            {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />} {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
          </button>
        </div>
      </div>
    </section>
  )
}
