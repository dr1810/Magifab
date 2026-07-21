/**
 * Stored movie artifacts are adapted in movieService.ts. This module remains a
 * compatibility export for old local catalog imports and intentionally has no
 * network or preprocessing behaviour.
 */
import type { SceneState } from './SceneState'

export function storedSceneToSceneState(_record: unknown, _window: unknown): SceneState {
  throw new Error('Stored scene compatibility adapter is no longer used; retrieve /scene through movieService instead.')
}
