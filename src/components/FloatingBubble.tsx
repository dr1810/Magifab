import { memo } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Loader2, Sparkles, X } from 'lucide-react'
import type { CompanionTheme } from '../types/movie'

type FloatingBubbleProps = {
  content: PromptBubbleContent | null
  theme: CompanionTheme
  reduceMotion: boolean
  visible: boolean
  onOpenCompanion: () => void
  onClose: () => void
}

export type PromptBubbleContent = {
  id: string
  question: string
  title: string
  relationship: string
  explanation: string
  anchor: { x: number; y: number }
  highlightTarget: boolean
  loading?: boolean
}

function FloatingBubbleComponent({ content, theme, reduceMotion, visible, onOpenCompanion, onClose }: FloatingBubbleProps) {
  if (!content) return null

  const calloutClass = theme === 'ocean' ? 'bubble-callout ocean' : 'bubble-callout sun'
  const targetTop = Math.min(content.anchor.y, 72)
  const bubbleTop = Math.max(12, targetTop - 18)

  const stableAnimation = { opacity: 1, scale: 1, y: 0 }

  return (
    <AnimatePresence initial={false}>
      {visible && (
        <>
          {content.highlightTarget && (
            <motion.span
              className="bubble-target-highlight"
              style={{ left: `${content.anchor.x}%`, top: `${targetTop}%` }}
              initial={reduceMotion ? false : { opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.92 }}
              transition={reduceMotion ? { duration: 0 } : { duration: 0.2 }}
              aria-hidden="true"
            />
          )}

          <motion.aside
            key={content.id}
            className={calloutClass}
            style={{ left: `${content.anchor.x}%`, top: `${bubbleTop}%` }}
            initial={reduceMotion ? false : { opacity: 0, scale: 0.92, y: 10 }}
            animate={stableAnimation}
            transition={reduceMotion ? { duration: 0 } : { duration: 0.2, ease: 'easeOut' }}
            exit={{ opacity: 0, scale: 0.92, y: 8 }}
            role="status"
            aria-live="polite"
          >
            <button type="button" className="bubble-close" onClick={onClose} aria-label="Close help bubble">
              <X size={14} />
            </button>
            <p className="eyebrow">{content.question}</p>
            <h4>{content.title}</h4>
            {content.loading ? (
              <p className="bubble-explanation" aria-label="Preparing explanation">
                <Loader2 className="spin" size={15} aria-hidden="true" /> Finding the character…
              </p>
            ) : (
              <>
                <p className="bubble-relationship">{content.relationship}</p>
                <p className="bubble-explanation">{content.explanation}</p>
                <button type="button" className="bubble-open-companion" onClick={onOpenCompanion}>
                  <Sparkles size={14} /> Open companion
                </button>
              </>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}

export const FloatingBubble = memo(FloatingBubbleComponent)
