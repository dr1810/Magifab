import { useMemo, useState, type FocusEvent, type MouseEvent } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown } from 'lucide-react'
import type { SceneData } from '../types/movie'
import { useAccessibility } from '../accessibility-context'
import { RelationshipDiagram } from './diagrams/RelationshipDiagram'
import { TimelineDiagram } from './diagrams/TimelineDiagram'
import { EmotionDiagram } from './diagrams/EmotionDiagram'
import { CauseEffectDiagram } from './diagrams/CauseEffectDiagram'
import { ObjectDiagram } from './diagrams/ObjectDiagram'
import type { AccessibilityPresentation } from '../services/backend/CompanionBackendService'

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
  scene: SceneData
  presentation?: AccessibilityPresentation | null
  onClose: () => void
  onMouseEnter: () => void
  onMouseLeave: () => void
  onFocus: () => void
  onBlur: (event: FocusEvent<HTMLElement>) => void
}

export function VisualDrawer({ open, scene, presentation, onClose, onMouseEnter, onMouseLeave, onFocus, onBlur }: VisualDrawerProps) {
  const [activeTab, setActiveTab] = useState<TabKey>('relationships')
  const { settings } = useAccessibility()
  const reduceMotion = settings.reduceMotion || settings.disableAnimations

  const content = useMemo(() => {
    if (presentation) return <BackendDrawerContent activeTab={activeTab} presentation={presentation} />
    if (activeTab === 'relationships') return <RelationshipDiagram scene={scene} />
    if (activeTab === 'timeline') return <TimelineDiagram scene={scene} />
    if (activeTab === 'emotion') return <EmotionDiagram scene={scene} />
    if (activeTab === 'causeEffect') return <CauseEffectDiagram scene={scene} />
    if (activeTab === 'memory') return <p className="empty-aid">No memory reminder is available for this scene yet.</p>
    return <ObjectDiagram scene={scene} />
  }, [activeTab, scene, presentation])

  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.section
          className="visual-drawer"
          aria-label="Visual aids drawer"
          initial={reduceMotion ? false : { y: '100%' }}
          animate={{ y: 0 }}
          exit={reduceMotion ? { y: 0 } : { y: '100%' }}
          transition={{ duration: reduceMotion ? 0 : 0.18, ease: 'easeOut' }}
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
          onFocus={onFocus}
          onBlur={onBlur}
          style={{ position: 'absolute', inset: 'auto 0 0', zIndex: 50, height: 'min(48%, 360px)', overflow: 'auto' }}
        >
          <div className="drawer-header">
            <div>
              <p className="eyebrow">Visual Aids</p>
              <h3>{scene.sceneId}</h3>
            </div>
            <button className="ghost-btn" onClick={onClose}><ChevronDown size={16} /> Close</button>
          </div>
          <div className="tab-row" role="tablist" aria-label="Visual aid tabs">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                role="tab"
                aria-selected={activeTab === tab.key}
                className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="drawer-content">{content}</div>
        </motion.section>
      )}
    </AnimatePresence>
  )
}

