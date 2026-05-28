import api from '../lib/api'
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

export type BatchJobsDashboardPayload = {
  generated_at: string
  /** Latest batch/jurisdiction progress timestamp (not API build time). */
  last_activity_at?: string
  totals: BatchJobsTotals
  batches: BatchJob[]
  source?: 'database' | 'files'
  /** ``summary`` = metrics only; ``full`` = all per-video rows included. */
  detail?: 'summary' | 'full' | string
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
  const res = await api.get<BatchJobsDashboardPayload>('/batch-jobs', {
    params: {
      refresh_files: refreshFiles,
      enrich_bronze: false,
      detail,
      batch_limit: 25,
    },
    signal: AbortSignal.timeout(30_000),
  })
  return res.data
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
  const res = await api.get<FailedVideosListPayload>('/batch-jobs/failed-videos', {
    params: {
      ...(batchId ? { batch_id: batchId } : {}),
      limit,
    },
    signal: AbortSignal.timeout(60_000),
  })
  return res.data
}

export async function fetchBatchJurisdictions(
  batchId: string,
  stateCode: string,
): Promise<BatchJurisdictionRun[]> {
  // Typed against the generated OpenAPI contract: the path, the `batch_id`
  // path param and the required `state` query param are checked at compile
  // time. The result is bridged to the existing hand type while batchJobs.ts
  // is migrated incrementally (see lib/apiClient.ts).
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
  const res = await api.get<BatchJob>(`/batch-jobs/${encodeURIComponent(batchId)}`, {
    params: { enrich_bronze: false, include_videos: includeVideos },
  })
  return res.data
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
