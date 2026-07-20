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
  return resolvePromptAnswer(state, question).text
}

export type PromptAnswer = {
  type: StoryQuestionType
  text: string
  entityIds: string[]
  evidence: string[]
}

/**
 * Retrieves a response from the current SceneState.  It intentionally has no
 * generative fallback: an answer without a grounded state remains unavailable.
 */
export function resolvePromptAnswer(state: SceneState, question: string): PromptAnswer {
  const type = classifyStoryQuestion(question)
  const mentionedCharacters = findMentionedCharacters(question, state)
  const answer = (text: string, entityIds: string[] = [], evidence: string[] = []): PromptAnswer => ({ type, text: cleanText(text), entityIds, evidence })

  if (type === 'character') {
    if (asksForAllCharacters(question)) {
      const characters = state.characters.map((character) => `${character.name} is ${withoutNamePrefix(character.name, character.reminder)}`)
      return answer(characters.length ? characters.join(' ') : unavailable('visible character information'), state.characters.map((character) => character.character_id), state.characters.map((character) => character.reminder))
    }
    const character = mentionedCharacters[0]
    return character
      ? answer(`${character.name} is ${withoutNamePrefix(character.name, character.reminder)}`, [character.character_id], [character.reminder])
      : answer(unavailable('that character in this story moment'))
  }

  if (type === 'emotion') {
    if (!mentionedCharacters.length && hasUnmatchedEntityTarget(question)) return answer(unavailable('emotion information for that character'))
    const emotion = findByMention(state.emotions, mentionedCharacters.map((character) => character.name), (item) => item.summary)
    return emotion ? answer(emotion.summary, mentionedCharacters.map((character) => character.character_id), [emotion.summary]) : answer(unavailable('grounded emotion information'))
  }

  if (type === 'relationship') {
    if (!mentionedCharacters.length && /\bbetween\b/i.test(question)) return answer(unavailable('relationship information for those characters'))
    const relationship = findByMention(state.relationships, mentionedCharacters.map((character) => character.name), (item) => item.summary)
    return relationship ? answer(relationship.summary, mentionedCharacters.map((character) => character.character_id), [relationship.summary]) : answer(unavailable('grounded relationship information'))
  }

  if (type === 'timeline') {
    const timeline = firstText(state.story.timelinePosition, state.timeline[0], state.timeline.at(-1))
    return answer(timeline ?? unavailable('timeline information'), [], timeline ? [timeline] : [])
  }

  if (type === 'memory') {
    const memory = firstText(state.memory[0]?.summary, state.story.storySoFar[0])
    return answer(memory ?? unavailable('an earlier-story reminder'), [], memory ? [memory] : [])
  }

  if (type === 'causeEffect') {
    const connection = state.causeEffect[0]
    return connection
      ? answer(`Because ${sentenceFragment(connection.cause)}, ${sentenceFragment(connection.effect)}.`, [], [connection.cause, connection.effect])
      : answer(unavailable('a cause-and-effect explanation'))
  }

  if (type === 'object') {
    const object = findMentionedObject(question, state.importantObjects) ?? state.importantObjects[0]
    const vocabulary = state.accessibilityHints.vocabulary.find((item) => object && item.term.toLowerCase() === object.toLowerCase())
    return vocabulary
      ? answer(`${vocabulary.term} means ${sentenceFragment(vocabulary.simple_definition)}.`, [], [vocabulary.term, vocabulary.simple_definition])
      : object ? answer(`${object} is the important object visible in this story moment.`, [], [object]) : answer(unavailable('a grounded object'))
  }

  if (type === 'conversation') {
    const conversation = firstText(state.conversation.simplifications[0]?.simple_text, state.conversation.sceneExplanation, state.subtitle)
    return answer(conversation ?? unavailable('conversation information'), [], conversation ? [conversation] : [])
  }

  if (type === 'storyNow') {
    const storyNow = firstText(state.sceneSummary, state.story.currentGoal)
    return answer(storyNow ?? unavailable('the current story moment'), [], storyNow ? [storyNow] : [])
  }

  const summary = firstText(state.sceneSummary, state.story.currentGoal, state.timeline[0], state.memory[0]?.summary)
  return answer(summary ?? unavailable('a story summary'), [], summary ? [summary] : [])
}

export type StoryQuestionType = 'character' | 'emotion' | 'relationship' | 'timeline' | 'memory' | 'causeEffect' | 'object' | 'conversation' | 'storyNow' | 'summary'

export function classifyStoryQuestion(question: string): StoryQuestionType {
  const value = question.toLowerCase()
  if (/remember|before|earlier|previous|already happened/.test(value)) return 'memory'
  if (/conversation|dialogue|say|said|mean|talking|discussing/.test(value)) return 'conversation'
  if (/object|item|thing|what is this|what matters|important.*(thing|object)/.test(value)) return 'object'
  if (/relationship|between|connected|together|how.*(get along|relate)/.test(value)) return 'relationship'
  if (/timeline|when|what.*next|where.*(story|timeline)/.test(value)) return 'timeline'
  if (/feel|feeling|emotion|angry|annoyed|upset|happy|frustrated|afraid|scared|sad|worried/.test(value)) return 'emotion'
  if (/what caused|cause|because|led to|how did.*happen|why did.*(happen|start|change)/.test(value)) return 'causeEffect'
  if (/who|character|tell me about|role/.test(value)) return 'character'
  if (/what.*(happening|going on|now)|story now|right now/.test(value)) return 'storyNow'
  return 'summary'
}

function findMentionedCharacters(question: string, state: SceneState) {
  const value = question.toLowerCase()
  return state.characters.filter((item) => value.includes(item.name.toLowerCase()))
}

function findMentionedObject(question: string, objects: string[]) {
  const value = question.toLowerCase()
  return objects.find((object) => value.includes(object.toLowerCase()))
}

function asksForAllCharacters(question: string) {
  return /all (the )?(people|characters)|who('?s| is) here|who are they/.test(question.toLowerCase())
}

function hasUnmatchedEntityTarget(question: string) {
  return /\b(?:why|how)\s+(?:is|are|does|do)\s+(?!they\b|he\b|she\b|this\b|that\b|it\b)/i.test(question)
}

function findByMention<T>(items: T[], names: string[], toText: (item: T) => string) {
  if (!items.length) return undefined
  if (!names.length) return items[0]
  return items.find((item) => names.some((name) => toText(item).toLowerCase().includes(name.toLowerCase())))
}

function withoutNamePrefix(name: string, value: string) {
  return value.replace(new RegExp(`^${escapeRegExp(name)}\\s*:\\s*`, 'i'), '').trim()
}

function sentenceFragment(value: string) {
  return value.replace(/[.?!]+$/, '').replace(/^(because|so)\s+/i, '').trim()
}

function cleanText(value: string) {
  return value.replace(/\b([A-Z][\w’'-]+):\s*\1:\s*/g, '$1: ').replace(/\s{2,}/g, ' ').trim()
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function firstText(...values: Array<string | null | undefined>) {
  return values.find((value): value is string => Boolean(value?.trim()))
}

function unavailable(subject: string) {
  return `I do not have verified ${subject} for this story moment yet.`
}

function selectPrompts(prompts: NarrativePrompt[], needs: Set<AccessibilityNeed>, visibleIds: Set<string>) {
  const grounded = prompts.filter((prompt) => !prompt.subjectEntityIds?.length || prompt.subjectEntityIds.every((id) => visibleIds.has(id)))
  const personalized = grounded.filter((prompt) => needs.has(prompt.triggerType))
  return (personalized.length ? personalized : grounded).slice(0, 4)
}
