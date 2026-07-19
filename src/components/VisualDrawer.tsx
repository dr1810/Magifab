import { useState, type FocusEvent } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown } from 'lucide-react'
import { useAccessibility } from '../accessibility-context'
import type { IntervalState } from '../services/backend/CompanionBackendService'

type TabKey = 'story' | 'relationships' | 'timeline' | 'emotion' | 'causeEffect' | 'object' | 'memory'

const tabs: { key: TabKey; label: string }[] = [
  { key: 'story', label: 'Story Now' },
  { key: 'relationships', label: 'Relationships' },
  { key: 'timeline', label: 'Timeline' },
  { key: 'emotion', label: 'Emotion' },
  { key: 'causeEffect', label: 'Cause & Effect' },
  { key: 'object', label: 'Object' },
  { key: 'memory', label: 'Memory' },
]

type VisualDrawerProps = {
  open: boolean
  intervalState?: IntervalState | null
  onClose: () => void
  onMouseEnter: () => void
  onMouseLeave: () => void
  onFocus: () => void
  onBlur: (event: FocusEvent<HTMLElement>) => void
}

/** Each fixed tab renders only pre-composed content from the active StoryState. */
export function VisualDrawer({ open, intervalState, onClose, onMouseEnter, onMouseLeave, onFocus, onBlur }: VisualDrawerProps) {
  const [activeTab, setActiveTab] = useState<TabKey>('story')
  const { settings } = useAccessibility()
  const reduceMotion = settings.reduceMotion || settings.disableAnimations
  const state = intervalState

  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.section className="visual-drawer" aria-label="Story companion dashboard" initial={reduceMotion ? false : { y: '100%' }} animate={{ y: 0 }} exit={reduceMotion ? { y: 0 } : { y: '100%' }} transition={{ duration: reduceMotion ? 0 : 0.18, ease: 'easeOut' }} onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave} onFocus={onFocus} onBlur={onBlur} style={{ position: 'absolute', inset: 'auto 0 0', zIndex: 50, height: 'min(48%, 360px)', overflow: 'auto' }}>
          <div className="drawer-header">
            <div><p className="eyebrow">Story Companion</p><h3>Movie right now</h3></div>
            <button className="ghost-btn" onClick={onClose}><ChevronDown size={16} /> Close</button>
          </div>
          <div className="tab-row" role="tablist" aria-label="Story companion tabs">
            {tabs.map((tab) => <button key={tab.key} role="tab" aria-selected={activeTab === tab.key} className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`} onClick={() => setActiveTab(tab.key)}>{tab.label}</button>)}
          </div>
          <div className="drawer-content">
            {state ? <StoryTab state={state} tab={activeTab} /> : <p className="empty-aid">Story context will appear as this moment is understood.</p>}
          </div>
        </motion.section>
      )}
    </AnimatePresence>
  )
}

type PresentedState = IntervalState

function StoryTab({ state, tab }: { state: PresentedState; tab: TabKey }) {
  const content = state.visualDrawer
  const intervalId = state.metadata.interval_id
  if (tab === 'story') return <TabCard title="Story Now" subtitle={formatTime(state.metadata.start_time)} items={content.story_now} fallback="The story is continuing in this moment." intervalId={intervalId} />
  if (tab === 'relationships') return <TabCard title="Relationships" items={content.relationships} fallback="The people here are sharing this moment together." intervalId={intervalId} />
  if (tab === 'timeline') return (
    <article className="diagram-node"><strong>Timeline</strong><ul className="drawer-list">
      {content.timeline.map((event, index) => <li key={`${state.metadata.interval_id}:timeline:${index}`}><small>{index === 0 ? 'Now' : 'Story'}</small>{event}</li>)}
      {!content.timeline.length && <li><small>Now</small>{state.storyState.scene_summary ?? 'The story is continuing.'}</li>}
    </ul></article>
  )
  if (tab === 'emotion') return <TabCard title="Emotion" text={content.emotion} fallback="The characters are reacting to what is happening now." intervalId={intervalId} />
  if (tab === 'causeEffect') return content.cause_effect.length ? <article className="diagram-node"><strong>Cause &amp; Effect</strong><ul className="drawer-list">{content.cause_effect.map((item, index) => <li key={`${state.metadata.interval_id}:cause-effect:${index}`}><small>Cause</small>{item.cause}<small>Effect</small>{item.effect}</li>)}</ul></article> : <TabCard title="Cause & Effect" text="This moment moves the story forward." intervalId={intervalId} />
  if (tab === 'object') return <TabCard title="Important Objects" items={content.objects} fallback="No object is more important than the characters' actions in this moment." intervalId={intervalId} />
  return <TabCard title="Memory" items={content.memory} fallback="There are no earlier events needed to understand this moment." intervalId={intervalId} />
}

function TabCard({ title, subtitle, text, items, fallback, intervalId }: { title: string; subtitle?: string; text?: string | null; items?: string[]; fallback?: string; intervalId?: string }) {
  return <article className="diagram-node"><strong>{title}</strong>{subtitle && <small>{subtitle}</small>}{text && <span>{text}</span>}{items && <ul className="drawer-list">{(items.length ? items : [fallback]).filter(Boolean).map((item, index) => <li key={`${intervalId ?? title}:${index}`}>{item}</li>)}</ul>}</article>
}

function formatTime(seconds: number) { return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}` }
