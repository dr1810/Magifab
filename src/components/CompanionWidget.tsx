import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'
import type { CompanionTheme } from '../types/movie'

type CompanionWidgetProps = {
  open: boolean
  name: string
  message: string
  theme: CompanionTheme
  onClose: () => void
  reduceMotion: boolean
}

export function CompanionWidget({ open, name, message, theme, onClose, reduceMotion }: CompanionWidgetProps) {
  return <AnimatePresence>{open && <motion.aside className={`companion-widget ${theme}`} aria-live="polite" initial={reduceMotion ? false : { opacity: 0, scale: .96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: .96 }}>
      <button className="companion-widget-close" onClick={onClose} aria-label="Close companion explanation"><X size={15}/></button>
      <p className="eyebrow">{name}</p>
      <p>{message}</p>
    </motion.aside>}</AnimatePresence>
}
