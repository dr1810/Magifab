import type {
  BackendConversationSimplification,
  BackendEmotionSummary,
  BackendMemoryReminder,
  BackendRelationshipSummary,
  BackendVocabularyAssistance,
  IntervalState,
} from '../backend/CompanionBackendService'

export type SceneState = {
  sceneId: string
  interval: number
  startTime: number
  endTime: number | null
  sceneSummary: string
  subtitle: string | null
  characters: IntervalState['characters']
  relationships: BackendRelationshipSummary[]
  timeline: string[]
  memory: BackendMemoryReminder[]
  importantObjects: string[]
  emotions: BackendEmotionSummary[]
  causeEffect: Array<{ cause: string; effect: string }>
  visualAid?: { type: string; description: string }
  promptBubbles: IntervalState['prompts']['prompt_bubbles']
  /** Persisted answers supplied with backend prompt candidates; no runtime model call is required. */
  promptAnswers?: Record<string, string>
  accessibilityHints: { vocabulary: BackendVocabularyAssistance[]; emotions: BackendEmotionSummary[] }
  conversation: { sceneExplanation: string; simplifications: BackendConversationSimplification[] }
  story: { currentGoal: string | null; timelinePosition: string | null; storySoFar: string[]; unresolvedThreads: string[] }
  phase?: 'intro_credits' | 'setup' | 'rising_action' | 'climax' | 'resolution' | 'transition'
  confidence?: number
  companionEnabled?: boolean
  metadata: { movieId: string; generatedAt: number; knowledgeRevision: number; frameTimestamp: number | null }
}

export function toSceneState(snapshot: IntervalState, subtitle: string | null = null): SceneState {
  const { metadata, storyState, timelineMemory, visualDrawer } = snapshot
  return {
    sceneId: metadata.interval_id,
    interval: metadata.interval_number,
    startTime: metadata.start_time,
    endTime: metadata.end_time,
    sceneSummary: storyState.scene_summary ?? visualDrawer.now ?? 'The story continues in this moment.',
    subtitle,
    characters: snapshot.characters,
    relationships: snapshot.relationships,
    timeline: unique([...visualDrawer.timeline, timelineMemory.previous_event, timelineMemory.current_event, timelineMemory.next_event]),
    memory: snapshot.memory,
    importantObjects: unique([...visualDrawer.objects, ...snapshot.semanticMemoryAfter.important_objects, ...snapshot.accessibilityHints.vocabulary.map((item) => item.term)]),
    emotions: snapshot.accessibilityHints.emotions,
    causeEffect: visualDrawer.cause_effect,
    promptBubbles: snapshot.prompts.prompt_bubbles,
    accessibilityHints: snapshot.accessibilityHints,
    conversation: { sceneExplanation: snapshot.conversationContext.scene_explanation, simplifications: snapshot.conversationContext.simplifications },
    story: { currentGoal: storyState.current_goal, timelinePosition: storyState.timeline_position ?? timelineMemory.timeline_position, storySoFar: storyState.story_so_far, unresolvedThreads: storyState.unresolved_threads },
    metadata: { movieId: metadata.movie_id, generatedAt: Date.now(), knowledgeRevision: metadata.knowledge_revision, frameTimestamp: snapshot.cacheMetadata.frame_hash ? metadata.start_time : null },
  }
}

function unique(values: Array<string | null | undefined>) {
  return [...new Set(values.filter((value): value is string => Boolean(value)))]
}
