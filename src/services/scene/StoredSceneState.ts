/** Adapts permanent backend scene knowledge to the existing prompt/drawer/companion UI contract. */
import type { CanonicalMagiFabScene, ProcessedChunk } from '../backend/MoviePreprocessingBackendService'
import type { SceneState } from './SceneState'

export function storedSceneToSceneState(record: CanonicalMagiFabScene, chunk: ProcessedChunk): SceneState {
  const scene = record.canonical_scene
  const confidence = score(scene.confidence)
  const characters = scene.characters.map((character, index) => ({
    character_id: `${record.id}:character:${index}`,
    name: character.name,
    reminder: character.description,
    confidence: score(character.confidence),
  }))
  const relationships = scene.relationships.map((relationship, index) => ({
    relationship_id: `${record.id}:relationship:${index}`,
    summary: `${relationship.subject} ${relationship.relationship} ${relationship.object}.`,
    confidence: score(relationship.confidence),
  }))
  const timeline = unique([
    ...scene.timeline.map((item) => item.event),
    ...scene.events,
    ...scene.locations.map((location) => `Location: ${location}`),
  ])
  const memory = unique(scene.important_memory).map((summary) => ({ summary, confidence }))
  const emotions = unique(scene.emotions).map((summary, index) => ({ emotion_id: `${record.id}:emotion:${index}`, summary, confidence }))
  const importantObjects = unique([
    ...scene.objects.map((object) => object.name),
    scene.visual_aid.description,
  ])
  const promptDefinitions = promptDefinitionsFor(record.id, scene)

  return {
    sceneId: record.id,
    interval: chunk.sequence_number,
    startTime: chunk.start_seconds,
    endTime: chunk.end_seconds,
    sceneSummary: scene.scene_summary,
    subtitle: scene.accessibility_explanation,
    characters,
    relationships,
    timeline,
    memory,
    importantObjects,
    emotions,
    causeEffect: scene.cause_effect,
    visualAid: scene.visual_aid,
    promptBubbles: promptDefinitions.map(({ answer: _answer, ...prompt }) => prompt),
    promptAnswers: Object.fromEntries(promptDefinitions.map((prompt) => [prompt.id, prompt.answer])),
    accessibilityHints: {
      vocabulary: scene.objects.map((object, index) => ({ term: object.name, simple_definition: object.description, confidence: score(object.confidence), id: `${record.id}:object:${index}` })),
      emotions,
    },
    conversation: {
      sceneExplanation: scene.accessibility_explanation,
      simplifications: scene.difficulty_points.map((simple_text, index) => ({ dialogue_id: `${record.id}:difficulty:${index}`, simple_text, confidence })),
    },
    story: {
      currentGoal: scene.events[0] ?? null,
      timelinePosition: scene.timeline[0]?.event ?? scene.events[0] ?? null,
      storySoFar: scene.important_memory,
      unresolvedThreads: [],
    },
    confidence,
    companionEnabled: true,
    metadata: { movieId: record.movie_id, generatedAt: Date.parse(record.updated_at) || Date.now(), knowledgeRevision: 1, frameTimestamp: chunk.start_seconds },
  }
}

function promptDefinitionsFor(sceneId: string, scene: CanonicalMagiFabScene['canonical_scene']) {
  const candidates = [
    { kind: 'scene_summary', label: 'What is happening?', question: 'What is happening right now?', answer: scene.accessibility_explanation },
    scene.events[0] ? { kind: 'important_event', label: 'Important event', question: 'What important event just happened?', answer: scene.events[0] } : null,
    scene.emotions[0] ? { kind: 'emotion', label: 'Feelings', question: 'How does this moment feel?', answer: scene.emotions[0] } : null,
    scene.important_memory[0] ? { kind: 'memory', label: 'Remember this', question: 'What should I remember?', answer: scene.important_memory[0] } : null,
    { kind: 'accessibility', label: 'Simple explanation', question: 'Can you explain this simply?', answer: scene.accessibility_explanation },
  ].filter((item): item is { kind: string; label: string; question: string; answer: string } => Boolean(item))
  return candidates.slice(0, 5).map((item, index) => ({ id: `${sceneId}:prompt:${item.kind}`, kind: item.kind, label: item.label, question: item.question, answer: item.answer, priority: candidates.length - index }))
}

function unique(values: Array<string | null | undefined>) { return [...new Set(values.filter((value): value is string => Boolean(value?.trim())))] }
function score(value: 'high' | 'medium' | 'low') { return value === 'high' ? 1 : value === 'medium' ? .7 : .4 }
