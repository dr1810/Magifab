import type { CompanionProfilePayload, ProcessingState } from './MoviePreprocessingBackendService'
import { requestBackendJson } from './apiClient'

export type BookCharacter = { name: string; description: string }
export type BookRelationship = { source: string; relation: string; target: string }
export type VisualMapNode = { id: string; label: string }
export type VisualMapEdge = { source: string; target: string; label: string }
export type CompanionQuestion = { label: string; question: string }
export type BookChapterMetadata = {
  chapter_number: number
  chapter_title: string
  section_label: string
  page_start: number
  page_end: number
}
export type BookChapter = {
  chapter_number: number
  chapter_title: string
  section_label: string
  page_start: number
  page_end: number
  chapter_summary: string
  simple_explanation: string
  characters: BookCharacter[]
  relationships: BookRelationship[]
  important_events: string[]
  difficult_concepts: string[]
  memory_aid: string
  visual_relationship_map: { nodes: VisualMapNode[]; edges: VisualMapEdge[] }
  companion_questions: CompanionQuestion[]
  confidence: number
}
export type BookProcessingState = ProcessingState & { chapter_count?: number }
export const bookBackendService = {
  dune() { return requestBackendJson<{ book_id: string }>('/api/v1/books/examples/dune') },
  async upload(file: File) { const form = new FormData(); form.append('book', file); form.append('title', file.name.replace(/\.[^.]+$/, '')); return requestBackendJson<{ book_id: string }>('/api/v1/books/upload', { method: 'POST', body: form, timeoutMs: 60_000 }) },
  start(bookId: string, companion_profile: CompanionProfilePayload) { return requestBackendJson<{ book_id: string; status: string; accepted: boolean }>(`/api/v1/books/${encodeURIComponent(bookId)}/preprocess`, { method: 'POST', jsonBody: { companion_profile }, timeoutMs: 45_000 }) },
  status(bookId: string) { return requestBackendJson<BookProcessingState>(`/api/v1/books/${encodeURIComponent(bookId)}/processing-status`) },
  chapters(bookId: string) { return requestBackendJson<{ book_id: string; chapters: BookChapterMetadata[] }>(`/api/v1/books/${encodeURIComponent(bookId)}/chapters`) },
  chapter(bookId: string, chapter = 1) { return requestBackendJson<BookChapter>(`/api/v1/books/${encodeURIComponent(bookId)}/chapter`, { query: { chapter } }) },
  chat(bookId: string, chapter: number, question: string, companion_profile: CompanionProfilePayload) { return requestBackendJson<{ answer: string; chapter_number: number }>(`/api/v1/books/${encodeURIComponent(bookId)}/companion/chat`, { method: 'POST', jsonBody: { chapter, question, companion_profile }, timeoutMs: 45_000 }) },
}
