import type { SceneData } from '../../types/movie'

export function CauseEffectDiagram({ scene }: { scene: SceneData }) {
  return (
    <div className="cause-effect">
      <article>
        <h4>Cause</h4>
        <p>{scene.causeEffectData.cause}</p>
      </article>
      <article>
        <h4>Action</h4>
        <p>{scene.causeEffectData.action}</p>
      </article>
      <article>
        <h4>Effect</h4>
        <p>{scene.causeEffectData.effect}</p>
      </article>
    </div>
  )
}
