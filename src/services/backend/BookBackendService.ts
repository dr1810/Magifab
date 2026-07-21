import type { CompanionProfilePayload, ProcessingState } from './MoviePreprocessingBackendService'

export type BookChapter = { chapter: number; title: string; summary: string; characters: Array<{ name: string; description: string }>; relationships: string[]; locations: string[]; politicalSocialContext: string[]; memoryAids: string[]; timeline: string[]; glossary: Array<{ term: string; definition: string }>; visualRelationshipMap: { nodes: string[]; edges: string[][] } }
const base = import.meta.env.VITE_MAGIFAB_BACKEND_URL?.trim().replace(/\/$/, '') ?? ''
const endpoint = `${base}/api/v1/books`
async function json<T>(request: Promise<Response>): Promise<T> { const response = await request; const body: unknown = await response.json().catch(() => null); if (!response.ok) throw new Error(body && typeof body === 'object' && 'detail' in body ? String(body.detail) : 'Book service is unavailable.'); return body as T }
export const bookBackendService = {
  dune() { return json<{ book_id: string }>(fetch(`${endpoint}/examples/dune`)) },
  async upload(file: File) { const form = new FormData(); form.append('book', file); form.append('title', file.name.replace(/\.[^.]+$/, '')); return json<{ book_id: string }>(fetch(`${endpoint}/upload`, { method: 'POST', body: form })) },
  start(bookId: string, companion_profile: CompanionProfilePayload) { return json(fetch(`${endpoint}/${encodeURIComponent(bookId)}/preprocess`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ companion_profile }) })) },
  status(bookId: string) { return json<ProcessingState>(fetch(`${endpoint}/${encodeURIComponent(bookId)}/processing-status`)) },
  chapter(bookId: string, chapter = 1) { return json<BookChapter>(fetch(`${endpoint}/${encodeURIComponent(bookId)}/chapter?chapter=${chapter}`)) },
  chat(bookId: string, chapter: number, question: string, companion_profile: CompanionProfilePayload) { return json<{ answer: string }>(fetch(`${endpoint}/${encodeURIComponent(bookId)}/companion/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ chapter, question, companion_profile }) })) },
}
