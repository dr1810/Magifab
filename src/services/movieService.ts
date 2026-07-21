import { demoMovies, getSceneAtTimestamp, movieById } from '../movie-data/index'
import { moviePreprocessingBackendService } from './backend/MoviePreprocessingBackendService'
import { storedSceneToSceneState } from './scene/StoredSceneState'
import type { SceneState } from './scene/SceneState'
import type { MovieData, MovieId, SceneData } from '../types/movie'

export type ResolvedMovieScene = { scene: SceneData; sceneState: SceneState | null }

export async function getMovies(): Promise<MovieData[]> {
  // Bundled catalog entries remain available for the existing demo experience.
  // Uploaded movies enter through MoviePreprocessingBackendService after processing.
  return Promise.resolve(demoMovies)
}

export async function getMovie(id: MovieId, signal?: AbortSignal): Promise<MovieData | null> {
  if (signal?.aborted) throw new DOMException('Movie request cancelled', 'AbortError')
  const catalogMovie = movieById[id]
  // Curated demo movies are local catalog content and must never trigger a
  // backend lookup for an uploaded-movie UUID.
  if (catalogMovie) return catalogMovie
  try {
    const state = await moviePreprocessingBackendService.status(id, signal)
    return backendMovie(id, state)
  } catch (error) {
    if (isNotFound(error)) return null
    throw error
  }
}

export async function getScene(movieId: MovieId, timestamp: number, signal?: AbortSignal): Promise<ResolvedMovieScene | null> {
  if (signal?.aborted) throw new DOMException('Scene request cancelled', 'AbortError')
  const catalogMovie = movieById[movieId]
  if (catalogMovie) return { scene: getSceneAtTimestamp(catalogMovie, timestamp), sceneState: null }
  try {
    const result = await moviePreprocessingBackendService.getScene(movieId, timestamp, signal)
    if (result) {
      const state = artifactToSceneState(movieId, result)
      return { scene: sceneDataFromStored(state), sceneState: state }
    }
    return null
  } catch (error) {
    if (isNotFound(error)) return null
    throw error
  }
}

function backendMovie(id: string, movie: Awaited<ReturnType<typeof moviePreprocessingBackendService.status>>): MovieData {
  return {
    id,
    title: movie.title || 'Uploaded movie',
    description: movie.status === 'complete' ? 'Your movie is ready with scene-by-scene MagiFab guidance.' : movie.progress,
    runtime: movie.status === 'complete' ? 'Ready to watch' : 'Preparing movie',
    genre: 'Uploaded movie',
    rating: 'Ready',
    accessibilityTags: ['Simple Language Prompts', 'Audio Description', 'Reduced Motion Supported'],
    posterUrl: '/favicon.svg',
    videoSrc: moviePreprocessingBackendService.videoUrl(id),
    subtitleSrc: '',
    companionTheme: 'ocean',
    scenes: [],
    source: 'backend',
    processingStatus: movie.status === 'complete' ? 'completed' : movie.status === 'failed' ? 'failed' : 'processing',
    processingError: movie.error,
  }
}

function artifactToSceneState(movieId: string, artifact: Awaited<ReturnType<typeof moviePreprocessingBackendService.getScene>>): SceneState {
  const prompts = artifact.promptBubble.map((item, index) => ({ id: `${movieId}:${artifact.timestamp}:prompt:${index}`, kind: 'scene', label: item.label, question: item.question, priority: 5 - index }))
  return {
    sceneId: `${movieId}:${artifact.timestamp}`, interval: Math.floor(artifact.timestamp / 90), startTime: artifact.timestamp, endTime: artifact.timestamp + 90,
    sceneSummary: artifact.companionExplanation, subtitle: artifact.companionExplanation,
    characters: artifact.characters.map((item, index) => ({ character_id: `${movieId}:character:${index}`, name: item.name, reminder: item.description, confidence: item.confidence === 'high' ? 1 : item.confidence === 'medium' ? .7 : .4 })),
    relationships: [], timeline: artifact.visualDrawer.timeline, memory: artifact.memoryCue.map((summary) => ({ summary, confidence: 1 })), importantObjects: artifact.visualDrawer.objects.map((item) => item.name), emotions: artifact.visualDrawer.emotion.map((summary, index) => ({ emotion_id: `${movieId}:emotion:${index}`, summary, confidence: 1 })), causeEffect: artifact.visualDrawer.cause,
    visualAid: artifact.visualAid, promptBubbles: prompts, promptAnswers: Object.fromEntries(prompts.map((prompt, index) => [prompt.id, artifact.promptBubble[index].answer])),
    accessibilityHints: { vocabulary: artifact.visualDrawer.objects.map((item, index) => ({ id: `${movieId}:object:${index}`, term: item.name, simple_definition: item.why, confidence: 1 })), emotions: artifact.visualDrawer.emotion.map((summary, index) => ({ emotion_id: `${movieId}:emotion:${index}`, summary, confidence: 1 })) },
    conversation: { sceneExplanation: artifact.companionExplanation, simplifications: [] }, story: { currentGoal: artifact.visualDrawer.timeline[0] ?? null, timelinePosition: artifact.visualDrawer.timeline[0] ?? null, storySoFar: artifact.memoryCue, unresolvedThreads: [] }, companionEnabled: true, metadata: { movieId, generatedAt: Date.now(), knowledgeRevision: 1, frameTimestamp: artifact.timestamp },
  }
}

function sceneDataFromStored(state: SceneState): SceneData {
  return {
    sceneId: state.sceneId,
    timestamp: state.startTime,
    subtitle: state.subtitle ?? state.sceneSummary,
    prompts: state.promptBubbles.map((prompt) => ({ id: prompt.id, label: prompt.label, question: prompt.question, explanation: state.promptAnswers?.[prompt.id] ?? '' })),
    characterList: state.characters.map((character) => ({ id: character.character_id, name: character.name, role: character.reminder, emotionalState: state.emotions[0]?.summary ?? '' })),
    emotion: state.emotions[0]?.summary ?? '',
    relationshipGraph: state.relationships.map((relationship, index) => ({ from: `relationship-${index}`, to: `relationship-${index}`, label: relationship.summary })),
    timelineData: state.timeline.map((label, index) => ({ id: `${state.sceneId}:timeline:${index}`, time: 'Now', label })),
    causeEffectData: { cause: state.causeEffect[0]?.cause ?? '', action: '', effect: state.causeEffect[0]?.effect ?? '' },
    companionPosition: { x: 50, y: 50 },
    highlightObject: { name: state.importantObjects[0] ?? '', reason: state.accessibilityHints.vocabulary[0]?.simple_definition ?? '' },
    voiceNarration: state.conversation.sceneExplanation,
    visibleObjects: state.importantObjects,
  }
}

function isNotFound(error: unknown) {
  return error instanceof Error && /not found/i.test(error.message)
}
