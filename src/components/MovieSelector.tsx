import { ArrowLeft, Loader2, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useMovies } from '../hooks/useMovies'
import type { MovieId } from '../types/movie'
import { MovieCard } from './MovieCard'
import { getPlaybackSession } from '../services/playbackSessionService'
import { moviePreprocessingBackendService, type MoviePreprocessingStatus } from '../services/backend/MoviePreprocessingBackendService'

type MovieSelectorProps = {
  onBack: () => void
  onSelect: (id: MovieId, startOver?: boolean) => void
}

export function MovieSelector({ onBack, onSelect }: MovieSelectorProps) {
  const { movies, loading } = useMovies()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [uploading, setUploading] = useState(false)
  const [processing, setProcessing] = useState<MoviePreprocessingStatus | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  useEffect(() => {
    const movie = processing?.movie
    if (!movie || movie.status === 'completed' || movie.status === 'failed') return
    const timer = window.setInterval(() => {
      void moviePreprocessingBackendService.status(movie.id).then(setProcessing).catch((error: unknown) => setUploadError(error instanceof Error ? error.message : 'Unable to check movie preparation.'))
    }, 3_000)
    return () => window.clearInterval(timer)
  }, [processing?.movie.id, processing?.movie.status])

  useEffect(() => {
    if (processing?.movie.status === 'completed') onSelect(processing.movie.id)
  }, [onSelect, processing?.movie.id, processing?.movie.status])

  const uploadMovie = async (file: File) => {
    setUploading(true)
    setUploadError(null)
    try {
      const result = await moviePreprocessingBackendService.processMovie(file, file.name.replace(/\.[^.]+$/, ''))
      const status = await moviePreprocessingBackendService.status(result.movie_id)
      setProcessing(status)
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Unable to upload this movie.')
    } finally {
      setUploading(false)
    }
  }

  const counts = processing?.chunk_counts
  const progress = counts ? `${counts.completed ?? 0} of ${(counts.completed ?? 0) + (counts.pending ?? 0) + (counts.processing ?? 0) + (counts.failed ?? 0)} scenes ready` : ''

  return (
    <main className="movie-experience selector-page">
      <div className="screen-header">
        <button className="ghost-btn" onClick={onBack}><ArrowLeft size={16} /> Back</button>
        <h1>Select a Movie</h1>
        <button className="primary-btn" onClick={() => fileInputRef.current?.click()} disabled={uploading || processing?.movie.status === 'processing'}><Upload size={15} /> {uploading ? 'Uploading…' : 'Upload a movie'}</button>
        <input ref={fileInputRef} className="sr-only" type="file" accept="video/*" onChange={(event) => { const file = event.target.files?.[0]; event.currentTarget.value = ''; if (file) void uploadMovie(file) }} />
      </div>
      <p className="selector-subtitle">Choose a curated story or upload a movie for scene-by-scene guidance.</p>
      {(uploading || processing || uploadError) && <section className="loading" aria-live="polite">
        {uploading || processing?.movie.status === 'uploaded' || processing?.movie.status === 'processing' ? <Loader2 className="spin" /> : null}
        <div>
          <strong>{uploadError ? 'Movie upload needs attention' : processing?.movie.status === 'failed' ? 'Movie preparation failed' : processing?.movie.status === 'completed' ? 'Movie ready — opening it now' : uploading ? 'Uploading your movie' : 'Preparing your movie'}</strong>
          <p>{uploadError ?? processing?.movie.error_message ?? (progress || 'MagiFab is building stored accessibility guidance. You can leave this page open while it works.')}</p>
        </div>
      </section>}
      {loading ? (
        <div className="loading"><Loader2 className="spin" /> Loading movies...</div>
      ) : (
        <section className="movie-grid" aria-label="Movie choices">
          {movies.slice(0, 2).map((movie) => (
            <MovieCard key={movie.id} movie={movie} playbackSession={getPlaybackSession(movie.id)} onSelect={onSelect} />
          ))}
        </section>
      )}
    </main>
  )
}
