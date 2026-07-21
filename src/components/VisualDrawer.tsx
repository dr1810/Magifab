import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useAnimation } from 'framer-motion'
import { ChevronDown } from 'lucide-react'
import { useAccessibility } from '../accessibility-context'
import type { StoryCompanionPromptContext, StoryCompanionTab } from '../services/narrative/StoryCompanionNavigation'
import type { SceneState } from '../services/scene/SceneState'

type TabKey = StoryCompanionTab

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: 'story', label: 'Story Now' },
  { key: 'characters', label: 'Characters' },
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
  promptContext?: StoryCompanionPromptContext | null
  onClose: () => void
  presentation?: 'default' | 'book-sheet'
}

export function VisualDrawer({ open, sceneState, promptContext = null, onClose, presentation = 'default' }: VisualDrawerProps) {
  const { settings } = useAccessibility()
  const reduceMotion = settings.reduceMotion || settings.disableAnimations
  const [activeTab, setActiveTab] = useState<TabKey>('relationships')
  const drawerRef = useRef<HTMLElement | null>(null)
  const scrollTopRef = useRef(0)
  const renderedIntervalIdRef = useRef<string | null>(null)
  const contentControls = useAnimation()
  const [sheetHeight, setSheetHeight] = useState<'collapsed' | 'half' | 'expanded'>('half')
  const dragStartRef = useRef<number | null>(null)
  const isBookSheet = presentation === 'book-sheet'
  const sheetHeights = { collapsed: '68px', half: '52vh', expanded: '80vh' }

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

  useEffect(() => {
    if (promptContext) setActiveTab(promptContext.tab)
  }, [promptContext])

  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.section
          ref={drawerRef}
          className={`visual-drawer ${isBookSheet ? 'book-visual-sheet' : ''}`}
          aria-label="Visual aids drawer"
          initial={reduceMotion ? false : { y: '100%' }}
          animate={{ y: 0 }}
          exit={reduceMotion ? { y: 0 } : { y: '100%' }}
          transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 360, damping: 34, mass: .8 }}
          style={isBookSheet ? { position: 'fixed', inset: 'auto 0 0', zIndex: 200, height: sheetHeights[sheetHeight], overflow: 'auto' } : { position: 'absolute', inset: 'auto 0 0', zIndex: 50, height: 'min(48%, 360px)', overflow: 'auto' }}
          onScroll={(event) => { scrollTopRef.current = event.currentTarget.scrollTop }}
        >
          {isBookSheet && <button type="button" className="book-sheet-handle" aria-label="Resize Story Companion" onPointerDown={(event) => { dragStartRef.current = event.clientY }} onPointerUp={(event) => { const start = dragStartRef.current; dragStartRef.current = null; if (start === null) return; const delta = event.clientY - start; setSheetHeight((height) => delta > 42 ? 'collapsed' : delta < -42 ? 'expanded' : height === 'collapsed' ? 'half' : height) }} onClick={() => setSheetHeight((height) => height === 'collapsed' ? 'half' : height === 'half' ? 'expanded' : 'collapsed')}><span/></button>}
          <div className="drawer-header">
            <div><p className="eyebrow">Visual Aids</p><h3>Story Companion</h3></div>
            <button className="ghost-btn" onClick={() => isBookSheet && sheetHeight !== 'collapsed' ? setSheetHeight('collapsed') : onClose()}><ChevronDown size={16} /> {isBookSheet && sheetHeight !== 'collapsed' ? 'Collapse' : 'Close'}</button>
          </div>
          {promptContext && <motion.section key={promptContext.id} className="drawer-prompt-context" initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 320, damping: 28, duration: 0.28 }}>
            <p className="eyebrow">Prompt</p>
            <h4>{promptContext.question}</h4>
            <p>{promptContext.answer}</p>
            <div className="drawer-prompt-visual-aid"><span>Visual Aid</span><strong>{promptContext.visualAid}</strong></div>
          </motion.section>}
          {sheetHeight !== 'collapsed' && <><div className="tab-row" role="tablist" aria-label="Visual aid tabs">
            {tabs.map((tab) => <button key={tab.key} role="tab" aria-selected={activeTab === tab.key} className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`} onClick={() => setActiveTab(tab.key)}>{tab.label}</button>)}
          </div>
          <motion.div className="drawer-content" initial={false} animate={contentControls}>
            <SceneStateDrawerContent activeTab={activeTab} state={sceneState ?? null} />
          </motion.div></>}
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
  if (activeTab === 'characters') return <NodeGrid items={state.characters.map((item) => [item.name, item.reminder] as const)} empty="No character information is available for this part of the story yet." />
  if (activeTab === 'relationships') return <NodeGrid items={[
    ...state.characters.map((item) => [item.name, item.reminder] as const),
    ...state.relationships.map((item) => ['Relationship', item.summary] as const),
  ]} empty="No verified character or relationship information is available yet." />
  if (activeTab === 'emotions') return <NodeGrid items={[
    ...state.emotions.map((item) => ['Emotion', item.summary] as const),
  ]} empty="No verified emotion information is available yet." />
  if (activeTab === 'objects') return <NodeGrid items={[
    ...(state.visualAid ? [['Visual aid', state.visualAid.description] as const] : []),
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
