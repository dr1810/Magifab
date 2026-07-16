export type MovieId = 'bigBuckBunny' | 'spriteFright'

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
}
