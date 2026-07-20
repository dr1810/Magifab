import { useCallback, useState } from 'react'

export type OverlaySurface = 'prompt-guide' | 'prompt-card' | 'story-companion' | 'assistant' | 'aster'

/** Keeps every viewer overlay mutually exclusive and closes it from one place. */
export function useOverlayManager() {
  const [activeSurface, setActiveSurface] = useState<OverlaySurface | null>(null)

  const open = useCallback((surface: OverlaySurface) => setActiveSurface(surface), [])
  const close = useCallback((surface?: OverlaySurface) => {
    setActiveSurface((current) => !surface || current === surface ? null : current)
  }, [])

  return {
    activeSurface,
    isOpen: (surface: OverlaySurface) => activeSurface === surface,
    open,
    close,
    closeAll: useCallback(() => setActiveSurface(null), []),
  }
}
