/**
 * Retained only as a type module for legacy local demo data. The frontend no
 * longer prepares intervals or calls a companion pipeline during playback.
 */
export type BackendCharacterCard = { character_id: string; name: string; reminder: string; confidence: number }
export type BackendRelationshipSummary = { relationship_id: string; summary: string; confidence: number }
export type BackendEmotionSummary = { emotion_id: string; summary: string; confidence: number }
export type BackendMemoryReminder = { summary: string; confidence: number }
export type BackendVocabularyAssistance = { id?: string; term: string; simple_definition: string; confidence: number }
export type BackendConversationSimplification = { dialogue_id: string; simple_text: string; confidence: number }
export type IntervalState = {
  metadata: { interval_id: string; movie_id: string; start_time: number; end_time: number | null; interval_number: number; knowledge_revision: number }
  prompts: { prompt_bubbles: Array<{ id: string; kind: string; label: string; question: string; priority: number }> }
  visualDrawer: { now?: string | null; timeline: string[]; objects: string[]; cause_effect: Array<{ cause: string; effect: string }> }
  storyState: { scene_summary: string | null; current_goal: string | null; timeline_position: string | null; story_so_far: string[]; unresolved_threads: string[] }
  characters: BackendCharacterCard[]; relationships: BackendRelationshipSummary[]; memory: BackendMemoryReminder[]
  conversationContext: { scene_explanation: string; simplifications: BackendConversationSimplification[] }
  accessibilityHints: { vocabulary: BackendVocabularyAssistance[]; emotions: BackendEmotionSummary[] }
  semanticMemoryAfter: { important_objects: string[] }; timelineMemory: { timeline_position: string | null; previous_event: string | null; current_event: string | null; next_event: string | null }
  cacheMetadata: { frame_hash: string | null }
}
