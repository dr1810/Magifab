import type { SceneData } from '../../types/movie'

export function EmotionDiagram({ scene }: { scene: SceneData }) {
  return (
    <div className="emotion-diagram">
      <h4>{scene.emotion}</h4>
      <div className="emotion-bars">
        {scene.characterList.map((character) => (
          <div key={character.id}>
            <span>{character.name}</span>
            <p>{character.emotionalState}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
