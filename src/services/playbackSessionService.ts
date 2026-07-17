import type { MovieId } from '../types/movie'

export type PlaybackSession = { timestamp: number; duration: number; progress: number; updatedAt: string }
const keyFor = (movieId: MovieId) => `magifab-playback-session:${movieId}`

/** Emits temporary development diagnostics for resume-state verification. */
function logPlayback(event: string, details: Record<string, unknown>): void {
  if (import.meta.env.DEV) console.debug(`[MagiFab playback] ${event}`, details)
}

/** Persists lightweight per-movie playback state without touching semantic movie analysis. */
export function getPlaybackTimestamp(movieId: MovieId): number {
  try {
    const session = JSON.parse(localStorage.getItem(keyFor(movieId)) ?? 'null') as PlaybackSession | null
    const timestamp = Math.max(0, session?.timestamp ?? 0)
    logPlayback('loaded timestamp', { movieId, timestamp, key: keyFor(movieId) })
    return timestamp
  } catch {
    return 0
  }
}

/** Gets resumable playback data when a movie has progressed beyond its opening frame. */
export function getPlaybackSession(movieId: MovieId): PlaybackSession | null {
  try {
    const session = JSON.parse(localStorage.getItem(keyFor(movieId)) ?? 'null') as PlaybackSession | null
    return session && session.timestamp > 0 ? session : null
  } catch {
    return null
  }
}

/** Saves the latest playback timestamp for Resume Movie. */
export function savePlaybackTimestamp(movieId: MovieId, timestamp: number, duration = 0): void {
  const safeTimestamp = Math.max(0, timestamp)
  const safeDuration = Math.max(0, duration)
  localStorage.setItem(keyFor(movieId), JSON.stringify({ timestamp: safeTimestamp, duration: safeDuration, progress: safeDuration ? Math.min(1, safeTimestamp / safeDuration) : 0, updatedAt: new Date().toISOString() } satisfies PlaybackSession))
  logPlayback('saved timestamp', { movieId, timestamp: safeTimestamp, duration: safeDuration, key: keyFor(movieId) })
}

/** Resets only playback position for Start Over; semantic memory and profile data remain intact. */
export function resetPlaybackTimestamp(movieId: MovieId): void {
  savePlaybackTimestamp(movieId, 0)
}
