import type { SceneData } from '../../types/movie'

export function RelationshipDiagram({ scene }: { scene: SceneData }) {
  return (
    <div className="diagram-grid">
      {scene.relationshipGraph.map((edge) => (
        <div key={`${edge.from}-${edge.to}`} className="diagram-node">
          <strong>{edge.from}</strong>
          <span>{edge.label}</span>
          <strong>{edge.to}</strong>
        </div>
      ))}
    </div>
  )
}
