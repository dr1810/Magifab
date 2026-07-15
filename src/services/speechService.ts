import type { SpeechRequest, SpeechResult } from '../types/speech'

export async function speakText(request: SpeechRequest): Promise<SpeechResult> {
  // TODO Backend:
  // Endpoint expected: POST /api/speech/synthesize
  // Request: { text: string, rate: number, volume: number, voicePreference?: string }
  // Response: { started: boolean, utteranceId: string, audioUrl?: string }
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(request.text)
    utterance.rate = request.rate
    utterance.volume = request.volume
    window.speechSynthesis.speak(utterance)
  }

  return Promise.resolve({
    started: true,
    utteranceId: `mock-utterance-${Date.now()}`,
  })
}

export async function stopSpeech(): Promise<void> {
  // TODO Backend:
  // Endpoint expected: POST /api/speech/stop
  // Request: { utteranceId?: string }
  // Response: { success: boolean }
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel()
  }
  return Promise.resolve()
}
