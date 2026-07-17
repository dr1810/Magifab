import { ArrowLeft, Loader2 } from 'lucide-react'
import { useMovies } from '../hooks/useMovies'
import type { MovieId } from '../types/movie'
import { MovieCard } from './MovieCard'
import { getPlaybackSession } from '../services/playbackSessionService'

type MovieSelectorProps = {
  onBack: () => void
  onSelect: (id: MovieId, startOver?: boolean) => void
}

export function MovieSelector({ onBack, onSelect }: MovieSelectorProps) {
  const { movies, loading } = useMovies()

  return (
    <main className="movie-experience selector-page">
      <div className="screen-header">
        <button className="ghost-btn" onClick={onBack}><ArrowLeft size={16} /> Back</button>
        <h1>Select a Movie</h1>
      </div>
      <p className="selector-subtitle">Two curated stories, each with scene-by-scene guidance and companion themes.</p>
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
