import type { StoryBeat } from '../services/narrative/types'

/** Opaque backend IDs support uploaded movies as well as the bundled demo catalog. */
export type MovieId = string

export type AccessibilityTag =
  | 'Audio Description'
  | 'High Contrast Friendly'
  | 'Simple Language Prompts'
  | 'Keyboard Navigation'
  | 'Reduced Motion Supported'

export type CompanionTheme = 'ocean' | 'sun'

export type PromptQuestion = {
  id: string
  label: string
  question: string
  explanation: string
}

export type CharacterInfo = {
  id: string
  name: string
  role: string
  emotionalState: string
}

export type RelationshipEdge = {
  from: string
  to: string
  label: string
}

export type TimelineItem = {
  id: string
  time: string
  label: string
}

export type CauseEffectItem = {
  cause: string
  action: string
  effect: string
}

export type HighlightObject = {
  name: string
  reason: string
}

export type SceneData = {
  sceneId: string
  timestamp: number
  subtitle: string
  prompts: PromptQuestion[]
  characterList: CharacterInfo[]
  emotion: string
  relationshipGraph: RelationshipEdge[]
  timelineData: TimelineItem[]
  causeEffectData: CauseEffectItem
  companionPosition: { x: number; y: number }
  highlightObject: HighlightObject
  voiceNarration: string
  visibleCharacterIds?: string[]
  missingCharacterIds?: string[]
  entityConfidence?: Record<string, number>
  entityEvidence?: Record<string, string[]>
  visibleObjects?: string[]
  promptSubjects?: Record<string, string[]>
  dialogueReferences?: Array<{ speakerEntityId?: string; targetEntityIds: string[]; pronouns: Array<{ pronoun: string; resolvedEntityId: string; evidence: string }> }>
  storyBeats?: StoryBeat[]
}

export type MovieData = {
  id: MovieId
  title: string
  description: string
  runtime: string
  genre: string
  rating: string
  accessibilityTags: AccessibilityTag[]
  posterUrl: string
  videoSrc: string
  subtitleSrc: string
  companionTheme: CompanionTheme
  scenes: SceneData[]
  canonicalCharacters?: Array<{
    id: string; name: string; description: string; personality: string; goals: string[]; relationships: string[]; firstAppearance: number; importantInformation: string[]; visualDescription: string; confidenceThreshold: number; lastAppearance?: number
  }>
  source?: 'backend' | 'catalog'
  processingStatus?: 'uploaded' | 'processing' | 'completed' | 'partial' | 'failed'
  processingError?: string | null
}
