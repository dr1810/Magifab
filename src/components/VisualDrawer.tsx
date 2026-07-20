import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useAnimation } from 'framer-motion'
import { ChevronDown } from 'lucide-react'
import { useAccessibility } from '../accessibility-context'
import type { SceneState } from '../services/scene/SceneState'

type TabKey = 'story' | 'relationships' | 'emotions' | 'objects' | 'memory' | 'timeline' | 'causeEffect' | 'conversation' | 'summary'

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: 'story', label: 'Story Now' },
  { key: 'relationships', label: 'Relationships' },
  { key: 'emotions', label: 'Emotions' },
  { key: 'objects', label: 'Objects' },
  { key: 'memory', label: 'Memory' },
  { key: 'timeline', label: 'Timeline' },
  { key: 'causeEffect', label: 'Cause & Effect' },
  { key: 'conversation', label: 'Conversation' },
  { key: 'summary', label: 'Summary' },
]

type VisualDrawerProps = {
  open: boolean
  sceneState?: SceneState | null
  onClose: () => void
}

export function VisualDrawer({ open, sceneState, onClose }: VisualDrawerProps) {
  const { settings } = useAccessibility()
  const reduceMotion = settings.reduceMotion || settings.disableAnimations
  const [activeTab, setActiveTab] = useState<TabKey>('relationships')
  const drawerRef = useRef<HTMLElement | null>(null)
  const scrollTopRef = useRef(0)
  const renderedIntervalIdRef = useRef<string | null>(null)
  const contentControls = useAnimation()

  useLayoutEffect(() => {
    if (!sceneState || sceneState.sceneId === renderedIntervalIdRef.current) return
    const drawer = drawerRef.current
    scrollTopRef.current = drawer?.scrollTop ?? 0
    renderedIntervalIdRef.current = sceneState.sceneId
    requestAnimationFrame(() => {
      if (drawer) drawer.scrollTop = scrollTopRef.current
    })
  }, [sceneState])

  useEffect(() => {
    if (!sceneState || reduceMotion) return
    void contentControls.start({ opacity: [0.82, 1], y: [4, 0], transition: { duration: 0.2, ease: 'easeOut' } })
  }, [contentControls, sceneState?.sceneId, reduceMotion])

  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.section
          ref={drawerRef}
          className="visual-drawer"
          aria-label="Visual aids drawer"
          initial={reduceMotion ? false : { y: '100%' }}
          animate={{ y: 0 }}
          exit={reduceMotion ? { y: 0 } : { y: '100%' }}
          transition={{ duration: reduceMotion ? 0 : 0.18, ease: 'easeOut' }}
          style={{ position: 'absolute', inset: 'auto 0 0', zIndex: 50, height: 'min(48%, 360px)', overflow: 'auto' }}
          onScroll={(event) => { scrollTopRef.current = event.currentTarget.scrollTop }}
        >
          <div className="drawer-header">
            <div><p className="eyebrow">Visual Aids</p><h3>Story Companion</h3></div>
            <button className="ghost-btn" onClick={onClose}><ChevronDown size={16} /> Close</button>
          </div>
          <div className="tab-row" role="tablist" aria-label="Visual aid tabs">
            {tabs.map((tab) => <button key={tab.key} role="tab" aria-selected={activeTab === tab.key} className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`} onClick={() => setActiveTab(tab.key)}>{tab.label}</button>)}
          </div>
          <motion.div className="drawer-content" initial={false} animate={contentControls}>
            <SceneStateDrawerContent activeTab={activeTab} state={sceneState ?? null} />
          </motion.div>
        </motion.section>
      )}
    </AnimatePresence>
  )
}

function SceneStateDrawerContent({ activeTab, state }: { activeTab: TabKey; state: SceneState | null }) {
  if (!state) return <p className="empty-aid">This visual aid will appear when the first story interval is ready.</p>
  if (activeTab === 'story') return <NodeGrid items={[
    ['Right now', state.sceneSummary],
    ['Current goal', state.story.currentGoal],
    ['Story position', state.story.timelinePosition],
    ['Story so far', state.story.storySoFar],
    ['Unresolved', state.story.unresolvedThreads],
  ]} />
  if (activeTab === 'relationships') return <NodeGrid items={[
    ...state.characters.map((item) => [item.name, item.reminder] as const),
    ...state.relationships.map((item) => ['Relationship', item.summary] as const),
  ]} empty="No verified character or relationship information is available yet." />
  if (activeTab === 'emotions') return <NodeGrid items={[
    ...state.emotions.map((item) => ['Emotion', item.summary] as const),
  ]} empty="No verified emotion information is available yet." />
  if (activeTab === 'objects') return <NodeGrid items={[
    ...state.importantObjects.map((item) => ['Important object', item] as const),
    ...state.accessibilityHints.vocabulary.map((item) => [item.term, item.simple_definition] as const),
  ]} empty="No object or vocabulary help is available yet." />
  if (activeTab === 'memory') return <TimelineList label="Earlier" items={state.memory.map((item) => item.summary)} empty="No memory reminder is available for this interval yet." />
  if (activeTab === 'timeline') return <TimelineList label="Now" items={state.timeline} empty="No timeline summary is available yet." />
  if (activeTab === 'causeEffect') return state.causeEffect.length ? <div className="cause-effect">{state.causeEffect.map((item, index) => <article key={`${item.cause}-${index}`}><h4>Cause</h4><p>{item.cause}</p><h4>Effect</h4><p>{item.effect}</p></article>)}</div> : <p className="empty-aid">No cause and effect explanation is available yet.</p>
  if (activeTab === 'conversation') return <NodeGrid items={[
    ['What happened', state.conversation.sceneExplanation],
    ...state.conversation.simplifications.map((item) => ['Simple conversation', item.simple_text] as const),
  ]} empty="No conversation simplification is available yet." />
  return <NodeGrid items={[
    ['Summary', state.sceneSummary],
    ['Important', state.importantObjects],
    ['Remember', state.memory.map((item) => item.summary)],
    ['What is next', state.timeline.at(-1)],
  ]} />
}

function NodeGrid({ items, empty }: { items: ReadonlyArray<readonly [string, string | string[] | null | undefined]>; empty?: string }) {
  const visibleItems = items.filter(([, value]) => Array.isArray(value) ? value.length > 0 : Boolean(value))
  if (!visibleItems.length) return <p className="empty-aid">{empty ?? 'This information is still being prepared.'}</p>
  return <div className="diagram-grid">{visibleItems.map(([title, value], index) => <article key={`${title}-${index}`} className="diagram-node"><strong>{title}</strong><span>{Array.isArray(value) ? value.join(' · ') : value}</span></article>)}</div>
}

function TimelineList({ label, items, empty }: { label: string; items: Array<string | null | undefined>; empty: string }) {
  const visibleItems = [...new Set(items.filter((item): item is string => Boolean(item)))]
  if (!visibleItems.length) return <p className="empty-aid">{empty}</p>
  return <ol className="timeline-diagram">{visibleItems.map((item) => <li key={item}><span>{label}</span><strong>{item}</strong></li>)}</ol>
}
