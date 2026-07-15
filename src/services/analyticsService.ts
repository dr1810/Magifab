import type { AnalyticsEvent } from '../types/analytics'

const analyticsBuffer: AnalyticsEvent[] = []

export async function trackEvent(event: AnalyticsEvent): Promise<{ accepted: boolean }> {
  // TODO Backend:
  // Endpoint expected: POST /api/analytics/events
  // Request: { eventName: string, category: string, metadata?: object, timestamp: string }
  // Response: { accepted: boolean, eventId: string }
  analyticsBuffer.push(event)
  return Promise.resolve({ accepted: true })
}

export async function getAnalyticsBuffer(): Promise<AnalyticsEvent[]> {
  // TODO Backend:
  // Endpoint expected: GET /api/analytics/events/pending
  // Request: no body
  // Response: { events: AnalyticsEvent[] }
  return Promise.resolve([...analyticsBuffer])
}
