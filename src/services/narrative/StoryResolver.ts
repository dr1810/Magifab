import type { SceneState } from '../scene/SceneState'
import type { AIProfile } from '../../types/user'
import { profileNeeds, type AccessibilityNeed, type NarrativeGraph, type NarrativePrompt, type NarrativeScene } from './types'
import { VisualGroundingResolver } from './VisualGroundingResolver'
import { DialogueResolver } from './DialogueResolver'

export class StoryResolver {
  private readonly grounding: VisualGroundingResolver
  private readonly dialogue = new DialogueResolver()

  constructor(private readonly graph: NarrativeGraph) {
    this.grounding = new VisualGroundingResolver(graph.characters)
  }

  resolveTime(currentTime: number, profile: AIProfile | null): SceneState | null {
    const scene = this.graph.scenes.find((item) => currentTime >= item.startTime && (item.endTime === null || currentTime < item.endTime)) ?? this.graph.scenes.at(-1)
    return scene ? this.hydrate(scene, profile) : null
  }

  resolvePage(page: number, profile: AIProfile | null): SceneState | null {
    const scene = this.graph.scenes.find((item) => item.pageReference && page >= item.pageReference.start && page <= item.pageReference.end)
    return scene ? this.hydrate(scene, profile) : null
  }

  private hydrate(scene: NarrativeScene, profile: AIProfile | null): SceneState {
    const needs = profileNeeds(profile)
    const grounding = this.grounding.resolve(scene)
    const visibleCharacters = grounding.visible
    const visibleIds = new Set(visibleCharacters.map((character) => character.id))
    const visibleNames = new Set(visibleCharacters.map((character) => character.name))
    const prompts = visibleCharacters.length ? selectPrompts(scene.accessibility.prompts, needs, visibleIds) : []
    const support = (need: AccessibilityNeed) => scene.accessibility.support[need] ?? []
    const priorScenes = this.graph.scenes.filter((item) => item.startTime < scene.startTime)
    const dialogueReferences = this.dialogue.resolve(scene, priorScenes)
    const emotions = scene.emotions.filter((emotion) => !emotion.character || visibleNames.has(emotion.character))
    const relationships = scene.relationships.filter((relationship) => [...visibleNames].some((name) => relationship.includes(name)))
    return {
      sceneId: scene.sceneId, interval: Math.floor(scene.startTime / 30), startTime: scene.startTime, endTime: scene.endTime, sceneSummary: visibleCharacters.length ? scene.summary : 'Character identity is unclear in this moment. The scene continues.', subtitle: scene.conversationSummary,
      characters: visibleCharacters.map((character) => ({ character_id: character.id, name: character.name, reminder: support('characters').find((item) => item.includes(character.name)) ?? character.description, confidence: scene.visualGrounding.confidence[character.id] })),
      relationships: relationships.map((summary, index) => ({ relationship_id: `${scene.sceneId}:relationship:${index}`, summary, confidence: 1 })),
      timeline: [scene.timelinePosition, ...scene.events], memory: scene.memoryCheckpoint.map((summary) => ({ summary, confidence: 1 })), importantObjects: scene.visualGrounding.visibleObjects,
      emotions: emotions.map((item, index) => ({ emotion_id: `${scene.sceneId}:emotion:${index}`, summary: item.explanation, confidence: 1 })),
      causeEffect: scene.causeEffect,
      promptBubbles: prompts.map((prompt) => ({ id: prompt.id, kind: prompt.triggerType, label: prompt.difficultyCategory, question: prompt.question, priority: prompt.priority ?? 1 })),
      accessibilityHints: { vocabulary: support('vocabulary').map((simple_definition, index) => ({ term: scene.visualGrounding.visibleObjects[index] ?? 'Word help', simple_definition, confidence: 1 })), emotions: emotions.map((item, index) => ({ emotion_id: `${scene.sceneId}:emotion:${index}`, summary: item.explanation, confidence: 1 })) },
      conversation: { sceneExplanation: scene.conversationSummary, simplifications: [...support('conversations'), ...dialogueReferences.map((reference) => `${reference.pronoun} refers to ${reference.entityId}. ${reference.evidence}`)].map((simple_text, index) => ({ dialogue_id: `${scene.sceneId}:conversation:${index}`, simple_text, confidence: 1 })) },
      story: { currentGoal: scene.events[0] ?? null, timelinePosition: scene.timelinePosition, storySoFar: scene.memoryCheckpoint, unresolvedThreads: [] },
      metadata: { movieId: this.graph.movie.id, generatedAt: 0, knowledgeRevision: this.graph.version, frameTimestamp: null },
    }
  }

}

export function answerPrompt(state: SceneState, question: string) {
  if (/who|character/i.test(question)) return state.characters.map((item) => item.reminder).join(' ') || state.sceneSummary
  if (/feel|emotion|why.*upset|happy/i.test(question)) return state.emotions[0]?.summary ?? state.sceneSummary
  if (/remember|before|earlier/i.test(question)) return state.memory[0]?.summary ?? state.sceneSummary
  if (/relationship|together/i.test(question)) return state.relationships[0]?.summary ?? state.sceneSummary
  if (/object|what is this|word/i.test(question)) return state.importantObjects[0] ?? state.sceneSummary
  return state.sceneSummary
}

function selectPrompts(prompts: NarrativePrompt[], needs: Set<AccessibilityNeed>, visibleIds: Set<string>) {
  const grounded = prompts.filter((prompt) => !prompt.subjectEntityIds?.length || prompt.subjectEntityIds.every((id) => visibleIds.has(id)))
  const personalized = grounded.filter((prompt) => needs.has(prompt.triggerType))
  return (personalized.length ? personalized : grounded).slice(0, 4)
}
