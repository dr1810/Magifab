import { motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'
import type { CompanionTheme, SceneData } from '../types/movie'

type FloatingBubbleProps = {
  scene: SceneData
  theme: CompanionTheme
  reduceMotion: boolean
  onClick: () => void
}

export function FloatingBubble({ scene, theme, reduceMotion, onClick }: FloatingBubbleProps) {
  const className = theme === 'ocean' ? 'bubble ocean' : 'bubble sun'

  return (
    <motion.button
      className={className}
      onClick={onClick}
      initial={false}
      animate={
        reduceMotion
          ? { left: `${scene.companionPosition.x}%`, top: `${scene.companionPosition.y}%` }
          : {
              left: `${scene.companionPosition.x}%`,
              top: `${scene.companionPosition.y}%`,
              y: [0, -6, 0],
            }
      }
      transition={reduceMotion ? { duration: 0 } : { duration: 2.6, repeat: Infinity }}
      aria-label="Toggle companion message"
    >
      <Sparkles size={18} />
    </motion.button>
  )
}
