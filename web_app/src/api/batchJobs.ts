import { apiTyped } from '../lib/apiClient'

export type BatchJobsTotals = {
  batches: number
  running: number
  states: number
  states_planned: number
  states_started: number
  states_completed: number
  processed_jurisdictions: number
  failed_jurisdictions: number
  remaining_jurisdictions: number
  videos_ok: number
  videos_fail: number
  videos_attempted: number
  files_transcripts: number
  files_transcripts_disk: number
  transcript_hours: number
  bronze_download_rows: number
  files_analysis: number
  files_reports: number
  /** Analyses summarised in the last 24h (file mtime within the rolling window). */
  files_analysis_recent?: number
  /** Reports generated in the last 24h (file mtime within the rolling window). */
  files_reports_recent?: number
  /** Analysis errors stamped in the last 24h (bronze policy_analysis_error). */
  files_analysis_errors_recent?: number
  /** Report errors stamped in the last 24h (bronze policy_report_error). */
  files_reports_errors_recent?: number
  /** Most recent transcript-download stamp (all time, ISO) — "Last transcript" ago card. */
  last_transcript_at?: string
  /** Most recent analysis stamp (all time, ISO) — drives the "Last analysis" ago card. */
  last_analysis_at?: string
  /** Most recent report stamp (all time, ISO) — drives the "Last report" ago card. */
  last_report_at?: string
}

export type BatchVideoResult = {
  video_id: string
  title: string
  status: string
  error: string
  transcript_source: string
  finished_at: string
  duration_seconds?: number | null
}

export type BatchJurisdictionRun = {
  state_code: string
  jurisdiction_id: string
  jurisdiction_name: string
  status: string
  started_at: string
  updated_at?: string
  finished_at: string
  elapsed_seconds: number
  exit_code: number
  stats: Record<string, number>
  videos: BatchVideoResult[]
  file_counts: Record<string, number>
  current_video_id?: string
  current_video_title?: string
  current_video_started_at?: string
}

export type BatchJob = {
  batch_id: string
  step: string
  status: string
  started_at: string
  updated_at: string
  finished_at: string
  config: Record<string, unknown>
  summary: Record<string, unknown>
  jurisdictions: BatchJurisdictionRun[]
}

export type PipelineStage = 'discover' | 'videos' | 'transcripts' | 'analyses' | 'reports'

/** One (scope, stage) row. ``scope`` is a 2-letter state code or ``ALL`` (rollup). */
export type StageReportRow = {
  scope: string
  stage: PipelineStage | string
  done: number
  total: number
  failed: number
  last_at: string
}

export type StageTiming = {
  avg_seconds?: number | null
  last_path?: string
  last_at?: string
}

export type StageReport = {
  states: string[]
  rows: StageReportRow[]
  /** Per-stage cadence + last file: keyed by stage name. */
  timing?: Record<string, StageTiming>
}

export type LaunchLog = {
  step: string
  path: string
  lines: string[]
  /** Best-effort "current item" line parsed from the log tail. */
  current: string
  current_since: string
}

export async function fetchLaunchLog(step: string): Promise<LaunchLog> {
  const r = await fetch(
    `/api/batch-jobs/launch/log?step=${encodeURIComponent(step)}&lines=150`,
    { signal: AbortSignal.timeout(10_000) },
  )
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return (await r.json()) as LaunchLog
}

export type BatchJobsDashboardPayload = {
  generated_at: string
  /** Latest batch/jurisdiction progress timestamp (not API build time). */
  last_activity_at?: string
  totals: BatchJobsTotals
  batches: BatchJob[]
  /** Long-format per-state pipeline coverage (scope×stage rows). */
  stage_report?: StageReport
  source?: 'database' | 'files'
  /** ``summary`` = metrics only; ``full`` = all per-video rows included. */
  detail?: 'summary' | 'full' | string
}

export type LaunchStatus = {
  enabled: boolean
  busy: boolean
  running: number
  /** Steps currently running — different steps can run concurrently. */
  running_steps: string[]
  /** Live but stalled (>1h no activity) — re-launchable. */
  stalled_steps: string[]
  steps: string[]
}

export type LaunchResult = {
  launched: boolean
  pid?: number | null
  step: string
  states: string[]
  log: string
  detail: string
}

export async function fetchLaunchStatus(): Promise<LaunchStatus> {
  const r = await fetch('/api/batch-jobs/launch', {
    signal: AbortSignal.timeout(10_000),
  })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return (await r.json()) as LaunchStatus
}

