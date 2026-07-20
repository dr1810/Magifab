import { useCallback, useEffect, useRef, useState } from 'react'
import type { PromptBubbleContent } from '../../components/FloatingBubble'
import type { StoryContext } from './StoryContextObserver'

export type PromptLifecycle = 'idle' | 'loading' | 'streaming' | 'completed' | 'expired' | 'dismissed' | 'failed' | 'fallback'
type PromptRequest = (signal: AbortSignal) => Promise<string>
type PromptDetails = Omit<PromptBubbleContent, 'lifecycle' | 'contextVersion' | 'storyBeatId' | 'timestampCreated' | 'validFrom' | 'validUntil' | 'loading'>

const REQUEST_TIMEOUT_MS = 5_000
const EXIT_DURATION_MS = 220

class PromptRequestTimeoutError extends Error {
  constructor() {
    super('Prompt request timed out')
  }
}

export function isPromptValid(prompt: PromptBubbleContent, context: StoryContext) {
  return prompt.contextVersion === context.contextVersion
    && prompt.storyBeatId === context.storyBeatId
    && context.currentTime >= (prompt.validFrom ?? Number.NEGATIVE_INFINITY)
    && context.currentTime < (prompt.validUntil ?? Number.POSITIVE_INFINITY)
}

export async function resolvePromptRequest(
  request: PromptRequest,
  controller: AbortController,
  fallback: string,
  timeoutMs = REQUEST_TIMEOUT_MS,
) {
  let timeout: ReturnType<typeof globalThis.setTimeout> | null = null
  let onAbort: (() => void) | null = null
  const timeoutPromise = new Promise<never>((_, reject) => {
    timeout = globalThis.setTimeout(() => reject(new PromptRequestTimeoutError()), timeoutMs)
  })
  const abortPromise = new Promise<never>((_, reject) => {
    onAbort = () => reject(new DOMException('Prompt request cancelled', 'AbortError'))
    if (controller.signal.aborted) onAbort()
    else controller.signal.addEventListener('abort', onAbort, { once: true })
  })

  try {
    const explanation = await Promise.race([request(controller.signal), timeoutPromise, abortPromise])
    return { lifecycle: 'completed' as const, explanation }
  } catch (error) {
    if (error instanceof PromptRequestTimeoutError) {
      controller.abort()
      return { lifecycle: 'fallback' as const, explanation: fallback }
    }
    if (controller.signal.aborted) return null
    return { lifecycle: 'failed' as const, explanation: fallback }
  } finally {
    if (timeout !== null) globalThis.clearTimeout(timeout)
    if (onAbort) controller.signal.removeEventListener('abort', onAbort)
  }
}

export function usePromptLifecycle(context: StoryContext) {
  const [activePrompt, setActivePrompt] = useState<PromptBubbleContent | null>(null)
  const controller = useRef<AbortController | null>(null)
  const exitTimer = useRef<number | null>(null)

  const clearExitTimer = useCallback(() => {
    if (exitTimer.current !== null) window.clearTimeout(exitTimer.current)
    exitTimer.current = null
  }, [])

  const finish = useCallback((lifecycle: PromptLifecycle, message?: string) => {
    controller.current?.abort()
    controller.current = null
    setActivePrompt((prompt) => prompt ? { ...prompt, lifecycle, loading: lifecycle === 'loading' || lifecycle === 'streaming', explanation: message ?? prompt.explanation } : null)
    if (lifecycle === 'expired' || lifecycle === 'dismissed') {
      clearExitTimer()
      exitTimer.current = window.setTimeout(() => setActivePrompt(null), EXIT_DURATION_MS)
    }
  }, [clearExitTimer])

  const start = useCallback(async (details: PromptDetails, request: PromptRequest, fallback: string) => {
    controller.current?.abort()
    clearExitTimer()
    const abortController = new AbortController()
    controller.current = abortController
    const prompt: PromptBubbleContent = {
      ...details,
      lifecycle: 'loading',
      loading: true,
      contextVersion: context.contextVersion,
      storyBeatId: context.storyBeatId ?? '',
      timestampCreated: context.currentTime,
      validFrom: context.validFrom,
      validUntil: context.validUntil,
    }
    setActivePrompt(prompt)
    const result = await resolvePromptRequest(request, abortController, fallback)
    if (!result || controller.current !== abortController) return
    controller.current = null
    setActivePrompt((current) => current ? { ...current, lifecycle: result.lifecycle, loading: false, explanation: result.explanation } : null)
  }, [clearExitTimer, context])

  useEffect(() => {
    if (!activePrompt) return
    if (activePrompt.lifecycle === 'expired' || activePrompt.lifecycle === 'dismissed') return
    if (!isPromptValid(activePrompt, context)) finish('expired')
  }, [activePrompt, context, finish])

  useEffect(() => () => {
    controller.current?.abort()
    clearExitTimer()
  }, [clearExitTimer])

  return { activePrompt, start, dismiss: () => finish('dismissed'), cancel: () => finish('dismissed') }
}
