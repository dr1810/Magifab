import type { AssistantAnswer } from '../types/assistant'

const assistantAnswers: Record<string, string> = {
  default: 'This moment matters because it changes how the characters trust each other moving forward.',
}

export async function askAssistant(sceneId: string, question: string): Promise<AssistantAnswer> {
  // TODO Backend:
  // Endpoint expected: POST /api/assistant/ask
  // Request: { sceneId: string, question: string }
  // Response: { answer: string, confidence: number, sceneId: string }
  const normalized = `${sceneId}:${question}`.toLowerCase()
  const answer = assistantAnswers[normalized] ?? assistantAnswers.default
  return Promise.resolve({
    sceneId,
    answer,
    confidence: 0.86,
  })
}
