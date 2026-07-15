import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import type { PromptQuestion } from '../types/movie'
import { PromptCard } from './PromptCard'

type PromptPanelProps = {
  open: boolean
  prompts: PromptQuestion[]
  selectedPromptId: string
  onSelectPrompt: (prompt: PromptQuestion) => void
  onClose: () => void
}

export function PromptPanel({ open, prompts, selectedPromptId, onSelectPrompt, onClose }: PromptPanelProps) {
  const [focusedIndex, setFocusedIndex] = useState(0)

  useEffect(() => {
    if (!open) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setFocusedIndex((value) => (value + 1) % prompts.length)
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        setFocusedIndex((value) => (value - 1 + prompts.length) % prompts.length)
      }
      if (event.key === 'Enter' && prompts[focusedIndex]) {
        onSelectPrompt(prompts[focusedIndex])
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, prompts, focusedIndex, onClose, onSelectPrompt])

  useEffect(() => {
    if (prompts.length === 0) return
    const selectedIndex = prompts.findIndex((prompt) => prompt.id === selectedPromptId)
    if (selectedIndex >= 0) setFocusedIndex(selectedIndex)
  }, [prompts, selectedPromptId])

  if (!open) return null

  return (
    <aside className="prompt-panel" aria-label="Prompt panel">
      <div className="prompt-panel-header">
        <div>
          <p className="eyebrow">Prompt Guide</p>
          <h3>Scene Questions</h3>
        </div>
        <button className="ghost-btn" onClick={onClose} aria-label="Close prompts">
          <X size={15} />
        </button>
      </div>
      <div className="prompt-list">
        {prompts.map((prompt, index) => (
          <PromptCard
            key={prompt.id}
            prompt={prompt}
            active={selectedPromptId === prompt.id || focusedIndex === index}
            onSelect={() => {
              setFocusedIndex(index)
              onSelectPrompt(prompt)
            }}
          />
        ))}
      </div>
    </aside>
  )
}