function BackendDrawerContent({ activeTab, presentation }: { activeTab: TabKey; presentation: AccessibilityPresentation }) {
  const drawer = presentation
  if (activeTab === 'story') {
    const state = drawer.story_state
    const story = drawer.live_story
    if (!state && !story) return <p className="empty-aid">The live story memory is building from timestamped scenes.</p>
    if (story) return (
      <div className="diagram-grid" aria-label="Live story assistant">
        <article className="diagram-node"><strong>Current Scene</strong><span>{story.current_scene} · {formatTime(story.current_timestamp)}</span></article>
        <article className="diagram-node"><strong>Current Goal</strong><span>{story.current_goal ?? 'No active goal.'}</span></article>
        <article className="diagram-node"><strong>Timeline Position</strong><span>{story.timeline_position ?? 'Learning the current story position.'}</span></article>
        <article className="diagram-node"><strong>Characters</strong><span>{join(story.current_characters)}</span></article>
        <article className="diagram-node"><strong>Emotions</strong><span>{join(story.current_emotions)}</span></article>
        <article className="diagram-node"><strong>Relationships</strong><span>{join(story.current_relationships)}</span></article>
        <article className="diagram-node"><strong>Recent Events</strong><span>{join(story.recent_events)}</span></article>
        <article className="diagram-node"><strong>Story So Far</strong><span>{join(story.story_so_far)}</span></article>
        <article className="diagram-node"><strong>Important Objects</strong><span>{join(story.important_objects)}</span></article>
        <article className="diagram-node"><strong>Memory Reminders</strong><span>{join(story.memory_reminders)}</span></article>
        <article className="diagram-node"><strong>Unresolved Threads</strong><span>{join(story.unresolved_story_threads)}</span></article>
      </div>
    )
    if (state) return (
      <div className="diagram-grid" aria-label="Live story assistant">
        <article className="diagram-node"><strong>Current Scene</strong><span>{state.current_scene ?? 'Learning scene'} · {formatTime(state.current_timestamp)}</span></article>
        <article className="diagram-node"><strong>Current Location</strong><span>{state.current_location ?? 'Not established yet.'}</span></article>
        <article className="diagram-node"><strong>Current Goal</strong><span>{state.current_goal ?? 'No active goal.'}</span></article>
        <article className="diagram-node"><strong>Characters</strong><span>{join(Object.values(state.known_characters).map((item) => item.name))}</span></article>
        <article className="diagram-node"><strong>Emotions</strong><span>{join(Object.values(state.active_emotions))}</span></article>
        <article className="diagram-node"><strong>Relationships</strong><span>{join(Object.values(state.known_relationships).map((item) => item.summary))}</span></article>
        <article className="diagram-node"><strong>Recent Events</strong><span>{join(state.recent_events.map((item) => item.summary))}</span></article>
        <article className="diagram-node"><strong>Story So Far</strong><span>{join(state.story_so_far.map((item) => item.summary))}</span></article>
        <article className="diagram-node"><strong>Important Objects</strong><span>{join(Object.values(state.known_objects).map((item) => item.name))}</span></article>
        <article className="diagram-node"><strong>Memory Reminders</strong><span>{join(state.memory_reminders.map((item) => item.summary))}</span></article>
        <article className="diagram-node"><strong>Unresolved Threads</strong><span>{join(state.open_story_threads.map((item) => item.summary))}</span></article>
      </div>
    )
    return <p className="empty-aid">The live story memory is building from timestamped scenes.</p>
  }
  if (activeTab === 'relationships') {
    return (
      <div className="diagram-grid">
        {drawer.character_cards.map((card) => <article key={card.character_id} className="diagram-node"><strong>{card.name}</strong><span>{card.reminder}</span></article>)}
        {drawer.relationship_summaries.map((item) => <article key={item.relationship_id} className="diagram-node"><span>{item.summary}</span></article>)}
        {drawer.character_cards.length === 0 && drawer.relationship_summaries.length === 0 && <p className="empty-aid">No verified character or relationship information is available yet.</p>}
      </div>
    )
  }
  if (activeTab === 'timeline') return drawer.timeline_summary ? <ol className="timeline-diagram"><li><span>Now</span><strong>{drawer.timeline_summary.summary}</strong></li></ol> : <p className="empty-aid">No timeline summary is available yet.</p>
  if (activeTab === 'emotion') return drawer.emotion_summaries.length ? <div className="emotion-diagram">{drawer.emotion_summaries.map((item) => <div key={item.emotion_id}><h4>{item.summary}</h4></div>)}</div> : <p className="empty-aid">No verified emotion information is available yet.</p>
  if (activeTab === 'causeEffect') return drawer.conversation_simplifications.length ? <div className="cause-effect">{drawer.conversation_simplifications.map((item) => <article key={item.dialogue_id}><h4>Simple conversation</h4><p>{item.simple_text}</p></article>)}</div> : <p className="empty-aid">No conversation simplification is available yet.</p>
  if (activeTab === 'object') return drawer.vocabulary_assistance.length ? <div className="object-diagram">{drawer.vocabulary_assistance.map((item) => <article key={item.term}><h4>{item.term}</h4><p>{item.simple_definition}</p></article>)}</div> : <p className="empty-aid">No vocabulary help is available yet.</p>
  return drawer.memory_reminders.length ? <ol className="timeline-diagram">{drawer.memory_reminders.map((item, index) => <li key={`${item.summary}-${index}`}><span>Earlier</span><strong>{item.summary}</strong></li>)}</ol> : <p className="empty-aid">No memory reminder is available yet.</p>
}

function join(values: string[]) { return values.length ? values.join(' · ') : 'None yet.' }
function formatTime(seconds: number) { return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}` }
