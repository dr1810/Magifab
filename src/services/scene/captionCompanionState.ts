import type { MovieId, SceneData } from '../../types/movie'
import type { SceneState } from './SceneState'

export function createCaptionCompanionState(movieId: MovieId, scene: SceneData | null, timestamp: number): SceneState | null {
  if (!scene?.subtitle) return null
  const caption = scene.subtitle.replace(/[.?!]+$/, '')
  const buck = /buck/i.test(caption)
  const character = buck ? 'Buck' : scene.characterList[0]?.name ?? 'The character'
  const emotion = buck ? 'Calm, safe, and happy' : scene.emotion || 'Calm and curious'
  const objects = buck ? ['Forest', 'Butterflies', 'Flowers'] : [scene.highlightObject.name || 'Important detail']
  const relationship = buck ? 'Buck lives peacefully in the forest.' : `${character} is part of this moment.`
  const explanation = buck
    ? 'Buck is enjoying a quiet, peaceful moment in the forest.'
    : `${caption}. This is the important part of the story right now.`
  const prompts = buck
    ? [['Who is Buck?', 'Character'], ['Why is Buck happy?', 'Feelings'], ['Where is Buck?', 'Place'], ['What should I remember?', 'Remember']]
    : [['Who is here?', 'Characters'], ['What is happening?', 'Story'], ['How does this feel?', 'Feelings'], ['What should I remember?', 'Remember']]

  return {
    sceneId: `caption:${scene.sceneId}`,
    interval: Math.floor(timestamp / 30),
    startTime: timestamp,
    endTime: timestamp + 30,
    sceneSummary: explanation,
    subtitle: scene.subtitle,
    characters: [{ character_id: character.toLowerCase().replace(/\s+/g, '-'), name: character, reminder: buck ? 'Main forest rabbit. Currently relaxed.' : 'Important in this moment.', confidence: 1 }],
    relationships: [{ relationship_id: `${character}-scene`, summary: relationship, confidence: 1 }],
    timeline: [buck ? 'Beginning of the story.' : 'This is the current part of the story.'],
    memory: [{ summary: buck ? 'Remember: Buck enjoys living peacefully.' : `Remember: ${caption}.`, confidence: 1 }],
    importantObjects: objects,
    emotions: [{ emotion_id: `${character}-emotion`, summary: `${character} feels ${emotion.toLowerCase()}.`, confidence: 1 }],
    causeEffect: [{ cause: buck ? 'Buck has not encountered danger yet.' : `${character} is safe in this moment.`, effect: buck ? 'He can enjoy the peaceful forest.' : 'The story can continue calmly.' }],
    promptBubbles: prompts.map(([question, label], index) => ({ id: `caption:${scene.sceneId}:${index}`, kind: 'caption', label, question, priority: prompts.length - index })),
    accessibilityHints: { vocabulary: [], emotions: [{ emotion_id: `${character}-emotion`, summary: `${character} feels ${emotion.toLowerCase()}.`, confidence: 1 }] },
    conversation: { sceneExplanation: explanation, simplifications: [] },
    story: { currentGoal: buck ? 'Enjoy a peaceful morning.' : 'Understand what is happening.', timelinePosition: buck ? 'Beginning of the story.' : 'Current story moment.', storySoFar: [explanation], unresolvedThreads: [] },
    metadata: { movieId, generatedAt: Date.now(), knowledgeRevision: 1, frameTimestamp: timestamp },
  }
}

export function captionPromptAnswer(state: SceneState, question: string) {
  if (/who/i.test(question)) return state.characters[0]?.reminder ?? state.sceneSummary
  if (/feel|happy|emotion/i.test(question)) return state.emotions[0]?.summary ?? state.sceneSummary
  if (/where|place/i.test(question)) return state.relationships[0]?.summary ?? state.sceneSummary
  if (/remember/i.test(question)) return state.memory[0]?.summary ?? state.sceneSummary
  return state.sceneSummary
}
