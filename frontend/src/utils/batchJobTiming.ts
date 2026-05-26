import { useEffect, useState } from 'react'
import type { BatchJurisdictionRun, BatchJob } from '../api/batchJobs'
import { parseApiDateTime } from './dateTime'

function compareJurisdictions(a: BatchJurisdictionRun, b: BatchJurisdictionRun): number {
  const stA = (a.state_code || '').toUpperCase()
  const stB = (b.state_code || '').toUpperCase()
  if (stA !== stB) return stA.localeCompare(stB)
  const nameA = (a.jurisdiction_name || a.jurisdiction_id || '').toLowerCase()
  const nameB = (b.jurisdiction_name || b.jurisdiction_id || '').toLowerCase()
  const byName = nameA.localeCompare(nameB)
  if (byName !== 0) return byName
  return (a.jurisdiction_id || '').localeCompare(b.jurisdiction_id || '')
}

/** Default table order: state, then jurisdiction name (then id). */
export function sortJurisdictions(jurisdictions: BatchJurisdictionRun[]): BatchJurisdictionRun[] {
  return [...jurisdictions].sort(compareJurisdictions)
}

/** Best timestamp for "last activity" on a jurisdiction row (ISO string). */
export function jurisdictionLastUpdatedIso(j: BatchJurisdictionRun): string | null {
  const candidates: string[] = []
  if (j.updated_at?.trim()) candidates.push(j.updated_at.trim())
  if (j.finished_at?.trim()) candidates.push(j.finished_at.trim())
  if (j.current_video_started_at?.trim()) candidates.push(j.current_video_started_at.trim())
  for (const v of j.videos || []) {
    if (v.finished_at?.trim()) candidates.push(v.finished_at.trim())
  }
  if (j.started_at?.trim()) candidates.push(j.started_at.trim())

  let best: string | null = null
  let bestMs = 0
  for (const iso of candidates) {
    const d = parseApiDateTime(iso)
    if (d && d.getTime() >= bestMs) {
      bestMs = d.getTime()
      best = iso
    }
  }
  return best
}

export function jurisdictionStateCodes(jurisdictions: BatchJurisdictionRun[]): string[] {
  const codes = new Set<string>()
  for (const j of jurisdictions) {
    const st = (j.state_code || '').toUpperCase().trim()
    if (st) codes.add(st)
  }
  return [...codes].sort()
}

export function filterJurisdictionsByState(
  jurisdictions: BatchJurisdictionRun[],
  stateFilter: string,
): BatchJurisdictionRun[] {
  const st = stateFilter.trim().toUpperCase()
  if (!st) return jurisdictions
  return jurisdictions.filter((j) => (j.state_code || '').toUpperCase() === st)
}

export type ActiveVideoRun = {
  videoId: string
  title: string
  jurisdictionId: string
  startedAt: string
}

function clockFromRunningJurisdiction(j: BatchJurisdictionRun): ActiveVideoRun | null {
  if (j.status !== 'running') return null

  if (j.current_video_started_at) {
    const started = parseApiDateTime(j.current_video_started_at)
    if (started) {
      return {
        videoId: j.current_video_id || '',
        title: j.current_video_title || '',
        jurisdictionId: j.jurisdiction_id,
        startedAt: j.current_video_started_at,
      }
    }
  }

  const videos = j.videos || []
  if (videos.length > 0) {
    const last = videos[videos.length - 1]
    if (last.finished_at) {
      const started = parseApiDateTime(last.finished_at)
      if (started) {
        return {
          videoId: j.current_video_id || last.video_id || '',
          title: j.current_video_title || last.title || '',
          jurisdictionId: j.jurisdiction_id,
          startedAt: last.finished_at,
        }
      }
    }
  }

  if (j.started_at) {
    const started = parseApiDateTime(j.started_at)
    if (started) {
      return {
        videoId: j.current_video_id || '',
        title: j.current_video_title || '',
        jurisdictionId: j.jurisdiction_id,
        startedAt: j.started_at,
      }
    }
  }

  return null
}

/** Running jurisdiction with an in-flight video (from batch job payload). */
export function findActiveVideoRun(
  jurisdictions: BatchJurisdictionRun[],
): ActiveVideoRun | null {
  let best: ActiveVideoRun | null = null
  let bestStarted = 0
  for (const j of jurisdictions) {
    const run = clockFromRunningJurisdiction(j)
    if (!run) continue
    const t = parseApiDateTime(run.startedAt)?.getTime() ?? 0
    if (!best || t >= bestStarted) {
      best = run
      bestStarted = t
    }
  }
  return best
}

export function resolveRunningFileClock(batch: BatchJob): ActiveVideoRun | null {
  const fromJurisdictions = findActiveVideoRun(batch.jurisdictions)
  if (fromJurisdictions) return fromJurisdictions

  if (batch.status !== 'running') return null
  const s = batch.summary || {}
  const iso = typeof s.current_video_started_at === 'string' ? s.current_video_started_at : ''
  if (!iso || !parseApiDateTime(iso)) return null
  return {
    videoId: typeof s.current_video_id === 'string' ? s.current_video_id : '',
    title: typeof s.current_video_title === 'string' ? s.current_video_title : '',
    jurisdictionId:
      typeof s.current_jurisdiction_id === 'string' ? s.current_jurisdiction_id : '',
    startedAt: iso,
  }
}

export function secondsSince(iso: string | null | undefined, nowMs = Date.now()): number | null {
  const started = parseApiDateTime(iso)
  if (!started) return null
  return Math.max(0, Math.floor((nowMs - started.getTime()) / 1000))
}

