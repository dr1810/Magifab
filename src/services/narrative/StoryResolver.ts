import type { SceneState } from '../scene/SceneState'
import type { AIProfile } from '../../types/user'
import { profileNeeds, type AccessibilityNeed, type NarrativeGraph, type NarrativePrompt, type NarrativeScene } from './types'
import { VisualGroundingResolver } from './VisualGroundingResolver'
import { DialogueResolver } from './DialogueResolver'
import { fallbackBeat } from './StoryBeatBuilder'
import type { StoryBeat } from './types'

export class StoryResolver {
  private readonly grounding: VisualGroundingResolver
  private readonly dialogue = new DialogueResolver()

  constructor(private readonly graph: NarrativeGraph) {
    this.grounding = new VisualGroundingResolver(graph.characters)
  }

  resolveTime(currentTime: number, profile: AIProfile | null): SceneState | null {
    const scene = this.graph.scenes.find((item) => currentTime >= item.startTime && (item.endTime === null || currentTime < item.endTime)) ?? this.graph.scenes.at(-1)
    return scene ? this.hydrate(scene, this.resolveBeat(scene, currentTime), profile) : null
  }

  resolvePage(page: number, profile: AIProfile | null): SceneState | null {
    const scene = this.graph.scenes.find((item) => item.pageReference && page >= item.pageReference.start && page <= item.pageReference.end)
    return scene ? this.hydrate(scene, this.resolveBeat(scene, scene.startTime), profile) : null
  }

  private resolveBeat(scene: NarrativeScene, timestamp: number): StoryBeat {
    const beats = scene.storyBeats?.length ? scene.storyBeats : [fallbackBeat(scene)]
    return beats.find((beat) => timestamp >= beat.startTime && (beat.endTime === null || timestamp < beat.endTime))
      ?? beats.reduce((closest, beat) => distanceToBeat(beat, timestamp) < distanceToBeat(closest, timestamp) ? beat : closest)
  }

  private hydrate(scene: NarrativeScene, beat: StoryBeat, profile: AIProfile | null): SceneState {
    const isIntro = beat.phase === 'intro_credits'
    const isConfident = beat.confidence >= 0.6
    const needs = profileNeeds(profile)
    const beatScene: NarrativeScene = {
      ...scene,
      sceneId: beat.id,
      startTime: beat.startTime,
      endTime: beat.endTime,
      summary: beat.summary,
      visualGrounding: beat.visualGrounding,
      characters: beat.visibleEntityIds,
      relationships: beat.relationships,
      emotions: beat.emotions,
      objects: beat.objects,
      causeEffect: beat.causeEffect,
      memoryCheckpoint: beat.memory,
      conversationSummary: beat.drawerState.conversationSummary ?? scene.conversationSummary,
      timelinePosition: beat.drawerState.timelinePosition ?? scene.timelinePosition,
      accessibility: { ...scene.accessibility, support: beat.drawerState.support ?? scene.accessibility.support, prompts: beat.promptCandidates },
    }
    const grounding = this.grounding.resolve(beatScene)
    const visibleCharacters = grounding.visible
    const visibleIds = new Set(visibleCharacters.map((character) => character.id))
    const visibleNames = new Set(visibleCharacters.map((character) => character.name))
    const prompts = !isIntro && isConfident && visibleCharacters.length ? selectPrompts(beatScene.accessibility.prompts, needs, visibleIds) : []
    const support = (need: AccessibilityNeed) => beatScene.accessibility.support[need] ?? []
    const priorScenes = this.graph.scenes.filter((item) => item.startTime < beat.startTime)
    const dialogueReferences = this.dialogue.resolve(beatScene, priorScenes)
    const emotions = beatScene.emotions.filter((emotion) => !emotion.character || visibleNames.has(emotion.character))
    const relationships = beatScene.relationships.filter((relationship) => [...visibleNames].some((name) => relationship.includes(name)))
    const sceneSummary = isIntro ? beat.summary : isConfident && visibleCharacters.length ? beat.summary : 'Current scene is still being analysed.'
    return {
      sceneId: beat.id, interval: Math.floor(beat.startTime / 30), startTime: beat.startTime, endTime: beat.endTime, sceneSummary, subtitle: isIntro ? beat.summary : isConfident ? beatScene.conversationSummary : 'Current scene is still being analysed.',
      characters: isIntro || !isConfident ? [] : visibleCharacters.map((character) => ({ character_id: character.id, name: character.name, reminder: support('characters').find((item) => item.includes(character.name)) ?? character.description, confidence: beatScene.visualGrounding.confidence[character.id] })),
      relationships: isIntro || !isConfident ? [] : relationships.map((summary, index) => ({ relationship_id: `${beat.id}:relationship:${index}`, summary, confidence: 1 })),
      timeline: [beatScene.timelinePosition, ...beatScene.events], memory: isIntro || !isConfident ? [] : beatScene.memoryCheckpoint.map((summary) => ({ summary, confidence: 1 })), importantObjects: isIntro || !isConfident ? [] : beatScene.visualGrounding.visibleObjects,
      emotions: isIntro || !isConfident ? [] : emotions.map((item, index) => ({ emotion_id: `${beat.id}:emotion:${index}`, summary: item.explanation, confidence: 1 })),
      causeEffect: isIntro || !isConfident ? [] : beatScene.causeEffect,
      promptBubbles: prompts.map((prompt) => ({ id: prompt.id, kind: prompt.triggerType, label: prompt.difficultyCategory, question: prompt.question, priority: prompt.priority ?? 1 })),
      accessibilityHints: { vocabulary: isIntro || !isConfident ? [] : support('vocabulary').map((simple_definition, index) => ({ term: beatScene.visualGrounding.visibleObjects[index] ?? 'Word help', simple_definition, confidence: 1 })), emotions: isIntro || !isConfident ? [] : emotions.map((item, index) => ({ emotion_id: `${beat.id}:emotion:${index}`, summary: item.explanation, confidence: 1 })) },
      conversation: { sceneExplanation: isIntro ? beat.summary : beatScene.conversationSummary, simplifications: isIntro || !isConfident ? [] : [...support('conversations'), ...dialogueReferences.map((reference) => `${reference.pronoun} refers to ${reference.entityId}. ${reference.evidence}`)].map((simple_text, index) => ({ dialogue_id: `${beat.id}:conversation:${index}`, simple_text, confidence: 1 })) },
      story: { currentGoal: isIntro || !isConfident ? null : beatScene.events[0] ?? null, timelinePosition: beatScene.timelinePosition, storySoFar: beatScene.memoryCheckpoint, unresolvedThreads: [] },
      phase: beat.phase, confidence: beat.confidence, companionEnabled: !isIntro && isConfident,
      metadata: { movieId: this.graph.movie.id, generatedAt: 0, knowledgeRevision: this.graph.version, frameTimestamp: null },
    }
  }

}

function distanceToBeat(beat: StoryBeat, timestamp: number) {
  if (timestamp < beat.startTime) return beat.startTime - timestamp
  if (beat.endTime === null || timestamp <= beat.endTime) return 0
  return timestamp - beat.endTime
}

export function answerPrompt(state: SceneState, question: string) {
  if (/who|character/i.test(question)) return state.characters.map((item) => item.reminder).join(' ') || state.sceneSummary
  if (/feel|emotion|why.*(upset|happy|angry|annoyed|frustrated|afraid|scared)/i.test(question)) return state.emotions[0]?.summary ?? state.sceneSummary
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
