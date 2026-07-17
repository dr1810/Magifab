import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'
import type { PromptQuestion } from '../types/movie'
import { PromptCard } from './PromptCard'
import { useAccessibility } from '../accessibility-context'

type PromptPanelProps = {
  open: boolean
  prompts: PromptQuestion[]
  selectedPromptId: string
  onSelectPrompt: (prompt: PromptQuestion) => void
  onClose: () => void
}

export function PromptPanel({ open, prompts, selectedPromptId, onSelectPrompt, onClose }: PromptPanelProps) {
  const [focusedIndex, setFocusedIndex] = useState(0)
  const panelRef = useRef<HTMLElement | null>(null)
  const { settings } = useAccessibility()
  const reduceMotion = settings.reduceMotion || settings.disableAnimations

  useEffect(() => {
    if (!open) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!panelRef.current?.contains(document.activeElement)) return
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

  return (
    <AnimatePresence initial={false}>
      {open && <motion.aside ref={panelRef} tabIndex={-1} className="prompt-panel" id="prompt-panel" aria-label="Prompt panel" initial={reduceMotion ? false : { x: '100%' }} animate={{ x: 0 }} exit={reduceMotion ? { x: 0 } : { x: '100%' }} transition={{ duration: reduceMotion ? 0 : 0.18, ease: 'easeOut' }}>
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
      </motion.aside>}
    </AnimatePresence>
  )
}
