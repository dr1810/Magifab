import { MovieViewer } from '../movie-viewer'
import type { MovieId } from '../types/movie'

type WatchPageProps = {
  movie: MovieId
  onBack: () => void
}

export function WatchPage({ movie, onBack }: WatchPageProps) {
  return <MovieViewer movie={movie} onBack={onBack} />
}
