import type { CompanionInterval, CompanionProvider } from './CompanionInterval'

export type BookIntervalInput = {
  contentId: string
  pageStart: number
  pageEnd: number
  text: string
  image: string
  metadata?: Record<string, unknown>
}

export class BookProvider implements CompanionProvider<BookIntervalInput> {
  createInterval(input: BookIntervalInput): CompanionInterval {
    const intervalNumber = Math.floor((input.pageStart - 1) / 2)
    return {
      id: `${input.contentId}:pages:${input.pageStart}-${input.pageEnd}`,
      contentId: input.contentId,
      start: intervalNumber * 30,
      end: (intervalNumber + 1) * 30,
      timestamp: intervalNumber * 30,
      image: input.image,
      text: input.text,
      metadata: { provider: 'book', pageStart: input.pageStart, pageEnd: input.pageEnd, ...input.metadata },
    }
  }
}
