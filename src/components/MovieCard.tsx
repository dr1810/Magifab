import { Clock3, Star } from 'lucide-react'
import type { MovieData } from '../types/movie'

type MovieCardProps = {
  movie: MovieData
  onSelect: (id: MovieData['id']) => void
}

export function MovieCard({ movie, onSelect }: MovieCardProps) {
  return (
    <article className="movie-card" tabIndex={0}>
      <img src={movie.posterUrl} alt={`${movie.title} poster`} className="movie-poster" />
      <div className="movie-content">
        <div className="movie-meta-row">
          <h3>{movie.title}</h3>
          <span className="rating-pill"><Star size={12} /> {movie.rating}</span>
        </div>
        <p>{movie.description}</p>
        <p className="runtime"><Clock3 size={12} /> {movie.runtime}</p>
        <div className="tag-row">
          {movie.accessibilityTags.map((tag) => (
            <span key={tag} className="tag-pill">{tag}</span>
          ))}
        </div>
        <button className="primary-btn" onClick={() => onSelect(movie.id)}>
          Start watching
        </button>
      </div>
    </article>
  )
}
