import type { AIProfile } from '../../types/user'

export type ContentType = 'movie' | 'book'
export type VisualAidType = 'relationship' | 'timeline' | 'cause' | 'emotion' | 'object' | 'summary' | 'conversation' | 'memory' | 'location'
export type AccessibilityNeed = 'emotions' | 'characters' | 'relationships' | 'plot' | 'memory' | 'conversations' | 'jokes' | 'sarcasm' | 'vocabulary' | 'objects' | 'nonverbal'

export type NarrativeCharacter = {
  id: string
  name: string
  description: string
  personality: string
  goals: string[]
  relationships: string[]
  firstAppearance: number
  importantInformation: string[]
  visualDescription: string
  confidenceThreshold: number
  lastAppearance?: number
}

export type VisualGrounding = {
  visibleEntityIds: string[]
  missingEntityIds: string[]
  confidence: Record<string, number>
  evidence: Record<string, string[]>
  visibleObjects: string[]
}

export type DialogueReference = {
  speakerEntityId?: string
  targetEntityIds: string[]
  pronouns: Array<{ pronoun: string; resolvedEntityId: string; evidence: string }>
}

export type NarrativeRelationship = {
  characterA: string
  characterB: string
  relationshipType: string
  changesOverTime: string[]
}

export type NarrativePrompt = {
  id: string
  triggerType: AccessibilityNeed
  question: string
  explanation: string
  difficultyCategory: string
  priority?: number
  subjectEntityIds?: string[]
  evidence?: string[]
}

export type VisualAidNode = { type: VisualAidType; content: string; visualizationDescription: string }
export type StoryBeatPhase = 'intro_credits' | 'setup' | 'rising_action' | 'climax' | 'resolution' | 'transition'

export type StoryBeat = {
  id: string
  startTime: number
  endTime: number | null
  phase: StoryBeatPhase
  summary: string
  visibleEntityIds: string[]
  relationships: string[]
  emotions: Array<{ character?: string; emotion: string; explanation: string }>
  objects: string[]
  causeEffect: Array<{ cause: string; effect: string }>
  memory: string[]
  promptCandidates: NarrativePrompt[]
  drawerState: { conversationSummary?: string; timelinePosition?: string; support?: Partial<Record<AccessibilityNeed, string[]>> }
  confidence: number
  visualGrounding: VisualGrounding
}

export type PreprocessingInterval = {
  id: string
  startTime: number
  endTime: number
  storyBeatIds: string[]
}

export type AccessibilityGraph = {
  possibleConfusions: string[]
  support: Partial<Record<AccessibilityNeed, string[]>>
  memoryPoints: string[]
  prompts: NarrativePrompt[]
}

export type NarrativeScene = {
  sceneId: string
  startTime: number
  endTime: number | null
  chapterReference?: string
  pageReference?: { start: number; end: number }
  title: string
  summary: string
  characters: string[]
  storyBeats?: StoryBeat[]
  visualGrounding: VisualGrounding
  dialogueReferences: DialogueReference[]
  events: string[]
  emotions: Array<{ character?: string; emotion: string; explanation: string }>
  relationships: string[]
  objects: string[]
  conversationSummary: string
  importantDetails: string[]
  causeEffect: Array<{ cause: string; effect: string }>
  timelinePosition: string
  memoryCheckpoint: string[]
  accessibility: AccessibilityGraph
  visualAids: VisualAidNode[]
}

export type NarrativeGraph = {
  version: 1
  movie: { id: string; title: string; type: ContentType; metadata: Record<string, string> }
  scenes: NarrativeScene[]
  characters: NarrativeCharacter[]
  relationships: NarrativeRelationship[]
  preprocessingIntervals?: PreprocessingInterval[]
}

export type NarrativeSource = { contentId: string; type: ContentType; timestamp?: number; page?: number; chapter?: string }
export type VideoFrameInput = { timestamp: number; image: Blob; subtitleContext?: string }
export type VisualSceneData = { sceneId: string; startTime: number; endTime: number; visibleEntityIds: string[]; visibleObjects: string[]; location?: string; facialExpressions: Array<{ entityId: string; expression: string; confidence: number }>; visualContext: string; confidence: Record<string, number> }
export type NarrativeProcessorInput = { source: NarrativeSource; metadata: Record<string, string>; transcript?: string; screenplay?: string; scenes?: Array<{ startTime: number; endTime?: number; text?: string }>; visualScenes?: VisualSceneData[] }
export type AccessibilityAnalyzerInput = { scene: NarrativeScene; graph: NarrativeGraph; userNeeds?: AccessibilityNeed[] }

export interface VisualAnalyzer { analyzeFrames(input: { source: NarrativeSource; frames: VideoFrameInput[]; canonicalEntities: NarrativeCharacter[] }): Promise<VisualSceneData[]> }
export interface NarrativeProcessor { createNarrativeGraph(input: NarrativeProcessorInput): Promise<NarrativeGraph> }
export interface AccessibilityAnalyzer { createAccessibilityGraph(input: AccessibilityAnalyzerInput): Promise<AccessibilityGraph> }

export function profileNeeds(profile: AIProfile | null): Set<AccessibilityNeed> {
  const needs = new Set<AccessibilityNeed>()
  for (const value of profile?.difficultyAreas ?? []) {
    const normalized = value.toLowerCase()
    if (/emotion|feeling/.test(normalized)) needs.add('emotions')
    else if (/character/.test(normalized)) needs.add('characters')
    else if (/relationship/.test(normalized)) needs.add('relationships')
    else if (/plot|follow/.test(normalized)) needs.add('plot')
    else if (/previous|remember|memory/.test(normalized)) needs.add('memory')
    else if (/conversation|dialogue/.test(normalized)) needs.add('conversations')
    else if (/joke/.test(normalized)) needs.add('jokes')
    else if (/sarcasm/.test(normalized)) needs.add('sarcasm')
    else if (/word|vocabulary/.test(normalized)) needs.add('vocabulary')
    else if (/object/.test(normalized)) needs.add('objects')
    else if (/without dialogue|visual|scene/.test(normalized)) needs.add('nonverbal')
  }
  return needs
}
