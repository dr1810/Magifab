import type { CompanionProfile as StoredCompanionProfile, AIProfile } from '../../types/user'

export type TimestampRange = { start: number; end: number }

/** Server-side source references for a newly imported movie. */
export type MovieMediaSource = {
  videoUrl: string
  transcriptUrl?: string
  frameManifestUrl?: string
}

/** A representative frame produced by the movie-import preprocessing pipeline. */
export type ExtractedFrame = { timestamp: number; imageUrl: string }

/** A timestamped transcript segment produced during movie import. */
export type TranscriptSegment = { start: number; end: number; text: string; speaker?: string }

/** A detected scene boundary before semantic analysis. */
export type DetectedScene = { id: string; range: TimestampRange; confidence: number }

/** GPT-ready scene data assembled from frames, transcript, and scene boundaries. */
export type StructuredSceneRepresentation = {
  sceneId: string
  range: TimestampRange
  frames: ExtractedFrame[]
  transcript: TranscriptSegment[]
}

/** Output of Movie Processing in the canonical architecture. */
export type MoviePreprocessingResult = {
  movieId: string
  source: MovieMediaSource
  scenes: StructuredSceneRepresentation[]
}

export type SemanticCharacter = {
  id: string
  name: string
  role: string
  traits: string[]
  /** Detector-safe labels that may be matched without asking a language model to guess. */
  aliases?: string[]
}

export type VisibleCharacter = {
  characterId: string
  prominence: 'primary' | 'secondary' | 'background'
  confidence: 'known' | 'uncertain'
}

export type SemanticRelationship = {
  fromCharacterId: string
  toCharacterId: string
  description: string
  timestamps: TimestampRange[]
}

export type SemanticObject = {
  id: string
  name: string
  significance: string
  timestamps: TimestampRange[]
}

export type ConfusionPoint = {
  timestamp: number
  reason: string
  suggestedQuestion: string
}

export type SemanticScene = {
  sceneId: string
  range: TimestampRange
  summary: string
  dialogue: string[]
  emotions: string[]
  importantEvents: string[]
  characterIds: string[]
  visibleCharacters: VisibleCharacter[]
  objectIds: string[]
  location: string
  keyFrameTimestamps: number[]
  accessibilityMetadata: string[]
  confusionPoints: ConfusionPoint[]
  companionAnchor: { x: number; y: number }
  /** Observations accepted by the semantic matcher, never raw model guesses. */
  knownDetections?: VerifiedSemanticDetection[]
}

export type VerifiedSemanticDetection = {
  detectionId: string
  className: string
  timestamp: number
  confidence: number
  characterId?: string
  bbox: { x: number; y: number; width: number; height: number }
}

/** Optimized, timestamp-indexed output of the one-time movie-analysis stage. */
export type SemanticMovieMemory = {
  movieId: string
  version: number
  createdAt: string
  characters: SemanticCharacter[]
  relationships: SemanticRelationship[]
  objects: SemanticObject[]
  timeline: Array<{ timestamp: number; event: string }>
  scenes: SemanticScene[]
  accessibilityKnowledge: AccessibilityKnowledge[]
}

/** Accessibility-focused knowledge indexed by scene timestamp. */
export type AccessibilityKnowledge = {
  sceneId: string
  range: TimestampRange
  metadata: string[]
  description: string
}

/** Reusable runtime profile compiled from the existing onboarding answers. */
export type CompanionProfile = {
  name: string
  personality: string
  appearance: string
  voiceStyle: string
  explanationStyle: string
  interactionFrequency: string
  detailLevel: string
  accessibilityNeeds: string[]
  conversationStyle: string
  interactionStyle: string
  emotionalSupport: string
  preferredPromptTypes: string[]
}

export type RuntimeContext = {
  movieId: string
  timestamp: number
  scene: SemanticScene
  recentTimeline: Array<{ timestamp: number; event: string }>
  relevantRelationships: SemanticRelationship[]
  accessibilityKnowledge: AccessibilityKnowledge | null
  profile: CompanionProfile
  question: string
}

export type CompanionResponse = {
  answer: string
  confidence: number
  sceneId: string
  shouldShowBubble: boolean
  /** The server-selected visual target for a user-initiated prompt bubble. */
  target?: { id: string; kind: 'character' | 'object' | 'emotion' | 'event'; label: string; anchor: { x: number; y: number } }
  presentation?: RuntimePresentation
}

/** Structured UI directives emitted by the runtime reasoning layer. */
export type RuntimePresentation = {
  companionMessage: string
  showCharacterCard: boolean
  showPromptBubble: boolean
  target?: CompanionResponse['target']
}

export type MovieAnalysisInput = {
  movieId: string
  title: string
  /** Server-side media references produced during import. */
  source: MovieMediaSource
}

export type StoredOnboardingProfile = {
  companionProfile: StoredCompanionProfile
  aiProfile: AIProfile
}
