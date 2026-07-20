import { ArrowLeft, LayoutPanelTop, Settings2 } from 'lucide-react'
import type { MovieData } from '../types/movie'

type TopBarProps = {
  movie: MovieData
  onBack: () => void
  onOpenDrawer: () => void
}

export function TopBar({ movie, onBack, onOpenDrawer }: TopBarProps) {
  return (
    <header className="top-bar">
      <div className="left-cluster">
        <button className="ghost-btn" onClick={onBack} aria-label="Back to movie selector">
          <ArrowLeft size={16} />
          Back
        </button>
        <div>
          <p className="eyebrow">Now Playing</p>
          <h2>{movie.title}</h2>
        </div>
      </div>
      <div className="right-cluster">
        <button className="ghost-btn" onClick={onOpenDrawer}>
          <LayoutPanelTop size={16} /> Story Companion
        </button>
        <button className="ghost-btn" aria-label="Viewer settings">
          <Settings2 size={16} />
        </button>
      </div>
    </header>
  )
}
