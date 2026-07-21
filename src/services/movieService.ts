import { demoMovies, getSceneAtTimestamp, movieById } from '../movie-data/index'
import { moviePreprocessingBackendService, type ProcessedChunk, type ProcessedMovie } from './backend/MoviePreprocessingBackendService'
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
  try {
    const [movie, chunks] = await Promise.all([moviePreprocessingBackendService.getMovie(id, signal), moviePreprocessingBackendService.getTimeline(id, signal)])
    return backendMovie(movie, chunks)
  } catch (error) {
    // Keep the curated, offline catalog usable when the backend has no matching record.
    if (isNotFound(error)) return movieById[id] ?? null
    throw error
  }
}

export async function getScene(movieId: MovieId, timestamp: number, signal?: AbortSignal): Promise<ResolvedMovieScene | null> {
  if (signal?.aborted) throw new DOMException('Scene request cancelled', 'AbortError')
  try {
    const result = await moviePreprocessingBackendService.getScene(movieId, timestamp, signal)
    if (result.scene && result.chunk) {
      const state = storedSceneToSceneState(result.scene, result.chunk)
      void moviePreprocessingBackendService.preloadNearbyScenes(movieId, timestamp).catch(() => undefined)
      return { scene: sceneDataFromStored(state), sceneState: state }
    }
    return null
  } catch (error) {
    if (!isNotFound(error)) throw error
    const movie = movieById[movieId]
    return movie ? { scene: getSceneAtTimestamp(movie, timestamp), sceneState: null } : null
  }
}

function backendMovie(movie: ProcessedMovie, chunks: ProcessedChunk[]): MovieData {
  return {
    id: movie.id,
    title: movie.title || movie.original_filename,
    description: movie.status === 'completed' ? 'Your movie is ready with scene-by-scene MagiFab guidance.' : 'MagiFab is preparing this movie for you.',
    runtime: durationLabel(chunks),
    genre: 'Uploaded movie',
    rating: 'Ready',
    accessibilityTags: ['Simple Language Prompts', 'Audio Description', 'Reduced Motion Supported'],
    posterUrl: '/favicon.svg',
    videoSrc: moviePreprocessingBackendService.videoUrl(movie.id),
    subtitleSrc: '',
    companionTheme: 'ocean',
    scenes: chunks.map((chunk) => emptyScene(chunk)),
    source: 'backend',
    processingStatus: movie.status,
    processingError: movie.error_message,
  }
}

function emptyScene(chunk: ProcessedChunk): SceneData {
  return {
    sceneId: chunk.id,
    timestamp: chunk.start_seconds,
    subtitle: '',
    prompts: [],
    characterList: [],
    emotion: '',
    relationshipGraph: [],
    timelineData: [],
    causeEffectData: { cause: '', action: '', effect: '' },
    companionPosition: { x: 50, y: 50 },
    highlightObject: { name: '', reason: '' },
    voiceNarration: '',
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

function durationLabel(chunks: ProcessedChunk[]) {
  const seconds = Math.max(0, chunks.at(-1)?.end_seconds ?? 0)
  return seconds ? `${Math.floor(seconds / 60)} min` : 'Preparing runtime'
}

function isNotFound(error: unknown) {
  return error instanceof Error && /not found/i.test(error.message)
}
