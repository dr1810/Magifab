export type AssistantQuestion = {
  sceneId: string
  question: string
}

export type AssistantAnswer = {
  sceneId: string
  answer: string
  confidence: number
  target?: { id: string; kind: 'character' | 'object' | 'emotion' | 'event'; label: string; anchor: { x: number; y: number } }
}
