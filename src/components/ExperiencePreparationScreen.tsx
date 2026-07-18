import { Check } from 'lucide-react'
import type { PreparationMilestoneId } from '../services/gpt/InitialMoviePreparationService'
import type { PreparationMilestoneState, PreparationPhase } from '../hooks/useExperiencePreparation'

type ExperiencePreparationScreenProps = {
  milestones: Record<PreparationMilestoneId, PreparationMilestoneState>
  phase: Exclude<PreparationPhase, 'ready'>
  reduceMotion?: boolean
}

const items: Array<{ id: PreparationMilestoneId; label: string }> = [
  { id: 'accessibility-needs', label: 'Understanding your accessibility needs' },
  { id: 'companion-profile', label: 'Preparing your companion' },
  { id: 'story-exploration', label: 'Exploring the story' },
  { id: 'characters', label: 'Discovering important characters' },
  { id: 'relationships', label: 'Understanding relationships' },
  { id: 'scenes', label: 'Mapping important scenes' },
  { id: 'objects', label: 'Learning important objects' },
  { id: 'accessibility-explanations', label: 'Preparing accessibility explanations' },
  { id: 'semantic-memory', label: 'Building semantic movie memory' },
  { id: 'personalized-guidance', label: 'Preparing personalized guidance...' },
]

export function ExperiencePreparationScreen({ milestones, phase, reduceMotion = false }: ExperiencePreparationScreenProps) {
  const isComplete = phase !== 'preparing'
  return (
    <section className={`experience-preparation ${phase === 'transitioning' ? 'is-transitioning' : ''} ${reduceMotion ? 'reduced-motion' : ''}`} aria-label="Preparing your experience" aria-live="polite">
      <div className="experience-preparation-card">
        {isComplete ? (
          <div className="experience-ready-message">
            <p className="eyebrow">MAGIFAB COMPANION</p>
            <h1>Your experience is ready.</h1>
            <p>Your companion now understands this story and is ready to help whenever you need it.</p>
            <p className="experience-enjoy">Enjoy your movie.</p>
          </div>
        ) : <>
          <p className="eyebrow">MAGIFAB COMPANION</p>
          <h1>Preparing your experience</h1>
          <p className="experience-preparation-subtitle">Your companion is learning this story so it can help you understand every important moment.</p>
          <ol className="experience-milestones" aria-label="Preparation milestones">
            {items.map(({ id, label }) => {
              const state = milestones[id]
              return <li key={id} className={`experience-milestone ${state}`}>
                <span className="experience-milestone-icon" aria-hidden="true">{state === 'complete' ? <Check size={14} strokeWidth={2.75} /> : <span />}</span>
                <span>{label}</span>
                {state === 'active' && <span className="sr-only"> in progress</span>}
              </li>
            })}
          </ol>
        </>}
      </div>
    </section>
  )
}
