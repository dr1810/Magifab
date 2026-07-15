export type AnalyticsEvent = {
  eventName: string
  category: 'navigation' | 'assistant' | 'accessibility' | 'onboarding' | 'playback'
  metadata?: Record<string, string | number | boolean>
  timestamp: string
}
