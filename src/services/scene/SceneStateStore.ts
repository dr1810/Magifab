import type { CapturedVideoFrame } from '../ai/VideoFrameCaptureService'
import type { SceneState } from './SceneState'

export type SceneStateRecord = { interval: number; start: number; end: number; status: 'NEW' | 'CAPTURING' | 'PREPARING' | 'READY' | 'FAILED'; sceneState?: SceneState; representativeFrame?: CapturedVideoFrame }

export class SceneStateStore {
  private readonly records = new Map<number, SceneStateRecord>()
  private readonly listeners = new Set<() => void>()
  private runId = 0
  private activeRunId: number | null = null

  reset(duration: number, intervalSeconds: number) {
    this.stop()
    for (let interval = 0; interval < Math.ceil(duration / intervalSeconds); interval += 1) {
      const start = interval * intervalSeconds
      this.records.set(interval, { interval, start, end: Math.min(duration, start + intervalSeconds), status: 'NEW' })
    }
    this.emit()
    return this.records.size
  }
  subscribe(listener: () => void) {
    this.listeners.add(listener)
    return () => { this.listeners.delete(listener) }
  }
  getSceneState(timestamp: number, intervalSeconds: number) { return this.records.get(Math.floor(timestamp / intervalSeconds))?.sceneState }
  get(interval: number) { return this.records.get(interval) }
  getSnapshot(interval: number) { return this.records.get(interval)?.sceneState }
  get readyCount() { return [...this.records.values()].filter((record) => record.status === 'READY').length }
  get failedCount() { return [...this.records.values()].filter((record) => record.status === 'FAILED').length }
  stop() { this.runId += 1; this.activeRunId = null; this.records.clear() }

  async start(process: (task: SceneStateRecord, transition: (status: 'CAPTURING' | 'PREPARING') => void) => Promise<Omit<SceneStateRecord, 'interval' | 'start' | 'end' | 'status'>>) {
    const runId = this.runId
    if (this.activeRunId === runId) return
    this.activeRunId = runId
    while (this.activeRunId === runId) {
      const task = [...this.records.values()].find((record) => record.status === 'NEW')
      if (!task) break
      try {
        const result = await process(task, (status) => this.transition(task.interval, status))
        if (this.activeRunId === runId) this.transition(task.interval, 'READY', result)
      } catch {
        if (this.activeRunId === runId) this.transition(task.interval, 'FAILED')
      }
    }
    if (this.activeRunId === runId) this.activeRunId = null
  }
  private transition(interval: number, status: SceneStateRecord['status'], update: Partial<SceneStateRecord> = {}) {
    const record = this.records.get(interval)
    if (!record) return
    this.records.set(interval, { ...record, ...update, status })
    this.emit()
  }
  private emit() { this.listeners.forEach((listener) => listener()) }
}
