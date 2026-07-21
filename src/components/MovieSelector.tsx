import { ArrowLeft, Loader2, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useMovies } from '../hooks/useMovies'
import type { MovieId } from '../types/movie'
import { MovieCard } from './MovieCard'
import { getPlaybackSession } from '../services/playbackSessionService'
import { moviePreprocessingBackendService, type ProcessingState } from '../services/backend/MoviePreprocessingBackendService'
import { useAccessibilityProfile } from '../hooks/useAccessibilityProfile'
import { companionProfilePayload } from '../services/backend/profilePayload'

type MovieSelectorProps = {
  onBack: () => void
  onSelect: (id: MovieId, startOver?: boolean) => void
}

export function MovieSelector({ onBack, onSelect }: MovieSelectorProps) {
  const { movies, loading } = useMovies()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [uploading, setUploading] = useState(false)
  const [processing, setProcessing] = useState<(ProcessingState & { movieId: string }) | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const { profile } = useAccessibilityProfile()

  useEffect(() => {
    if (!processing || processing.status === 'complete' || processing.status === 'failed') return
    const timer = window.setInterval(() => {
      void moviePreprocessingBackendService.status(processing.movieId).then((state) => setProcessing({ ...state, movieId: processing.movieId })).catch((error: unknown) => setUploadError(error instanceof Error ? error.message : 'Unable to check movie preparation.'))
    }, 3_000)
    return () => window.clearInterval(timer)
  }, [processing?.movieId, processing?.status])

  useEffect(() => {
    if (processing?.status === 'complete') onSelect(processing.movieId)
  }, [onSelect, processing?.movieId, processing?.status])

  const uploadMovie = async (file: File) => {
    setUploading(true)
    setUploadError(null)
    try {
      const result = await moviePreprocessingBackendService.processMovie(file, companionProfilePayload(profile), file.name.replace(/\.[^.]+$/, ''))
      const state = await moviePreprocessingBackendService.status(result.movie_id)
      setProcessing({ ...state, movieId: result.movie_id })
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Unable to upload this movie.')
    } finally {
      setUploading(false)
    }
  }

  const progress = processing ? `${processing.percentage}% · ${processing.progress}` : ''

  return (
    <main className="movie-experience selector-page">
      <div className="screen-header">
        <button className="ghost-btn" onClick={onBack}><ArrowLeft size={16} /> Back</button>
        <h1>Select a Movie</h1>
        <button className="primary-btn" onClick={() => fileInputRef.current?.click()} disabled={uploading || Boolean(processing && !['complete', 'failed'].includes(processing.status))}><Upload size={15} /> {uploading ? 'Uploading…' : 'Upload a movie'}</button>
        <input ref={fileInputRef} className="sr-only" type="file" accept="video/*" onChange={(event) => { const file = event.target.files?.[0]; event.currentTarget.value = ''; if (file) void uploadMovie(file) }} />
      </div>
      <p className="selector-subtitle">Choose a curated story or upload a movie for scene-by-scene guidance.</p>
      {(uploading || processing || uploadError) && <section className="loading" aria-live="polite">
        {uploading || (processing && !['complete', 'failed'].includes(processing.status)) ? <Loader2 className="spin" /> : null}
        <div>
          <strong>{uploadError ? 'Movie upload needs attention' : processing?.status === 'failed' ? 'Movie preparation failed' : processing?.status === 'complete' ? 'Movie ready — opening it now' : uploading ? 'Uploading your movie' : 'Creating your MagiFab companion experience…'}</strong>
          <p>{uploadError ?? processing?.error ?? (progress || 'MagiFab is building stored accessibility guidance. You can leave this page open while it works.')}</p>
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
