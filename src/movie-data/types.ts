export type VisualAidKind =
  | 'relationships'
  | 'timeline'
  | 'cause'
  | 'emotion'
  | 'object'
  | 'summary'
  | 'conversation'
  | 'memory'
  | 'location'

export type MovieInfo = {
  id: string
  title: string
  year: string
  duration: string
  genre: string
  description: string
  posterUrl: string
  videoUrl: string
}

export type Character = {
  id: string
  name: string
  role: string
  description: string
  color: string
}

export type Relationship = {
  id: string
  source: string
  target: string
  label: string
}

export type TimelineEvent = {
  id: string
  time: string
  label: string
  tone: string // For color styling
}

export type CauseEffectStep = {
  label: string
  description: string
  tone: string
}

export type CauseEffectData = {
  cause: CauseEffectStep
  action: CauseEffectStep
  effect: CauseEffectStep
}

export type EmotionProfile = {
  character: string
  emotion: string
  description: string
  intensity: number // height multiplier (1-10)
  tone: string
}

export type ObjectDetail = {
  name: string
  description: string
  use: string
  glowCondition: string
}

export type ConversationBubble = {
  character: string
  text: string
  tone: string
}

export type MemoryCompare = {
  pastTitle: string
  pastDetail: string
  nowTitle: string
  nowDetail: string
}

export type LocationDetail = {
  name: string
  description: string
  focusArea: string
}

export type VisualAidData = {
  relationships?: { source: string; target: string; label: string }[]
  timeline?: TimelineEvent[]
  cause?: CauseEffectData
  emotions?: EmotionProfile[]
  object?: ObjectDetail
  conversation?: ConversationBubble[]
  memory?: MemoryCompare
  location?: LocationDetail
}

export type Prompt = {
  id: string
  label: string
  question: string
  answer: string
  kind: VisualAidKind
  target: { x: number; y: number }
  visualAid?: VisualAidData
}

export type MovieDataset = {
  info: MovieInfo
  characters: Character[]
  prompts: Prompt[]
  subtitles: { start: number; end: number; text: string }[]
}
