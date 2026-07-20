import type { CapturedVideoFrame } from '../ai/VideoFrameCaptureService'
import type { IntervalState } from '../backend/CompanionBackendService'

export type IntervalLifecycle = 'NEW' | 'CAPTURING' | 'PREPARING' | 'READY' | 'FAILED'

export type CachedIntervalSnapshot = IntervalState & { representativeFrame: CapturedVideoFrame }

export type IntervalRecord = {
  interval: number
  start: number
  end: number
  status: IntervalLifecycle
  snapshot?: CachedIntervalSnapshot
  error?: { stage: string; message: string }
  updatedAt: number
}

/**
 * Browser-local producer/consumer boundary for companion data.  Requests may
 * finish in any order; every successful package is retained and published.
 */
export class IntervalManager {
  private readonly records = new Map<number, IntervalRecord>()
  private readonly listeners = new Set<() => void>()
  private runId = 0
  private activeRunId: number | null = null

  reset(duration: number, intervalSeconds: number) {
    this.runId += 1
    this.activeRunId = null
    this.records.clear()
    const count = Math.ceil(duration / intervalSeconds)
    for (let interval = 0; interval < count; interval += 1) {
      const start = interval * intervalSeconds
      this.records.set(interval, { interval, start, end: Math.min(duration, start + intervalSeconds), status: 'NEW', updatedAt: Date.now() })
    }
    this.emit()
    return count
  }

  subscribe(listener: () => void) { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  get(interval: number) { return this.records.get(interval) }
  getSnapshot(interval: number) { return this.records.get(interval)?.snapshot }
  get size() { return this.records.size }
  get readyCount() { return [...this.records.values()].filter((record) => record.status === 'READY').length }
  get failedCount() { return [...this.records.values()].filter((record) => record.status === 'FAILED').length }

  /** Exactly one FIFO producer owns state transitions and atomic package commits. */
  async start(process: (task: IntervalRecord, transition: (state: 'CAPTURING' | 'PREPARING') => void) => Promise<CachedIntervalSnapshot>) {
    const runId = this.runId
    if (this.activeRunId === runId) return
    this.activeRunId = runId
    while (this.activeRunId === runId) {
      const task = [...this.records.values()].find((record) => record.status === 'NEW')
      if (!task) break
      try {
        const snapshot = await process(task, (status) => {
          if (this.activeRunId === runId) this.transition(task.interval, status)
        })
        if (this.activeRunId === runId) this.transition(task.interval, 'READY', { snapshot, error: undefined })
      } catch (error) {
        if (this.activeRunId === runId) this.transition(task.interval, 'FAILED', { error: { stage: 'producer', message: error instanceof Error ? error.message : String(error) } })
      }
    }
    if (this.activeRunId === runId) this.activeRunId = null
  }
  stop() {
    this.runId += 1
    this.activeRunId = null
  }

  private transition(interval: number, status: IntervalLifecycle, change: Partial<IntervalRecord> = {}) {
    const current = this.records.get(interval)
    if (!current) return
    console.info('[MagiFab] INTERVAL_TRANSITION', { interval, from: current.status, to: status })
    this.records.set(interval, { ...current, ...change, status, updatedAt: Date.now() })
    this.emit()
  }
  private emit() { this.listeners.forEach((listener) => listener()) }
}

// Kept as an API alias while consumers move to the production name.
export const IntervalStore = IntervalManager
