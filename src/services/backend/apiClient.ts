type QueryValue = string | number | boolean | null | undefined

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  headers?: Record<string, string>
  body?: BodyInit | null
  jsonBody?: unknown
  query?: Record<string, QueryValue>
  signal?: AbortSignal
  timeoutMs?: number
}

export class BackendRequestError extends Error {
  status: number | null

  constructor(message: string, status: number | null = null) {
    super(message)
    this.name = 'BackendRequestError'
    this.status = status
  }
}

function normalizeBackendBaseUrl(): string {
  const raw = import.meta.env.VITE_MAGIFAB_BACKEND_URL?.trim()
  if (!raw) {
    throw new BackendRequestError('Backend URL is not configured. Set VITE_MAGIFAB_BACKEND_URL to your Render API URL.')
  }
  return raw.replace(/\/$/, '')
}

export function buildBackendUrl(path: string, query?: Record<string, QueryValue>): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`
  const url = new URL(`${normalizeBackendBaseUrl()}${cleanPath}`)

  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null) continue
      url.searchParams.set(key, String(value))
    }
  }

  return url.toString()
}

function createTimeoutSignal(timeoutMs: number, upstream?: AbortSignal): { signal: AbortSignal; cleanup: () => void; timedOut: () => boolean } {
  const controller = new AbortController()
  let timeoutHandle: number | null = null
  let didTimeout = false

  if (Number.isFinite(timeoutMs) && timeoutMs > 0) {
    timeoutHandle = window.setTimeout(() => {
      didTimeout = true
      controller.abort()
    }, timeoutMs)
  }

  const onAbort = () => controller.abort()
  if (upstream) {
    if (upstream.aborted) controller.abort()
    else upstream.addEventListener('abort', onAbort)
  }

  return {
    signal: controller.signal,
    cleanup: () => {
      if (timeoutHandle !== null) window.clearTimeout(timeoutHandle)
      if (upstream) upstream.removeEventListener('abort', onAbort)
    },
    timedOut: () => didTimeout,
  }
}

async function parseJsonBody(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text.trim()) return null
  try {
    return JSON.parse(text)
  } catch {
    throw new BackendRequestError('The backend returned invalid JSON. Please try again.')
  }
}

export async function requestBackendJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    method = 'GET',
    headers,
    body,
    jsonBody,
    query,
    signal,
    timeoutMs = 20_000,
  } = options

  const requestHeaders: Record<string, string> = { ...(headers ?? {}) }
  let requestBody: BodyInit | null | undefined = body

  if (jsonBody !== undefined) {
    requestBody = JSON.stringify(jsonBody)
    requestHeaders['Content-Type'] = 'application/json'
  }

  const timeout = createTimeoutSignal(timeoutMs, signal)

  try {
    const response = await fetch(buildBackendUrl(path, query), {
      method,
      headers: requestHeaders,
      body: requestBody,
      signal: timeout.signal,
    })

    let parsed: unknown
    try {
      parsed = await parseJsonBody(response)
    } catch (error) {
      if (!response.ok) {
        throw new BackendRequestError(`Backend request failed (${response.status}).`, response.status)
      }
      throw error
    }

    if (!response.ok) {
      const detail = parsed && typeof parsed === 'object' && 'detail' in parsed ? String((parsed as { detail: unknown }).detail) : null
      throw new BackendRequestError(detail || `Backend request failed (${response.status}).`, response.status)
    }

    return parsed as T
  } catch (error: unknown) {
    if (error instanceof BackendRequestError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      if (timeout.timedOut()) throw new BackendRequestError('The backend request timed out. Please try again.')
      throw new BackendRequestError('The backend request was interrupted. Please retry.')
    }
    throw new BackendRequestError('Cannot reach backend service. Check network connectivity or backend availability.')
  } finally {
    timeout.cleanup()
  }
}
