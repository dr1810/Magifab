/**
 * The content-neutral unit consumed by the Companion Engine.
 * Providers may use seconds, pages, slides, or document positions for start
 * and end, as long as they remain ordered within one content item.
 */
export interface CompanionInterval {
  id: string
  contentId: string
  start: number
  end: number
  timestamp: number
  image: string
  text: string
  metadata: Record<string, unknown>
}

export interface CompanionProvider<Input> {
  createInterval(input: Input): CompanionInterval
}
