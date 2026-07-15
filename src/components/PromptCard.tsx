import type { PromptQuestion } from '../types/movie'

type PromptCardProps = {
  prompt: PromptQuestion
  active: boolean
  onSelect: () => void
}

export function PromptCard({ prompt, active, onSelect }: PromptCardProps) {
  return (
    <button className={`prompt-card ${active ? 'active' : ''}`} onClick={onSelect}>
      <span className="prompt-label">{prompt.label}</span>
      <strong>{prompt.question}</strong>
      <p>{prompt.explanation}</p>
    </button>
  )
}
