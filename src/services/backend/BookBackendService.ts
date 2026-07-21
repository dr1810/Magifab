import type { CompanionProfilePayload, ProcessingState } from './MoviePreprocessingBackendService'

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
const base = import.meta.env.VITE_MAGIFAB_BACKEND_URL?.trim().replace(/\/$/, '') ?? ''
const endpoint = `${base}/api/v1/books`
async function json<T>(request: Promise<Response>): Promise<T> { const response = await request; const body: unknown = await response.json().catch(() => null); if (!response.ok) throw new Error(body && typeof body === 'object' && 'detail' in body ? String(body.detail) : 'Book service is unavailable.'); return body as T }
export const bookBackendService = {
  dune() { return json<{ book_id: string }>(fetch(`${endpoint}/examples/dune`)) },
  async upload(file: File) { const form = new FormData(); form.append('book', file); form.append('title', file.name.replace(/\.[^.]+$/, '')); return json<{ book_id: string }>(fetch(`${endpoint}/upload`, { method: 'POST', body: form })) },
  start(bookId: string, companion_profile: CompanionProfilePayload) { return json(fetch(`${endpoint}/${encodeURIComponent(bookId)}/preprocess`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ companion_profile }) })) },
  status(bookId: string) { return json<BookProcessingState>(fetch(`${endpoint}/${encodeURIComponent(bookId)}/processing-status`)) },
  chapters(bookId: string) { return json<{ book_id: string; chapters: BookChapterMetadata[] }>(fetch(`${endpoint}/${encodeURIComponent(bookId)}/chapters`)) },
  chapter(bookId: string, chapter = 1) { return json<BookChapter>(fetch(`${endpoint}/${encodeURIComponent(bookId)}/chapter?chapter=${chapter}`)) },
  chat(bookId: string, chapter: number, question: string, companion_profile: CompanionProfilePayload) { return json<{ answer: string; chapter_number: number }>(fetch(`${endpoint}/${encodeURIComponent(bookId)}/companion/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ chapter, question, companion_profile }) })) },
}
