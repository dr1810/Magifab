import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Send, X } from 'lucide-react'
import { CompanionAvatar } from './CompanionAvatar'
import type { CompanionTheme } from '../types/movie'

export type CompanionChatMessage = {
  id: string
  role: 'assistant' | 'user'
  text: string
}

type CompanionChatPanelProps = {
  open: boolean
  name: string
  appearance?: string
  theme: CompanionTheme
  messages: CompanionChatMessage[]
  onClose: () => void
  onSend: (question: string) => void
  reduceMotion: boolean
  drawerOpen: boolean
}

export function CompanionChatPanel({ open, name, appearance, theme, messages, onClose, onSend, reduceMotion, drawerOpen }: CompanionChatPanelProps) {
  const [question, setQuestion] = useState('')
  const inputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (!open) return
    const timer = window.setTimeout(() => inputRef.current?.focus(), reduceMotion ? 0 : 180)
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      event.stopPropagation()
      onClose()
    }
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target
      if (!(target instanceof Element)) return
      if (target.closest('.companion-chat-panel, .companion-launcher')) return
      onClose()
    }
    document.addEventListener('keydown', handleKeyDown, true)
    document.addEventListener('pointerdown', handlePointerDown, true)
    return () => {
      window.clearTimeout(timer)
      document.removeEventListener('keydown', handleKeyDown, true)
      document.removeEventListener('pointerdown', handlePointerDown, true)
    }
  }, [onClose, open, reduceMotion])

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    const trimmedQuestion = question.trim()
    if (!trimmedQuestion) return
    onSend(trimmedQuestion)
    setQuestion('')
  }

  return <AnimatePresence initial={false}>{open && <motion.aside
    id="companion-chat-panel"
    className={`companion-chat-panel ${theme} ${drawerOpen ? 'above-drawer' : ''}`}
    aria-label={`${name} companion chat`}
    initial={reduceMotion ? false : { opacity: 0, y: 12, scale: .98 }}
    animate={{ opacity: 1, y: 0, scale: 1 }}
    exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 12, scale: .98 }}
    transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 340, damping: 28, mass: .8 }}
  >
    <header className="companion-chat-header">
      <div className="companion-chat-identity"><CompanionAvatar appearance={appearance} name={name} size="small" /><div><p className="eyebrow">Personal companion</p><h3>{name}</h3></div></div>
      <button type="button" className="companion-chat-close" onClick={onClose} aria-label="Close companion chat"><X size={16} /></button>
    </header>
    <div className="companion-chat-messages" aria-live="polite">
      {messages.map((message) => <p key={message.id} className={`companion-chat-message ${message.role}`}>{message.text}</p>)}
    </div>
    <form className="companion-chat-form" onSubmit={submit}>
      <input ref={inputRef} value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === 'Escape') { event.preventDefault(); onClose() } }} aria-label={`Ask ${name} about this moment`} placeholder={`Ask ${name} about this moment`} />
      <button type="submit" aria-label="Send question" disabled={!question.trim()}><Send size={16} /></button>
    </form>
  </motion.aside>}</AnimatePresence>
}
