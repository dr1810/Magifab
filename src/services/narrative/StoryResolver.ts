import type { SceneState } from '../scene/SceneState'
import type { AIProfile } from '../../types/user'
import { profileNeeds, type AccessibilityNeed, type NarrativeGraph, type NarrativePrompt, type NarrativeScene } from './types'

export class StoryResolver {
  constructor(private readonly graph: NarrativeGraph) {}

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
    const prompts = selectPrompts(scene.accessibility.prompts, needs)
    const support = (need: AccessibilityNeed) => scene.accessibility.support[need] ?? []
    return {
      sceneId: scene.sceneId, interval: Math.floor(scene.startTime / 30), startTime: scene.startTime, endTime: scene.endTime, sceneSummary: scene.summary, subtitle: scene.conversationSummary,
      characters: scene.characters.map((name) => ({ character_id: name.toLowerCase().replace(/\s+/g, '-'), name, reminder: support('characters').find((item) => item.includes(name)) ?? `${name} is part of this scene.`, confidence: 1 })),
      relationships: scene.relationships.map((summary, index) => ({ relationship_id: `${scene.sceneId}:relationship:${index}`, summary, confidence: 1 })),
      timeline: [scene.timelinePosition, ...scene.events], memory: scene.memoryCheckpoint.map((summary) => ({ summary, confidence: 1 })), importantObjects: scene.objects,
      emotions: scene.emotions.map((item, index) => ({ emotion_id: `${scene.sceneId}:emotion:${index}`, summary: item.explanation, confidence: 1 })),
      causeEffect: scene.importantDetails.map((detail) => ({ cause: scene.events[0] ?? scene.summary, effect: detail })),
      promptBubbles: prompts.map((prompt) => ({ id: prompt.id, kind: prompt.triggerType, label: prompt.difficultyCategory, question: prompt.question, priority: prompt.priority ?? 1 })),
      accessibilityHints: { vocabulary: support('vocabulary').map((simple_definition, index) => ({ term: scene.objects[index] ?? 'Word help', simple_definition, confidence: 1 })), emotions: scene.emotions.map((item, index) => ({ emotion_id: `${scene.sceneId}:emotion:${index}`, summary: item.explanation, confidence: 1 })) },
      conversation: { sceneExplanation: scene.conversationSummary, simplifications: support('conversations').map((simple_text, index) => ({ dialogue_id: `${scene.sceneId}:conversation:${index}`, simple_text, confidence: 1 })) },
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

function selectPrompts(prompts: NarrativePrompt[], needs: Set<AccessibilityNeed>) {
  const personalized = prompts.filter((prompt) => needs.has(prompt.triggerType))
  return (personalized.length ? personalized : prompts).slice(0, 4)
}
