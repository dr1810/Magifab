import { Clock3, Play, RotateCcw, Star } from 'lucide-react'
import type { MovieData } from '../types/movie'
import type { PlaybackSession } from '../services/playbackSessionService'

type MovieCardProps = {
  movie: MovieData
  playbackSession: PlaybackSession | null
  onSelect: (id: MovieData['id'], startOver?: boolean) => void
}

function formatTimestamp(timestamp: number) {
  const seconds = Math.max(0, Math.floor(timestamp))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function MovieCard({ movie, playbackSession, onSelect }: MovieCardProps) {
  return (
    <article className="movie-card" tabIndex={0} aria-label={`${movie.title}, ${movie.genre}`}>
      <img src={movie.posterUrl} alt={`${movie.title} poster`} className="movie-poster" />
      <div className="movie-content">
        <div className="movie-meta-row">
          <h3>{movie.title}</h3>
          <span className="rating-pill"><Star size={12} /> {movie.rating}</span>
        </div>
        <p>{movie.description}</p>
        <p className="runtime"><Clock3 size={12} /> {movie.runtime} <span aria-hidden="true">·</span> {movie.genre}</p>
        <div className="tag-row">
          {movie.accessibilityTags.map((tag) => (
            <span key={tag} className="tag-pill">{tag}</span>
          ))}
        </div>
        {playbackSession ? (
          <div className="movie-resume-actions" aria-label={`Continue ${movie.title}`}>
            <button className="primary-btn" onClick={() => onSelect(movie.id)}><Play size={15} fill="currentColor" /> Resume ({formatTimestamp(playbackSession.timestamp)})</button>
            <button className="chip-btn" onClick={() => onSelect(movie.id, true)}><RotateCcw size={15} /> Start Over</button>
          </div>
        ) : <button className="primary-btn" onClick={() => onSelect(movie.id)}>Watch with Magifab</button>}
      </div>
    </article>
  )
}
