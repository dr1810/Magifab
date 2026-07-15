import type { SceneData } from '../../types/movie'

export function ObjectDiagram({ scene }: { scene: SceneData }) {
  return (
    <article className="object-diagram">
      <h4>{scene.highlightObject.name}</h4>
      <p>{scene.highlightObject.reason}</p>
    </article>
  )
}
