export type KnowledgeIntent = 'character_identity' | 'emotion' | 'object' | 'plot' | 'relationship' | 'conversation' | 'general'

export type KnowledgeLookup = {
  movieId: string
  sceneId: string
  timestamp: number
  timestampRange: { start: number; end: number }
  intent: KnowledgeIntent
  needs: string[]
  companionStyle: string[]
}

export type StoredKnowledge<T> = KnowledgeLookup & {
  key: string
  createdAt: string
  value: T
}

const STORAGE_PREFIX = 'magifab-knowledge:v2:'

const normalize = (value: string) => value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')

/** Stores reusable, scene-scoped knowledge without coupling the viewer to a backend store. */
export class KnowledgeStore {
  private readonly cache = new Map<string, StoredKnowledge<unknown>>()

  buildKey({ movieId, sceneId, timestampRange, intent, needs, companionStyle }: KnowledgeLookup): string {
    return [
      normalize(movieId),
      normalize(sceneId),
      `${Math.floor(timestampRange.start)}-${Number.isFinite(timestampRange.end) ? Math.floor(timestampRange.end) : 'end'}`,
      intent,
      [...new Set(needs.map(normalize))].sort().join(',') || 'general',
      [...new Set(companionStyle.map(normalize))].sort().join(',') || 'default',
    ].join('::')
  }

  has(lookup: KnowledgeLookup): boolean {
    return this.get(lookup) !== null
  }

  get<T>(lookup: KnowledgeLookup): StoredKnowledge<T> | null {
    const key = this.buildKey(lookup)
    const cached = this.cache.get(key)
    if (cached) return cached as StoredKnowledge<T>

    try {
      const raw = localStorage.getItem(`${STORAGE_PREFIX}${key}`)
      if (!raw) return null
      const stored = JSON.parse(raw) as StoredKnowledge<T>
      if (!stored || stored.key !== key) return null
      this.cache.set(key, stored)
      return stored
    } catch {
      return null
    }
  }

  save<T>(lookup: KnowledgeLookup, value: T): StoredKnowledge<T> {
    const key = this.buildKey(lookup)
    const stored: StoredKnowledge<T> = { ...lookup, key, createdAt: new Date().toISOString(), value }
    this.cache.set(key, stored)
    try {
      localStorage.setItem(`${STORAGE_PREFIX}${key}`, JSON.stringify(stored))
    } catch {
      // The in-memory cache still prevents duplicate requests for this viewing session.
    }
    return stored
  }
}

export const knowledgeStore = new KnowledgeStore()
