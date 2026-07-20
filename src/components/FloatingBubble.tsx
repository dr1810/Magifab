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
  visualAnchor?: { x: number; y: number; width: number; height: number }
  visualAidType?: 'magnifier' | 'highlight'
  highlightTarget: boolean
  loading?: boolean
  lifecycle?: 'idle' | 'loading' | 'streaming' | 'completed' | 'expired' | 'dismissed' | 'failed' | 'fallback'
  contextVersion?: number
  storyBeatId?: string
  timestampCreated?: number
  validFrom?: number
  validUntil?: number
  absolutePosition?: { left: number; top: number }
}

function FloatingBubbleComponent({ content, theme, reduceMotion, visible, onOpenCompanion, onClose }: FloatingBubbleProps) {
  if (!content) return null

  const calloutClass = theme === 'ocean' ? 'bubble-callout ocean' : 'bubble-callout sun'
  const visualAnchor = content.visualAnchor ?? { ...content.anchor, width: 8, height: 8 }
  const targetTop = Math.min(visualAnchor.y, 72)
  const cardLeft = content.visualAnchor
    ? content.visualAnchor.x <= 50
      ? Math.min(84, content.visualAnchor.x + content.visualAnchor.width / 2 + 18)
      : Math.max(16, content.visualAnchor.x - content.visualAnchor.width / 2 - 18)
    : content.anchor.x
  const bubbleTop = content.visualAnchor ? Math.max(22, Math.min(78, content.visualAnchor.y)) : Math.max(12, targetTop - 18)

  const stableAnimation = { opacity: 1, scale: 1, y: 0 }

  return (
    <AnimatePresence initial={false}>
      {visible && (
        <>
          {content.highlightTarget && (
            <motion.span
              className={`bubble-target-highlight ${content.visualAidType ?? ''}`}
              style={{
                left: `${visualAnchor.x}%`,
                top: `${targetTop}%`,
                width: `${visualAnchor.width}%`,
                height: `${visualAnchor.height}%`,
              }}
              initial={reduceMotion ? false : { opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.92 }}
              transition={reduceMotion ? { duration: 0 } : { duration: 0.2 }}
              aria-hidden="true"
            />
          )}

          <motion.aside
            key={content.id}
            className={`${calloutClass} floating-prompt-card`}
            style={content.absolutePosition ? { left: content.absolutePosition.left, top: content.absolutePosition.top } : { left: `${cardLeft}%`, top: `${bubbleTop}%` }}
            initial={reduceMotion ? false : { opacity: 0, scale: 0.92, y: 10 }}
            animate={stableAnimation}
            transition={reduceMotion ? { duration: 0 } : { duration: 0.2, ease: 'easeOut' }}
            exit={{ opacity: 0, scale: 0.92, y: 8 }}
            onClick={content.loading || content.lifecycle === 'streaming' ? undefined : onOpenCompanion}
            role="status"
            aria-live="polite"
          >
            <button type="button" className="bubble-close" onClick={(event) => { event.stopPropagation(); onClose() }} aria-label="Close help bubble">
              <X size={14} />
            </button>
            <p className="eyebrow">{content.question}</p>
            <h4>{content.title}</h4>
            {content.loading || content.lifecycle === 'streaming' ? (
              <p className="bubble-explanation" aria-label="Preparing explanation">
                <Loader2 className="spin" size={15} aria-hidden="true" /> Finding the character…
              </p>
            ) : (
              <>
                <p className="bubble-relationship">{content.relationship}</p>
                <p className="bubble-explanation">{content.explanation}</p>
                <button type="button" className="bubble-open-companion" onClick={(event) => { event.stopPropagation(); onOpenCompanion() }}>
                  <Sparkles size={14} /> Open Story Companion
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
