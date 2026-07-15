import { useEffect, useState } from 'react'
import { getMovies } from '../services/movieService'
import type { MovieData } from '../types/movie'

export function useMovies() {
  const [movies, setMovies] = useState<MovieData[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true

    void getMovies().then((response) => {
      if (!mounted) return
      setMovies(response)
      setLoading(false)
    })

    return () => {
      mounted = false
    }
  }, [])

  return { movies, loading }
}
