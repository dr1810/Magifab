import { useMemo, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import type { SceneData } from '../types/movie'
import { RelationshipDiagram } from './diagrams/RelationshipDiagram'
import { TimelineDiagram } from './diagrams/TimelineDiagram'
import { EmotionDiagram } from './diagrams/EmotionDiagram'
import { CauseEffectDiagram } from './diagrams/CauseEffectDiagram'
import { ObjectDiagram } from './diagrams/ObjectDiagram'

type TabKey = 'relationships' | 'timeline' | 'emotion' | 'causeEffect' | 'object'

const tabs: { key: TabKey; label: string }[] = [
  { key: 'relationships', label: 'Relationships' },
  { key: 'timeline', label: 'Timeline' },
  { key: 'emotion', label: 'Emotion' },
  { key: 'causeEffect', label: 'Cause & Effect' },
  { key: 'object', label: 'Object' },
]

type VisualDrawerProps = {
  open: boolean
  scene: SceneData
  onClose: () => void
}

export function VisualDrawer({ open, scene, onClose }: VisualDrawerProps) {
  const [activeTab, setActiveTab] = useState<TabKey>('relationships')

  const content = useMemo(() => {
    if (activeTab === 'relationships') return <RelationshipDiagram scene={scene} />
    if (activeTab === 'timeline') return <TimelineDiagram scene={scene} />
    if (activeTab === 'emotion') return <EmotionDiagram scene={scene} />
    if (activeTab === 'causeEffect') return <CauseEffectDiagram scene={scene} />
    return <ObjectDiagram scene={scene} />
  }, [activeTab, scene])

  if (!open) return null

  return (
    <section className="visual-drawer" aria-label="Visual aids drawer">
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
    </section>
  )
}
