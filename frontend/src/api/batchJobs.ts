import api from '../lib/api'

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
  totals: BatchJobsTotals
  batches: BatchJob[]
  source?: 'database' | 'files'
}

export async function fetchBatchJobsDashboard(
  refreshFiles = false,
): Promise<BatchJobsDashboardPayload> {
  const res = await api.get<BatchJobsDashboardPayload>('/batch-jobs', {
    params: { refresh_files: refreshFiles, enrich_bronze: true },
  })
  return res.data
}

/** SSE URL for live dashboard updates (Postgres-backed). */
export function batchJobsStreamUrl(): string {
  const base = import.meta.env.PROD
    ? '/api'
    : import.meta.env.VITE_API_URL || '/api'
  const prefix = base.endsWith('/') ? base.slice(0, -1) : base
  return `${prefix}/batch-jobs/stream`
}