export function avgSecondsPerFile(summary: Record<string, unknown>): number | null {
  const fromApi = summary.avg_seconds_per_file
  if (fromApi != null && fromApi !== '') {
    const n = Number(fromApi)
    if (!Number.isNaN(n) && n > 0) return n
  }
  const elapsed = Number(summary.elapsed_seconds) || 0
  const processed = Number(summary.files_processed) || 0
  if (processed > 0 && elapsed > 0) return elapsed / processed
  const videos =
    (Number(summary.videos_ok) || 0) +
    (Number(summary.videos_fail) || 0) +
    (Number(summary.videos_tombstoned) || 0) +
    (Number(summary.videos_empty) || 0) +
    (Number(summary.videos_rate_limit) || 0)
  if (videos > 0 && elapsed > 0) return elapsed / videos
  return null
}

function doneVideosCount(j: BatchJurisdictionRun): number {
  const st = j.stats || {}
  return (
    (Number(st.ok) || 0) +
    (Number(st.fail) || 0) +
    (Number(st.tombstoned) || 0) +
    (Number(st.empty) || 0) +
    (Number(st.rate_limit) || 0)
  )
}

/** Remaining videos for one jurisdiction: pending − done (if pending is known). */
export function remainingVideosForJurisdiction(j: BatchJurisdictionRun): number | null {
  const pending = Number(j.stats?.pending)
  if (!Number.isFinite(pending) || pending <= 0) return null
  return Math.max(0, Math.floor(pending - doneVideosCount(j)))
}

function batchPlannedVideosEstimate(batch: BatchJob): number | null {
  // If every jurisdiction run reported stats.pending, we can be exact.
  // Otherwise, estimate remaining jurisdictions as N videos each.
  const cfgN = Number((batch.config as any)?.n)
  const n = Number.isFinite(cfgN) && cfgN > 0 ? Math.floor(cfgN) : null

  let pendingKnown = 0
  let pendingKnownCount = 0
  for (const j of batch.jurisdictions || []) {
    const p = Number(j.stats?.pending)
    if (!Number.isFinite(p) || p < 0) continue
    pendingKnown += Math.floor(p)
    pendingKnownCount += 1
  }

  const totalJurisdictions =
    Number((batch.summary as any)?.total_jurisdictions) ||
    Number((batch.config as any)?.total_jurisdictions) ||
    0

  if (pendingKnownCount > 0 && pendingKnownCount === (batch.jurisdictions || []).length) {
    return pendingKnown
  }

  if (!n || totalJurisdictions <= 0) {
    // We don't have enough info to estimate total work.
    return pendingKnownCount > 0 ? pendingKnown : null
  }

  const unknown = Math.max(0, totalJurisdictions - pendingKnownCount)
  return pendingKnown + unknown * n
}

/** Remaining videos across a batch (exact when pending counts exist; else estimated from N). */
export function remainingVideosForBatch(batch: BatchJob): number | null {
  const planned = batchPlannedVideosEstimate(batch)
  if (planned == null) return null

  let done = 0
  for (const j of batch.jurisdictions || []) {
    done += doneVideosCount(j)
  }
  return Math.max(0, Math.floor(planned - done))
}

/** Remaining videos across all running batches (best-effort). */
export function remainingVideosForRunningBatches(batches: BatchJob[]): number | null {
  let total = 0
  let any = false
  for (const b of batches) {
    if (b.status !== 'running') continue
    const rem = remainingVideosForBatch(b)
    if (rem == null) continue
    any = true
    total += rem
  }
  return any ? total : null
}

export function aggregateRunningFileTiming(batches: BatchJob[]): {
  avgSecondsPerFile: number | null
  activeVideo: ActiveVideoRun | null
  runningBatchCount: number
  idleRunningBatchCount: number
} {
  let totalElapsed = 0
  let totalFiles = 0
  let activeVideo: ActiveVideoRun | null = null
  let activeStarted = 0

  let runningBatchCount = 0
  let idleRunningBatchCount = 0

  for (const batch of batches) {
    if (batch.status !== 'running') continue
    runningBatchCount += 1
    const s = batch.summary || {}
    const elapsed = Number(s.elapsed_seconds) || 0
    const files =
      Number(s.files_processed) ||
      (Number(s.videos_ok) || 0) +
        (Number(s.videos_fail) || 0) +
        (Number(s.videos_tombstoned) || 0) +
        (Number(s.videos_empty) || 0) +
        (Number(s.videos_rate_limit) || 0)
    totalElapsed += elapsed
    totalFiles += files

    const run = resolveRunningFileClock(batch)
    if (!run) {
      idleRunningBatchCount += 1
      continue
    }
    const t = parseApiDateTime(run.startedAt)?.getTime() ?? 0
    if (!activeVideo || t >= activeStarted) {
      activeVideo = run
      activeStarted = t
    }
  }

  return {
    avgSecondsPerFile:
      totalFiles > 0 && totalElapsed > 0 ? totalElapsed / totalFiles : null,
    activeVideo,
    runningBatchCount,
    idleRunningBatchCount,
  }
}

/** Live counter for the in-flight video (ticks every second while enabled). */
export function useTickingSeconds(
  iso: string | null | undefined,
  enabled: boolean,
): number | null {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!enabled || !iso) return
    setNow(Date.now())
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [enabled, iso])
  if (!enabled || !iso) return null
  return secondsSince(iso, now)
}
