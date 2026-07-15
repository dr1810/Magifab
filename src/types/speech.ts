export type SpeechRequest = {
  text: string
  rate: number
  volume: number
  voicePreference?: 'Female' | 'Male' | 'Neutral'
}

export type SpeechResult = {
  started: boolean
  utteranceId: string
}
