import type { SceneData } from '../../types/movie'

export function TimelineDiagram({ scene }: { scene: SceneData }) {
  return (
    <ol className="timeline-diagram">
      {scene.timelineData.map((step) => (
        <li key={step.id}>
          <span>{step.time}</span>
          <strong>{step.label}</strong>
        </li>
      ))}
    </ol>
  )
}
