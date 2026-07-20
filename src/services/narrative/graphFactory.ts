import type { MovieData, SceneData } from '../../types/movie'
import type { AccessibilityNeed, NarrativeCharacter, NarrativeGraph, NarrativeScene } from './types'

function sceneNode(scene: SceneData, next: SceneData | undefined): NarrativeScene {
  const visibleCharacterRecords = scene.characterList.filter((character) => scene.visibleCharacterIds?.includes(character.id) ?? true)
  const characters = visibleCharacterRecords.map((character) => character.name)
  const emotions = scene.characterList.map((character) => ({ character: character.name, emotion: character.emotionalState, explanation: `${character.name} feels ${character.emotionalState.toLowerCase()} in this moment.` }))
  const relationshipText = scene.relationshipGraph.map((relationship) => `${relationship.from} and ${relationship.to}: ${relationship.label}`)
  const object = scene.highlightObject.name
  const prompts = scene.prompts.map((prompt, index) => ({
    id: `${scene.sceneId}:${prompt.id}`,
    triggerType: (prompt.id === 'emotion' ? 'emotions' : prompt.id === 'who' ? 'characters' : prompt.id === 'before' ? 'memory' : 'plot') as AccessibilityNeed,
    question: prompt.question,
    explanation: prompt.explanation,
    difficultyCategory: prompt.label,
    priority: scene.prompts.length - index,
    subjectEntityIds: scene.promptSubjects?.[prompt.id],
    evidence: [scene.subtitle],
  }))
  return {
    sceneId: scene.sceneId,
    startTime: scene.timestamp,
    endTime: next?.timestamp ?? null,
    title: scene.subtitle,
    summary: scene.prompts.find((prompt) => /happening|scene|changed/i.test(prompt.question))?.explanation ?? scene.voiceNarration,
    characters,
    visualGrounding: {
      visibleEntityIds: scene.visibleCharacterIds ?? scene.characterList.map((character) => character.id),
      missingEntityIds: scene.missingCharacterIds ?? [],
      confidence: scene.entityConfidence ?? Object.fromEntries(scene.characterList.map((character) => [character.id, 1])),
      evidence: scene.entityEvidence ?? Object.fromEntries(scene.characterList.map((character) => [character.id, ['authored scene annotation']])),
      visibleObjects: scene.visibleObjects ?? (object ? [object] : []),
    },
    dialogueReferences: scene.dialogueReferences ?? [],
    events: [scene.voiceNarration],
    emotions,
    relationships: relationshipText,
    objects: scene.visibleObjects ?? (object ? [object] : []),
    conversationSummary: scene.subtitle,
    importantDetails: object ? [scene.highlightObject.reason] : [],
    causeEffect: [{ cause: scene.causeEffectData.cause, effect: scene.causeEffectData.effect }],
    timelinePosition: scene.timelineData.find((item) => item.time === 'Now')?.label ?? 'Current story moment',
    memoryCheckpoint: [scene.voiceNarration],
    accessibility: {
      possibleConfusions: [`Who is involved in ${scene.subtitle.toLowerCase()}`, `Why does this moment matter?`],
      support: {
        emotions: emotions.map((item) => item.explanation),
        characters: visibleCharacterRecords.map((character) => `${character.name}: ${character.emotionalState}.`),
        relationships: relationshipText,
        plot: [scene.voiceNarration],
        memory: [scene.voiceNarration],
        objects: object ? [`${object}: ${scene.highlightObject.reason}`] : [],
        nonverbal: [scene.subtitle],
      },
      memoryPoints: [scene.voiceNarration],
      prompts,
    },
    visualAids: [
      { type: 'summary', content: scene.voiceNarration, visualizationDescription: 'A simple summary of the active story moment.' },
      { type: 'timeline', content: scene.timelineData.map((item) => item.label).join(' → '), visualizationDescription: 'Where this scene sits in the story.' },
      ...(emotions.length ? [{ type: 'emotion' as const, content: emotions.map((item) => item.explanation).join(' '), visualizationDescription: 'Character feelings in this scene.' }] : []),
      ...(object ? [{ type: 'object' as const, content: `${object}: ${scene.highlightObject.reason}`, visualizationDescription: 'An important object to notice.' }] : []),
    ],
  }
}

/** Converts the curated demo annotations into the same immutable graph emitted by preprocessing. */
export function graphFromMovieData(movie: MovieData): NarrativeGraph {
  const scenes = movie.scenes.map((scene, index) => sceneNode(scene, movie.scenes[index + 1]))
  const characters: NarrativeCharacter[] = movie.canonicalCharacters ?? movie.scenes.flatMap((scene) => scene.characterList).filter((character, index, items) => items.findIndex((item) => item.id === character.id) === index).map((character) => ({
    id: character.id, name: character.name, description: character.role, personality: character.emotionalState, goals: [], relationships: [], firstAppearance: movie.scenes.find((scene) => scene.characterList.some((item) => item.id === character.id))?.timestamp ?? 0, importantInformation: [character.role], visualDescription: '', confidenceThreshold: 0.7,
  }))
  return { version: 1, movie: { id: movie.id, title: movie.title, type: 'movie', metadata: { runtime: movie.runtime, genre: movie.genre } }, scenes, characters, relationships: [] }
}
