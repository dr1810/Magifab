import { getAccessibilityProfile } from '../accessibilityProfileService'
import { knowledgeStore, type KnowledgeIntent, type KnowledgeLookup, type StoredKnowledge } from './KnowledgeStore'
import { semanticMemoryService } from '../gpt/SemanticMemoryService'

type KnowledgeRequest = Omit<KnowledgeLookup, 'intent' | 'needs' | 'companionStyle' | 'timestampRange'> & { question: string }

export type KnowledgeResult<T> = { source: 'cache' | 'generated'; record: StoredKnowledge<T> }

function inferIntent(question: string): KnowledgeIntent {
  const normalized = question.toLowerCase()
  if (/\bwho\b/.test(normalized)) return 'character_identity'
  if (/emotion|feel|sad|angry|scared|happy/.test(normalized)) return 'emotion'
  if (/object|thing|this/.test(normalized)) return 'object'
  if (/relationship|related|friend|family/.test(normalized)) return 'relationship'
  if (/conversation|said|mean|sarcasm|joke/.test(normalized)) return 'conversation'
  if (/what happened|why|before|plot|matter/.test(normalized)) return 'plot'
  return 'general'
}

/** Retrieves profile-aware movie knowledge and shares concurrent cache-miss work. */
export class KnowledgeRetriever {
  private readonly pending = new Map<string, Promise<StoredKnowledge<unknown>>>()

  async buildLookup(request: KnowledgeRequest): Promise<KnowledgeLookup> {
    const profile = await getAccessibilityProfile()
    const memory = semanticMemoryService.get(request.movieId)
    const semanticScene = memory ? semanticMemoryService.getScene(memory, request.timestamp) : null
    return {
      movieId: request.movieId,
      sceneId: request.sceneId,
      timestamp: request.timestamp,
      timestampRange: semanticScene?.range ?? { start: Math.floor(request.timestamp / 30) * 30, end: Math.floor(request.timestamp / 30) * 30 + 30 },
      intent: inferIntent(request.question),
      needs: profile?.aiProfile.difficultyAreas ?? ['general_accessibility'],
      companionStyle: [
        profile?.companionProfile.personality ?? 'warm',
        profile?.companionProfile.conversationStyle ?? profile?.companionProfile.speakingStyle ?? 'simple',
        profile?.aiProfile.detailLevel ?? 'just_the_essentials',
        profile?.aiProfile.explanationTone ?? 'warm_and_encouraging',
      ],
    }
  }

  async getOrCreate<T>(request: KnowledgeRequest, generate: () => Promise<T>): Promise<KnowledgeResult<T>> {
    const lookup = await this.buildLookup(request)
    const existing = knowledgeStore.get<T>(lookup)
    if (existing) return { source: 'cache', record: existing }

    const key = knowledgeStore.buildKey(lookup)
    const pending = this.pending.get(key)
    if (pending) return { source: 'generated', record: await pending as StoredKnowledge<T> }

    const work = generate()
      .then((value) => knowledgeStore.save(lookup, value))
      .finally(() => this.pending.delete(key))
    this.pending.set(key, work)
    return { source: 'generated', record: await work }
  }
}

export const knowledgeRetriever = new KnowledgeRetriever()