export async function launchPipeline(body: {
  step: string
  states?: string[]
  n?: number
  parallel?: number
}): Promise<LaunchResult> {
  const r = await fetch('/api/batch-jobs/launch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15_000),
  })
  if (!r.ok) {
    let detail = `HTTP ${r.status}`
    try {
      const j = (await r.json()) as { error?: string; detail?: string }
      if (j?.error || j?.detail) detail = (j.error || j.detail) as string
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return (await r.json()) as LaunchResult
}

export type StopResult = {
  stopped: number
  steps: string[]
  pids: number[]
  detail: string
}

/** Stop running pipeline launch(es). Omit `step` to stop everything. */
export async function stopPipeline(body: {
  step?: string
  force?: boolean
} = {}): Promise<StopResult> {
  const r = await fetch('/api/batch-jobs/launch/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15_000),
  })
  if (!r.ok) {
    let detail = `HTTP ${r.status}`
    try {
      const j = (await r.json()) as { error?: string; detail?: string }
      if (j?.error || j?.detail) detail = (j.error || j.detail) as string
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return (await r.json()) as StopResult
}

export type BatchJobsDetailLevel = 'summary' | 'standard' | 'full'

type ApiErrorBody = { detail?: string | { msg?: string }[] }

/** User-visible message from failed ``api.get`` (includes FastAPI ``detail``). */
export function batchJobsFetchErrorMessage(error: unknown): string {
  const err = error as {
    message?: string
    response?: { data?: ApiErrorBody; status?: number; statusText?: string }
  }
  const detail = err.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (Array.isArray(detail)) {
    const text = detail.map((d) => d?.msg).filter(Boolean).join('; ')
    if (text) return text
  }
  if (err.response?.status) {
    return `HTTP ${err.response.status}: ${err.response.statusText ?? 'Error'}`
  }
  return err.message ?? 'unknown error'
}

export async function fetchBatchJobsDashboard(
  refreshFiles = false,
  detail: BatchJobsDetailLevel = 'summary',
): Promise<BatchJobsDashboardPayload> {
  const { data, error } = await apiTyped.GET('/api/batch-jobs/', {
    params: {
      query: {
        refresh_files: refreshFiles,
        enrich_bronze: false,
        detail,
        batch_limit: 25,
      },
    },
    signal: AbortSignal.timeout(30_000),
  })
  if (error) throw error
  return data as BatchJobsDashboardPayload
}

export type FailedVideosListPayload = {
  rows: Array<{
    batch_id: string
    batch_step: string
    state_code: string
    jurisdiction_id: string
    jurisdiction_name: string
    video: BatchVideoResult
  }>
  total_fail_in_summaries: number
  truncated: boolean
}

export async function fetchFailedVideos(
  batchId?: string,
  limit = 500,
): Promise<FailedVideosListPayload> {
  const { data, error } = await apiTyped.GET('/api/batch-jobs/failed-videos', {
    params: {
      query: { ...(batchId ? { batch_id: batchId } : {}), limit },
    },
    signal: AbortSignal.timeout(60_000),
  })
  if (error) throw error
  return data as FailedVideosListPayload
}

export async function fetchBatchJurisdictions(
  batchId: string,
  stateCode: string,
): Promise<BatchJurisdictionRun[]> {
  const { data, error } = await apiTyped.GET(
    '/api/batch-jobs/{batch_id}/jurisdictions',
    { params: { path: { batch_id: batchId }, query: { state: stateCode.toUpperCase() } } },
  )
  if (error) throw error
  return (data.jurisdictions ?? []) as BatchJurisdictionRun[]
}

export async function fetchBatchJobDetail(
  batchId: string,
  includeVideos: 'all' | 'failed_only' | 'none' | 'running' = 'all',
): Promise<BatchJob> {
  const { data, error } = await apiTyped.GET('/api/batch-jobs/{batch_id}', {
    params: {
      path: { batch_id: batchId },
      query: { enrich_bronze: false, include_videos: includeVideos },
    },
  })
  if (error) throw error
  return data as BatchJob
}

/** Attach on-demand jurisdiction rows to a summary-only batch row. */
export function mergeBatchJurisdictions(
  batch: BatchJob,
  jurisdictions: BatchJurisdictionRun[],
): BatchJob {
  return { ...batch, jurisdictions }
}

/** Merge jurisdiction rows (and videos) from a detail fetch into cached dashboard data. */
export function mergeBatchIntoDashboard(
  prev: BatchJobsDashboardPayload | undefined,
  batch: BatchJob,
): BatchJobsDashboardPayload | undefined {
  if (!prev) return prev
  const batches = prev.batches.map((b) =>
    b.batch_id === batch.batch_id ? { ...b, ...batch, jurisdictions: batch.jurisdictions } : b,
  )
  if (!batches.some((b) => b.batch_id === batch.batch_id)) {
    batches.unshift(batch)
  }
  return { ...prev, batches, detail: 'full' }
}

/** SSE URL for live dashboard updates (Postgres-backed). */
export function batchJobsStreamUrl(): string {
  const base = import.meta.env.PROD
    ? '/api'
    : import.meta.env.VITE_API_URL || '/api'
  const prefix = base.endsWith('/') ? base.slice(0, -1) : base
  return `${prefix}/batch-jobs/stream`
}
