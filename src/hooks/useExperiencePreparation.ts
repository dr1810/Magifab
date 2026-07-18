import { useEffect, useMemo, useRef, useState } from 'react'
import type { MovieData } from '../types/movie'
import {
  initialMoviePreparationService,
  type PreparationMilestoneId,
  type PreparationProgressEvent,
} from '../services/gpt/InitialMoviePreparationService'

export type PreparationMilestoneState = 'pending' | 'active' | 'complete'
export type PreparationPhase = 'preparing' | 'complete-message' | 'transitioning' | 'ready'

const milestoneIds: PreparationMilestoneId[] = [
  'accessibility-needs', 'companion-profile', 'story-exploration', 'characters', 'relationships',
  'scenes', 'objects', 'accessibility-explanations', 'semantic-memory', 'personalized-guidance',
]

const initialMilestones = () => Object.fromEntries(milestoneIds.map((id) => [id, id === 'accessibility-needs' ? 'active' : 'pending'])) as Record<PreparationMilestoneId, PreparationMilestoneState>
const presentationPause = () => new Promise<void>((resolve) => window.setTimeout(resolve, 140))

/** Connect this hook to backend SSE/WebSocket events by passing them to reportProgress. */
export function useExperiencePreparation(movie: MovieData | null, companionProfileLoading: boolean, companionReady: boolean) {
  const [milestones, setMilestones] = useState(initialMilestones)
  const [phase, setPhase] = useState<PreparationPhase>('preparing')
  const companionReadyRef = useRef(companionReady)
  companionReadyRef.current = companionReady

  const reportProgress = (event: PreparationProgressEvent) => {
    setMilestones((current) => {
      const next = { ...current, [event.milestone]: event.status }
      if (event.status === 'active') {
        const index = milestoneIds.indexOf(event.milestone)
        milestoneIds.slice(0, index).forEach((id) => { if (next[id] !== 'complete') next[id] = 'complete' })
      }
      return next
    })
  }

  useEffect(() => {
    let cancelled = false
    let completionTimer: number | undefined
    let transitionTimer: number | undefined
    setMilestones(initialMilestones())
    setPhase('preparing')

    const prepare = async () => {
      // Accessibility settings are already resolved by AccessibilityProvider. The
      // state still has its own milestone so a remote profile can replace it later.
      reportProgress({ milestone: 'accessibility-needs', status: 'complete' })
      await presentationPause()
      if (companionProfileLoading || !movie) return
      reportProgress({ milestone: 'companion-profile', status: 'active' })
      await presentationPause()
      reportProgress({ milestone: 'companion-profile', status: 'complete' })
      await presentationPause()
      try {
        await initialMoviePreparationService.prepare((event) => {
          if (!cancelled) reportProgress(event)
        })
        // Semantic baseline and backend scene preparation are distinct gates. The
        // viewer keeps the movie paused until both are ready.
        while (!cancelled && !companionReadyRef.current) await presentationPause()
        if (cancelled) return
        setPhase('complete-message')
        completionTimer = window.setTimeout(() => {
          if (cancelled) return
          setPhase('transitioning')
          transitionTimer = window.setTimeout(() => !cancelled && setPhase('ready'), 360)
        }, 1000)
      } catch {
        // Do not open playback unless the opening semantic knowledge is valid.
        // A future backend event stream can retry and report the missing stage.
        if (!cancelled) reportProgress({ milestone: 'personalized-guidance', status: 'active' })
      }
    }
    void prepare()

    return () => {
      cancelled = true
      if (completionTimer) window.clearTimeout(completionTimer)
      if (transitionTimer) window.clearTimeout(transitionTimer)
    }
  }, [movie?.id, companionProfileLoading])

  return useMemo(() => ({ milestones, phase, reportProgress }), [milestones, phase])
}
