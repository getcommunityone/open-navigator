import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  batchJobsStreamUrl,
  batchJobsFetchErrorMessage,
  fetchBatchJobDetail,
  fetchBatchJurisdictions,
  fetchBatchJobsDashboard,
  fetchCohorts,
  type BatchCohort,
  fetchFailedVideos,
  fetchLaunchLog,
  fetchLaunchStatus,
  launchPipeline,
  stopPipeline,
  mergeBatchIntoDashboard,
  mergeBatchJurisdictions,
  type BatchJob,
  type BatchJurisdictionRun,
  type BatchJobsDashboardPayload,
  type BatchVideoResult,
  FULL_FILTER_OPTIONS,
  type PipelineStage,
  type StageReportRow,
} from '../api/batchJobs'
import DeploymentPanel from '../components/DeploymentPanel'
import { LinkifiedText } from '../utils/linkifiedText'
import {
  formatCompactHours,
  formatCompactNumber,
  formatCompactPair,
  formatFullNumber,
} from '../utils/formatCompact'
import {
  aggregateRunningFileTiming,
  avgSecondsPerFile,
  filterJurisdictionsByState,
  jurisdictionStateCodes,
  remainingVideosForRunningBatches,
  resolveRunningFileClock,
  jurisdictionLastUpdatedIso,
  latestDashboardActivityIso,
  remainingVideosForBatch,
  sortJurisdictions,
  useTickingSeconds,
} from '../utils/batchJobTiming'
import {
  formatAgoCompact,
  formatDateTimeAbsolute,
  formatUpdatedAt,
} from '../utils/dateTime'
import {
  fullRunPhaseFromLog,
  fullRunPhaseLabel,
  stageOwnsFullRunLog,
  type FullRunPhase,
} from '../lib/batchJobFullRunPhase'
import { STATE_CODES } from '../lib/usStates'

/** Stages lit as "running" for a live Run-all / Run-each phase (#761). */
function phasesToRunningStages(phase: FullRunPhase | null): PipelineStage[] {
  if (!phase) return []
  if (phase === 'discover') return ['discover']
  if (phase === 'videos') return ['videos']
  if (phase === 'transcripts') return ['transcripts']
  if (phase === 'analyses') return ['analyses_light']
  if (phase === 'reports') return ['reports_light']
  return []
}

type FailedVideoRow = {
  batch_id: string
  batch_step: string
  state_code: string
  jurisdiction_id: string
  jurisdiction_name: string
  video: BatchVideoResult
}

const FAILED_VIDEO_STATUSES = new Set([
  'fail',
  'failed',
  'tombstoned',
  'empty',
  'rate_limit',
  'error',
])

function isFailedVideoStatus(status: string): boolean {
  const s = (status || '').toLowerCase()
  if (!s || s === 'ok' || s === 'pending' || s === 'skipped') return false
  if (FAILED_VIDEO_STATUSES.has(s)) return true
  return s !== 'ok'
}

function failedVideoCount(j: BatchJurisdictionRun): number {
  const fromVideos = (j.videos || []).filter((v) => isFailedVideoStatus(v.status)).length
  const fromStats = Number(j.stats?.fail ?? 0)
  return Math.max(fromVideos, fromStats)
}

// Which runnable step advances each stage (used for the per-stage log drill-down).
const STAGE_STEP: Record<string, string> = {
  discover: 'discover',
  videos: 'catalog',
  transcripts: 'captions',
  analyses_light: 'analyze-light',
  reports_light: 'reports-light',
  analyses_full: 'analyze-full',
  reports_full: 'reports-full',
  // Legacy
  analyses: 'analyze-light',
  reports: 'reports-light',
}

const FULL_STAGE_SET = new Set(['analyses_full', 'reports_full'])
const FULL_FILTERS_STORAGE_KEY = 'batch-full-filters'

function defaultFullFilters(cohort: string): string[] {
  const keys = ['has_decisions', 'interestingness']
  if (cohort === 'data_centers') keys.push('data_center')
  return keys
}

function loadFullFilters(cohort: string): string[] {
  try {
    const raw = localStorage.getItem(FULL_FILTERS_STORAGE_KEY)
    if (!raw) return defaultFullFilters(cohort)
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return defaultFullFilters(cohort)
    const allowed = new Set(['has_decisions', 'interestingness', 'data_center'])
    const out = parsed
      .map((x) => String(x))
      .filter((k) => allowed.has(k))
    return out.length ? out : defaultFullFilters(cohort)
  } catch {
    return defaultFullFilters(cohort)
  }
}

function fmtSecs(s?: number | null): string {
  if (s == null || !Number.isFinite(s)) return '—'
  const v = Math.round(s)
  if (v < 60) return `${v}s`
  const m = Math.floor(v / 60)
  const r = v % 60
  return r ? `${m}m ${r}s` : `${m}m`
}

function baseName(p?: string): string {
  if (!p) return '—'
  const parts = p.split('/')
  return parts[parts.length - 1] || p
}

function fmtEta(hours: number): string {
  if (!Number.isFinite(hours) || hours <= 0) return '—'
  if (hours < 1) return `${Math.round(hours * 60)}m`
  if (hours < 48) return `${Math.round(hours)}h`
  return `${(hours / 24).toFixed(1)}d`
}

function mergeDashboardFromStream(
  prev: BatchJobsDashboardPayload | undefined,
  next: BatchJobsDashboardPayload,
): BatchJobsDashboardPayload {
  if (!prev || next.detail !== 'summary') {
    return next
  }
  const prevById = new Map(prev.batches.map((b) => [b.batch_id, b]))
  return {
    ...next,
    batches: next.batches.map((b) => {
      const older = prevById.get(b.batch_id)
      if (older?.jurisdictions?.length) {
        return { ...b, jurisdictions: older.jurisdictions }
      }
      return b
    }),
  }
}

function collectFailedVideos(
  batches: BatchJob[],
  opts?: { batchId?: string; jurisdictionId?: string },
): FailedVideoRow[] {
  const rows: FailedVideoRow[] = []
  for (const batch of batches) {
    if (opts?.batchId && batch.batch_id !== opts.batchId) continue
    for (const j of batch.jurisdictions) {
      if (opts?.jurisdictionId && j.jurisdiction_id !== opts.jurisdictionId) continue
      for (const v of j.videos || []) {
        if (!isFailedVideoStatus(v.status)) continue
        rows.push({
          batch_id: batch.batch_id,
          batch_step: batch.step,
          state_code: j.state_code,
          jurisdiction_id: j.jurisdiction_id,
          jurisdiction_name: j.jurisdiction_name,
          video: v,
        })
      }
    }
  }
  return rows
}

function formatDuration(seconds: unknown): string {
  if (seconds == null || seconds === '') return '—'
  const total = Math.max(0, Math.floor(Number(seconds)))
  if (Number.isNaN(total)) return '—'
  if (total < 60) return `${total}s`
  const m = Math.floor(total / 60)
  const s = total % 60
  if (m < 60) return `${m}m ${s}s`
  const h = Math.floor(m / 60)
  const remM = m % 60
  if (h >= 24) {
    const compact = formatCompactNumber(h)
    return remM > 0 ? `${compact}h ${remM}m` : `${compact}h`
  }
  return remM > 0 ? `${h}h ${remM}m` : `${h}h`
}

function metricCountTitle(n: unknown, label: string): string | undefined {
  const full = formatFullNumber(n)
  const compact = formatCompactNumber(n, '')
  if (!full || full === compact) return undefined
  return `${label}: ${full}`
}

function formatVideoDuration(seconds: unknown): string {
  if (seconds == null || seconds === '') return '—'
  const total = Math.max(0, Math.floor(Number(seconds)))
  if (Number.isNaN(total) || total <= 0) return '—'
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

function statusBadgeClass(status: string): string {
  if (status === 'completed' || status === 'ok') {
    return 'bg-emerald-100 text-emerald-800'
  }
  if (status === 'noop') {
    return 'bg-slate-100 text-slate-700'
  }
  if (status === 'failed' || status === 'fail') {
    return 'bg-red-100 text-red-800'
  }
  if (status === 'running') {
    return 'bg-sky-100 text-sky-800'
  }
  if (status === 'cancelled') {
    return 'bg-slate-200 text-slate-700'
  }
  if (status === 'pending') {
    return 'bg-amber-50 text-amber-900'
  }
  return 'bg-slate-100 text-slate-700'
}

function displayJurisdictionName(j: { jurisdiction_name?: string; jurisdiction_id?: string }): string {
  const raw = (j.jurisdiction_name || j.jurisdiction_id || '').trim()
  return raw.replace(/\s+(city|town|village|borough|municipality)\s*$/i, '').trim() || raw
}

function displayJurisdictionStatus(j: BatchJurisdictionRun): { label: string; badgeStatus: string } {
  const st = j.stats || {}
  if (Number(st.noop) > 0) return { label: 'noop', badgeStatus: 'noop' }
  if (Number(st.dry_run) > 0) return { label: 'dry-run', badgeStatus: 'noop' }
  return { label: j.status || 'pending', badgeStatus: j.status || 'pending' }
}

function SummaryCard({
  label,
  value,
  title,
  onClick,
  active,
  emphasis,
}: {
  label: string
  value: string | number
  title?: string
  onClick?: () => void
  active?: boolean
  emphasis?: 'danger' | 'default'
}) {
  const content = (
    <>
      <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div
        className={`mt-0.5 text-xl font-semibold tabular-nums ${
          emphasis === 'danger' ? 'text-red-700' : 'text-slate-900'
        }`}
      >
        {value}
      </div>
    </>
  )

  const className = `rounded-lg border px-3 py-2 text-left shadow-sm transition-colors ${
    active
      ? 'border-red-400 bg-red-50 ring-1 ring-red-300'
      : 'border-slate-200 bg-white hover:border-slate-300'
  } ${onClick ? 'cursor-pointer hover:bg-slate-50' : ''}`

  const tip = title || (onClick ? `View ${label}` : undefined)

  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={className} title={tip}>
        {content}
      </button>
    )
  }

  return (
    <div className={className} title={tip}>
      {content}
    </div>
  )
}

function ProgressBar({ pct }: { pct: number }) {
  const width = Math.min(100, Math.max(0, pct))
  return (
    <div className="h-2 overflow-hidden rounded-full bg-slate-200">
      <div
        className="h-full rounded-full bg-teal-600 transition-all duration-300"
        style={{ width: `${width}%` }}
      />
    </div>
  )
}

function FailedVideosPanel({
  rows,
  scopeLabel,
  subtitle,
  onClose,
  onSelectJurisdiction,
}: {
  rows: FailedVideoRow[]
  scopeLabel: string
  subtitle?: string
  onClose: () => void
  onSelectJurisdiction?: (batchId: string, jurisdictionId: string) => void
}) {
  return (
    <div className="rounded-lg border border-red-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-red-100 bg-red-50/80 px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold text-red-900">Failed videos</h3>
          <p className="text-xs text-red-800/80">
            {scopeLabel} · {rows.length} video{rows.length === 1 ? '' : 's'}
            {subtitle ? ` · ${subtitle}` : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-red-200 bg-white px-2.5 py-1 text-xs font-medium text-red-800 hover:bg-red-50"
        >
          Close
        </button>
      </div>
      <div className="overflow-auto max-h-[min(420px,55vh)]">
        {rows.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-slate-500">
            No per-video failure log yet. Failures are recorded when backfill runs with{' '}
            <code className="rounded bg-slate-100 px-1">--batch-id</code>.
          </p>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 bg-white text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2 font-medium">Jurisdiction</th>
                <th className="px-3 py-2 font-medium">Video</th>
                <th className="px-3 py-2 font-medium">Title</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Error</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={`${row.batch_id}-${row.jurisdiction_id}-${row.video.video_id}`}
                  className="border-t border-slate-100 align-top"
                >
                  <td className="px-3 py-2 text-xs">
                    <button
                      type="button"
                      className="text-left hover:text-teal-800"
                      onClick={() =>
                        onSelectJurisdiction?.(row.batch_id, row.jurisdiction_id)
                      }
                    >
                      <div className="font-medium text-slate-900">
                        {displayJurisdictionName({
                          jurisdiction_name: row.jurisdiction_name,
                          jurisdiction_id: row.jurisdiction_id,
                        })}
                      </div>
                      <div className="font-mono text-[11px] text-slate-500">
                        {row.state_code} · {row.jurisdiction_id}
                      </div>
                      <div className="mt-0.5 font-mono text-[10px] text-slate-400">
                        {row.batch_step}
                      </div>
                    </button>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">
                    <a
                      href={`https://www.youtube.com/watch?v=${row.video.video_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-teal-700 hover:underline"
                    >
                      {row.video.video_id}
                    </a>
                  </td>
                  <td className="max-w-[180px] px-3 py-2 text-xs text-slate-700">
                    {row.video.title || '—'}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <span
                      className={`rounded px-1.5 py-0.5 text-xs font-medium ${statusBadgeClass(row.video.status)}`}
                    >
                      {row.video.status}
                    </span>
                    {row.video.transcript_source ? (
                      <div className="mt-0.5 text-[10px] text-slate-500">
                        {row.video.transcript_source}
                      </div>
                    ) : null}
                  </td>
                  <td className="max-w-md px-3 py-2 text-xs text-red-800 whitespace-pre-wrap break-words">
                    {row.video.error ? (
                      <LinkifiedText
                        text={row.video.error}
                        linkClassName="font-medium text-teal-800 underline decoration-teal-500/70 hover:text-teal-950 break-all"
                      />
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function JurisdictionTable({
  jurisdictions,
  selectedId,
  onSelect,
  onShowFailedVideos,
  emptyMessage,
}: {
  jurisdictions: BatchJurisdictionRun[]
  selectedId: string | null
  onSelect: (id: string) => void
  onShowFailedVideos?: (jurisdictionId: string) => void
  emptyMessage?: string
}) {
  if (!jurisdictions.length) {
    return (
      <p className="py-6 text-center text-sm text-slate-500">
        {emptyMessage ?? (
          <>
            No jurisdictions recorded yet. Run{' '}
            <code className="rounded bg-slate-100 px-1">run_priority_states_last_n.sh captions</code>.
          </>
        )}
      </p>
    )
  }

  return (
    <div className="overflow-auto max-h-[min(420px,50vh)]">
      <table className="min-w-full text-sm">
        <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2 font-medium">State</th>
            <th className="px-3 py-2 font-medium">Jurisdiction</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 font-medium">Videos</th>
            <th className="px-3 py-2 font-medium">Files</th>
            <th className="px-3 py-2 font-medium">Time</th>
            <th className="px-3 py-2 font-medium" title="When this jurisdiction was last checked in the batch run">
              Last checked
            </th>
          </tr>
        </thead>
        <tbody>
          {jurisdictions.map((j) => {
            const st = j.stats || {}
            const fc = j.file_counts || {}
            const failCount = failedVideoCount(j)
            const disp = displayJurisdictionStatus(j)
            const selected = selectedId === j.jurisdiction_id
            const lastUpdated = formatUpdatedAt(jurisdictionLastUpdatedIso(j))
            return (
              <tr
                key={j.jurisdiction_id}
                className={`cursor-pointer border-t border-slate-100 hover:bg-teal-50/50 ${
                  selected ? 'bg-teal-50' : ''
                }`}
                onClick={() => onSelect(j.jurisdiction_id)}
              >
                <td className="px-3 py-2 font-mono text-xs">{j.state_code}</td>
                <td className="px-3 py-2">
                  <div className="font-medium text-slate-900">
                    {displayJurisdictionName(j)}
                  </div>
                  <div className="font-mono text-[11px] text-slate-500">{j.jurisdiction_id}</div>
                </td>
                <td className="px-3 py-2">
                  <span
                    className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${statusBadgeClass(disp.badgeStatus)}`}
                  >
                    {disp.label}
                    {j.exit_code ? ` (${j.exit_code})` : ''}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-slate-600">
                  {j.status === 'pending' ? (
                    <span className="text-slate-400">—</span>
                  ) : Number(st.noop) > 0 ? (
                    <span
                      className="text-slate-500"
                      title="Backfill ran; no videos needed download (already in bronze or on disk)"
                    >
                      all cached
                    </span>
                  ) : (
                    <>
                      ok {st.ok ?? 0} ·{' '}
                  {failCount > 0 && onShowFailedVideos ? (
                    <button
                      type="button"
                      className="font-medium text-red-700 underline decoration-red-300 hover:text-red-900"
                      title="View failed videos for this jurisdiction"
                      onClick={(e) => {
                        e.stopPropagation()
                        onShowFailedVideos(j.jurisdiction_id)
                      }}
                    >
                      fail {failCount}
                    </button>
                  ) : (
                    <>fail {failCount}</>
                  )}{' '}
                      · tomb {st.tombstoned ?? 0}
                    </>
                  )}
                </td>
                <td
                  className="px-3 py-2 text-xs text-slate-600"
                  title="Transcript / analysis / report files under policy cache for this place"
                >
                  {Number(st.noop) > 0 &&
                  !(fc.transcripts_disk ?? fc.transcripts) &&
                  !(fc.analysis_disk ?? fc.analysis) &&
                  !(fc.reports_disk ?? fc.reports) ? (
                    <span className="text-slate-400">—</span>
                  ) : (
                    <>
                      disk T {fc.transcripts_disk ?? fc.transcripts ?? 0} · A{' '}
                      {fc.analysis_disk ?? fc.analysis ?? 0} · R{' '}
                      {fc.reports_disk ?? fc.reports ?? 0}
                    </>
                  )}
                </td>
                <td className="px-3 py-2 text-xs tabular-nums text-slate-600">
                  {formatDuration(j.elapsed_seconds)}
                </td>
                <td
                  className="px-3 py-2 text-xs text-slate-600 whitespace-nowrap"
                  title={lastUpdated.title}
                >
                  {lastUpdated.display}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function VideoDrillDown({
  jurisdiction,
  onlyFailed = false,
}: {
  jurisdiction: BatchJurisdictionRun
  onlyFailed?: boolean
}) {
  const videos = useMemo(() => {
    const all = jurisdiction.videos || []
    if (!onlyFailed) return all
    return all.filter((v) => isFailedVideoStatus(v.status))
  }, [jurisdiction.videos, onlyFailed])

  return (
    <div
      id="batch-jurisdiction-drilldown"
      className="rounded-lg border border-slate-200 bg-white shadow-sm"
    >
      <div className="border-b border-slate-100 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-900">
          {onlyFailed ? 'Failed videos · ' : ''}
          {displayJurisdictionName(jurisdiction)}
        </h3>
        <p className="mt-0.5 font-mono text-xs text-slate-500">{jurisdiction.jurisdiction_id}</p>
        {onlyFailed ? (
          <p className="mt-1 text-xs text-red-800">
            {videos.length} failed video{videos.length === 1 ? '' : 's'} in this batch run
          </p>
        ) : null}
      </div>
      <div className="overflow-auto max-h-[min(360px,45vh)]">
        <table className="min-w-full text-sm">
          <thead className="sticky top-0 bg-white text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2 font-medium">Video</th>
              <th className="px-3 py-2 font-medium">Title</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Duration</th>
              <th className="px-3 py-2 font-medium">Source</th>
              <th className="px-3 py-2 font-medium">Error</th>
            </tr>
          </thead>
          <tbody>
            {videos.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-center text-xs text-slate-500">
                  {onlyFailed
                    ? 'No failed videos logged for this jurisdiction in this batch run.'
                    : (
                      <>
                        No per-video log for this run (re-run backfill with{' '}
                        <code>--batch-id</code>).
                      </>
                      )}
                </td>
              </tr>
            ) : (
              videos.map((v) => (
                <tr key={v.video_id} className="border-t border-slate-50">
                  <td className="px-3 py-2 font-mono text-xs">
                    <a
                      href={`https://www.youtube.com/watch?v=${v.video_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-teal-700 hover:underline"
                    >
                      {v.video_id}
                    </a>
                  </td>
                  <td className="max-w-[200px] truncate px-3 py-2 text-xs text-slate-700">
                    {v.title || '—'}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded px-1.5 py-0.5 text-xs font-medium ${statusBadgeClass(v.status)}`}
                    >
                      {v.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs tabular-nums text-slate-600 whitespace-nowrap">
                    {formatVideoDuration(v.duration_seconds)}
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-600">{v.transcript_source || '—'}</td>
                  <td className="max-w-md px-3 py-2 text-xs text-slate-600 whitespace-pre-wrap break-words">
                    {v.error ? (
                      <LinkifiedText text={v.error} />
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function BatchDetailPanel({
  batch,
  selectedJurisdictionId,
  onSelectJurisdiction,
  stateFilter,
  onStateFilterChange,
  showFailedVideos,
  onToggleFailedVideos,
  onShowFailedForJurisdiction,
}: {
  batch: BatchJob
  selectedJurisdictionId: string | null
  onSelectJurisdiction: (id: string | null) => void
  stateFilter: string
  onStateFilterChange: (state: string) => void
  showFailedVideos: boolean
  onToggleFailedVideos: () => void
  onShowFailedForJurisdiction: (jurisdictionId: string) => void
}) {
  const s = batch.summary || {}
  const total = Number(s.total_jurisdictions) || 0
  const processed = Number(s.processed_jurisdictions) || 0
  const pct = total > 0 ? Math.round((100 * processed) / total) : 0
  const cfg = batch.config || {}
  const states = Array.isArray(cfg.states) ? (cfg.states as string[]).join(', ') : '—'

  const selectedJurisdiction = useMemo(
    () =>
      batch.jurisdictions.find((j) => j.jurisdiction_id === selectedJurisdictionId) ?? null,
    [batch.jurisdictions, selectedJurisdictionId],
  )

  const videosFailCount = Number(s.videos_fail) || 0
  const isRunning = batch.status === 'running'
  const fileClock = useMemo(() => resolveRunningFileClock(batch), [batch])
  const currentFileSeconds = useTickingSeconds(
    fileClock?.startedAt,
    isRunning && !!fileClock?.startedAt,
  )
  const avgPerFileSec = avgSecondsPerFile(s)
  const batchRemainingVideos = useMemo(() => remainingVideosForBatch(batch), [batch])

  const stateCodes = useMemo(() => {
    const fromCfg = Array.isArray(cfg.states)
      ? (cfg.states as string[]).map((s) => String(s).toUpperCase().trim()).filter(Boolean)
      : []
    if (fromCfg.length) return [...new Set(fromCfg)].sort()
    return jurisdictionStateCodes(batch.jurisdictions)
  }, [batch.jurisdictions, cfg.states])
  const sortedJurisdictions = useMemo(
    () => sortJurisdictions(batch.jurisdictions),
    [batch.jurisdictions],
  )
  const displayedJurisdictions = useMemo(
    () => filterJurisdictionsByState(sortedJurisdictions, stateFilter),
    [sortedJurisdictions, stateFilter],
  )
  const showJurisdictionTable = !!stateFilter

  return (
    <div className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold text-slate-900">{batch.step}</h2>
          <span className={`rounded px-2 py-0.5 text-xs font-medium ${statusBadgeClass(batch.status)}`}>
            {batch.status}
          </span>
        </div>
        <p className="mt-1 font-mono text-xs text-slate-500">{batch.batch_id}</p>
        <p className="mt-1 text-xs text-slate-600">
          Started {formatDateTimeAbsolute(batch.started_at)}
          {batch.finished_at
            ? ` · Finished ${formatDateTimeAbsolute(batch.finished_at)}`
            : ''}
        </p>
        {isRunning && fileClock?.videoId ? (
          <p className="mt-1 text-xs text-slate-500">
            Current:{' '}
            <a
              href={`https://www.youtube.com/watch?v=${fileClock.videoId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-teal-700 hover:underline"
            >
              {fileClock.videoId}
            </a>
            {fileClock.title ? ` · ${fileClock.title.slice(0, 72)}` : ''}
          </p>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <SummaryCard
          label="Processed"
          value={formatCompactPair(processed, total || '?')}
          title={metricCountTitle(processed, 'Processed jurisdictions')}
        />
        <SummaryCard
          label="Success"
          value={formatCompactNumber(s.success_jurisdictions)}
          title={metricCountTitle(s.success_jurisdictions, 'Success jurisdictions')}
        />
        <SummaryCard
          label="Failed"
          value={formatCompactNumber(s.failed_jurisdictions)}
          title={metricCountTitle(s.failed_jurisdictions, 'Failed jurisdictions')}
        />
        <SummaryCard
          label="Jurisdictions remaining"
          value={formatCompactNumber(s.remaining_jurisdictions)}
          title={metricCountTitle(s.remaining_jurisdictions, 'Remaining jurisdictions')}
        />
        <SummaryCard label="Elapsed" value={formatDuration(s.elapsed_seconds)} />
        <SummaryCard label="ETA" value={formatDuration(s.eta_seconds)} />
        {isRunning ? (
          <>
            <SummaryCard label="Avg / file" value={formatDuration(avgPerFileSec)} />
            <SummaryCard
              label="Current file"
              value={formatDuration(currentFileSeconds)}
            />
            <SummaryCard
              label="Videos remaining"
              value={
                batchRemainingVideos != null
                  ? formatCompactNumber(batchRemainingVideos)
                  : '—'
              }
              title={metricCountTitle(batchRemainingVideos, 'Videos remaining')}
            />
          </>
        ) : null}
        <SummaryCard
          label="Videos OK"
          value={formatCompactNumber(s.videos_ok)}
          title={metricCountTitle(s.videos_ok, 'Videos OK')}
        />
        <SummaryCard
          label="Videos fail"
          value={formatCompactNumber(videosFailCount)}
          title={metricCountTitle(videosFailCount, 'Videos failed')}
          emphasis={videosFailCount > 0 ? 'danger' : 'default'}
          active={showFailedVideos}
          onClick={videosFailCount > 0 ? onToggleFailedVideos : undefined}
        />
      </div>

      <ProgressBar pct={pct} />
      <p className="text-xs text-slate-600">
        States: {states} · N={String(cfg.n ?? '—')} · delay={String(cfg.delay ?? '—')}s · source=
        {String(cfg.transcript_source || '—')}
      </p>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-2">
          <h3 className="text-sm font-semibold text-slate-800">
            Jurisdictions
            {showJurisdictionTable ? (
              <span className="ml-1 font-normal text-slate-500">
                ({displayedJurisdictions.length} in {stateFilter})
              </span>
            ) : null}
          </h3>
          <div className="flex items-center gap-2">
            <label
              htmlFor="batch-jobs-state-filter"
              className="text-[10px] font-medium uppercase tracking-wide text-slate-500"
            >
              State <span className="text-red-600">*</span>
            </label>
            <select
              id="batch-jobs-state-filter"
              value={stateFilter}
              onChange={(e) => onStateFilterChange(e.target.value)}
              required
              className="min-w-[8rem] rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-800 shadow-sm"
            >
              <option value="" disabled>
                Select state…
              </option>
              {stateCodes.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </div>
        </div>
        {showJurisdictionTable ? (
          <JurisdictionTable
            jurisdictions={displayedJurisdictions}
            selectedId={selectedJurisdictionId}
            onSelect={(id) => onSelectJurisdiction(id)}
            onShowFailedVideos={onShowFailedForJurisdiction}
            emptyMessage={`No jurisdictions in ${stateFilter} for this batch.`}
          />
        ) : (
          <p className="px-4 py-8 text-center text-sm text-slate-500">
            {selectedJurisdictionId
              ? 'Per-jurisdiction details are below. Pick a state to browse the full list for that state.'
              : 'Select a state to browse jurisdictions. The full plan is large; filter by state to keep the table fast.'}
          </p>
        )}
      </div>

      {selectedJurisdiction ? (
        <VideoDrillDown
          jurisdiction={selectedJurisdiction}
          onlyFailed={showFailedVideos}
        />
      ) : null}
    </div>
  )
}

// Priority dev states — mirrors the wrapper-script default (the STATES env in
// youtube_run_priority_states_last_n.sh). "All states" uses STATE_CODES (50 + DC).
const PRIORITY_STATE_CODES = ['AL', 'GA', 'IN', 'MA', 'MT', 'WA', 'WI']

function parseBatchCohort(raw: string | null | undefined): BatchCohort {
  if (raw === 'priority' || raw === 'data_centers' || raw === 'all') return raw
  return 'priority'
}

function cohortLaunchLabel(cohort: BatchCohort): string {
  if (cohort === 'data_centers') return 'data centers'
  if (cohort === 'all') return 'all 50 + DC'
  return 'priority'
}

function batchJobsDashboardQueryKey(cohort: BatchCohort) {
  return ['batch-jobs-dashboard', cohort] as const
}

type JobType = 'youtube' | 'load' | 'deployment'

function JobTypeTabs({
  active,
  onChange,
}: {
  active: JobType
  onChange: (t: JobType) => void
}) {
  const tabs: { key: JobType; label: string }[] = [
    { key: 'youtube', label: '1 Extract Transform' },
    { key: 'load', label: '2 Load' },
    { key: 'deployment', label: '3 Deploy' },
  ]
  return (
    <div className="flex gap-1 border-b border-slate-200">
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          onClick={() => onChange(t.key)}
          className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
            active === t.key
              ? 'border-sky-500 text-sky-700'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

export default function BatchJobStatusPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const typeParam = searchParams.get('type')
  const jobType: JobType =
    typeParam === 'deployment' ? 'deployment' : typeParam === 'load' ? 'load' : 'youtube'
  const setJobType = useCallback(
    (t: JobType) => {
      const next = new URLSearchParams(searchParams)
      if (t === 'deployment' || t === 'load') next.set('type', t)
      else next.delete('type')
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )
  const batchId = searchParams.get('batch') ?? ''
  const jurisdictionId = searchParams.get('jurisdiction') ?? ''
  const stateFilter = (searchParams.get('state') ?? '').toUpperCase()
  const showFailedVideos = searchParams.get('view') === 'failed-videos'
  const failedVideosScopeAll = searchParams.get('failed_scope') === 'all'
  const queryClient = useQueryClient()
  const [streamLive, setStreamLive] = useState(false)
  const [videosLoading, setVideosLoading] = useState(false)

  // URL is the single source of truth for Filter (cohort). Avoid useState↔URL
  // sync races that briefly (or permanently) keep Priority counts while the
  // select already shows Data centers.
  const allScope = parseBatchCohort(
    searchParams.get('cohort') ?? localStorage.getItem('batch-launch-scope'),
  )
  const setAllScope = useCallback(
    (v: BatchCohort, cohortStates?: string[]) => {
      localStorage.setItem('batch-launch-scope', v)
      const next = new URLSearchParams(searchParams)
      next.set('cohort', v)
      const st = (searchParams.get('state') ?? '').toUpperCase()
      const allowed = cohortStates ?? []
      if (st && allowed.length > 0 && !allowed.includes(st)) {
        next.delete('state')
      }
      setSearchParams(next, { replace: true })
      // Drop cached dashboards so numerator/denominator always refetch for the
      // newly selected Filter (priority / data_centers / all).
      void queryClient.invalidateQueries({ queryKey: ['batch-jobs-dashboard'] })
    },
    [searchParams, setSearchParams, queryClient],
  )

  useEffect(() => {
    if (searchParams.get('cohort')) return
    const next = new URLSearchParams(searchParams)
    next.set('cohort', allScope)
    setSearchParams(next, { replace: true })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- seed ?cohort= once

  useEffect(() => {
    localStorage.setItem('batch-launch-scope', allScope)
  }, [allScope])

  const { data: cohortsData } = useQuery({
    queryKey: ['batch-cohorts'],
    queryFn: fetchCohorts,
    staleTime: 300_000,
    retry: 1,
  })

  const { data, isPending, isFetching, isError, error, refetch } = useQuery({
    queryKey: batchJobsDashboardQueryKey(allScope),
    queryFn: ({ queryKey }) => {
      const cohort = (queryKey[1] as BatchCohort) || 'priority'
      return fetchBatchJobsDashboard(false, 'summary', cohort)
    },
    staleTime: 0,
    refetchOnWindowFocus: true,
    retry: 1,
  })

  useEffect(() => {
    if (!cohortsData || !stateFilter) return
    const allowed = cohortsData[allScope] ?? []
    if (allowed.length > 0 && !allowed.includes(stateFilter)) {
      const next = new URLSearchParams(searchParams)
      next.delete('state')
      setSearchParams(next, { replace: true })
    }
  }, [cohortsData, allScope, stateFilter, searchParams, setSearchParams])

  useEffect(() => {
    const cohort = allScope
    const url = batchJobsStreamUrl(cohort)
    const es = new EventSource(url)
    let active = true

    const applyPayload = (payload: BatchJobsDashboardPayload) => {
      if (!active) return
      queryClient.setQueryData<BatchJobsDashboardPayload>(
        batchJobsDashboardQueryKey(cohort),
        (prev) => mergeDashboardFromStream(prev, payload),
      )
    }

    es.onopen = () => {
      if (active) setStreamLive(true)
    }
    es.addEventListener('summary', (ev) => {
      try {
        applyPayload(JSON.parse(ev.data) as BatchJobsDashboardPayload)
      } catch {
        /* ignore */
      }
    })
    es.onerror = () => {
      if (!active) return
      setStreamLive(false)
      es.close()
      void refetch()
    }

    return () => {
      active = false
      setStreamLive(false)
      es.close()
    }
  }, [queryClient, refetch, allScope])

  const { data: launchStatus, refetch: refetchLaunch } = useQuery({
    queryKey: ['batch-launch-status'],
    queryFn: fetchLaunchStatus,
    // Snappy so Run/Stop enablement and dashboard poll wake with the launch (#761).
    refetchInterval: 4000,
    retry: false,
  })
  const launchBusy =
    !!launchStatus?.busy ||
    (launchStatus?.running_steps?.length ?? 0) > 0 ||
    (launchStatus?.stalled_steps?.length ?? 0) > 0
  // Catalog/discover do not bump youtube_batch_job_runs — poll while a launch
  // is live so Last activity / pills move (#757 / #761).
  useEffect(() => {
    if (!launchBusy) return
    const id = window.setInterval(() => {
      void refetch()
    }, 5000)
    return () => window.clearInterval(id)
  }, [launchBusy, refetch])
  const [launching, setLaunching] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [launchMsg, setLaunchMsg] = useState<string | null>(null)
  // Parallelism = how many jurisdictions analyze at once (the main throughput
  // lever). Persisted so it survives reloads; ceiling is the Gemini quota.
  const [parallelism, setParallelism] = useState<number>(() => {
    const v = Number(localStorage.getItem('batch-parallelism'))
    return v >= 1 && v <= 8 ? v : 6
  })
  const setParallel = useCallback((v: number) => {
    setParallelism(v)
    localStorage.setItem('batch-parallelism', String(v))
  }, [])
  // How many missing transcripts one ▶ Backfill click fetches. 0 = "All" (sweep
  // every missing transcript). The run is resumable — it re-queries what's still
  // missing — so a bounded size still makes incremental progress across clicks.
  // Persisted across reloads; defaults to 4000.
  const BACKFILL_SIZES = [100, 500, 2000, 4000, 0] as const
  const [backfillSize, setBackfillSizeState] = useState<number>(() => {
    const raw = localStorage.getItem('batch-backfill-size')
    const v = Number(raw)
    return raw != null && (BACKFILL_SIZES as readonly number[]).includes(v) ? v : 4000
  })
  const setBackfillSize = useCallback((v: number) => {
    setBackfillSizeState(v)
    localStorage.setItem('batch-backfill-size', String(v))
  }, [])
  // Per-stage drill-down: expand one stage to see its live log + current file.
  const [expandedStage, setExpandedStage] = useState<string | null>(null)
  const [fullFilters, setFullFiltersState] = useState<string[]>(() =>
    loadFullFilters('priority'),
  )
  const setFullFilters = useCallback((next: string[]) => {
    setFullFiltersState(next)
    localStorage.setItem(FULL_FILTERS_STORAGE_KEY, JSON.stringify(next))
  }, [])
  const toggleFullFilter = useCallback(
    (key: string) => {
      setFullFilters(
        fullFilters.includes(key)
          ? fullFilters.filter((k) => k !== key)
          : [...fullFilters, key],
      )
    },
    [fullFilters, setFullFilters],
  )

  const runLaunch = useCallback(
    async (step: string, states: string[], nOverride?: number) => {
      setLaunching(true)
      setLaunchMsg(null)
      try {
        const needsFilters =
          step === 'analyze-full' || step === 'reports-full'
        if (needsFilters && fullFilters.length === 0) {
          setLaunchMsg('Select at least one full eligibility filter before running.')
          return
        }
        const res = await launchPipeline({
          step,
          states,
          parallel: parallelism,
          n: nOverride ?? 25,
          cohort: allScope,
          ...(needsFilters ? { full_filters: fullFilters } : {}),
        })
        setLaunchMsg(res.detail || 'Launched.')
        // Open the stage that matches the launch so the live log is visible.
        if (step === 'all') {
          // Run all fans out stages 1–5 in parallel (#763); no single shared log.
          setExpandedStage(null)
        } else if (step === 'each' || step === 'catalog') {
          setExpandedStage('videos')
        } else if (step === 'discover') {
          setExpandedStage('discover')
        } else if (step === 'captions' || step === 'backfill') {
          setExpandedStage('transcripts')
        } else if (step === 'analyze' || step === 'analyze-light') {
          setExpandedStage('analyses_light')
        } else if (step === 'reports-light') {
          setExpandedStage('reports_light')
        } else if (step === 'analyze-full') {
          setExpandedStage('analyses_full')
        } else if (step === 'reports-full') {
          setExpandedStage('reports_full')
        }
        void refetchLaunch()
        window.setTimeout(() => void refetch(), 2500)
      } catch (e) {
        setLaunchMsg((e as Error).message || 'Launch failed')
      } finally {
        setLaunching(false)
      }
    },
    [refetchLaunch, refetch, parallelism, allScope, fullFilters],
  )

  const stopLaunch = useCallback(
    async (step?: string) => {
      const label = step ? `the '${step}' run` : 'all running jobs'
      if (!window.confirm(`Stop ${label}? In-flight work checkpoints and the process exits.`)) {
        return
      }
      setStopping(true)
      setLaunchMsg(null)
      try {
        const res = await stopPipeline(step ? { step } : {})
        setLaunchMsg(res.detail || 'Stop requested.')
        void refetchLaunch()
        window.setTimeout(() => void refetch(), 2500)
      } catch (e) {
        setLaunchMsg((e as Error).message || 'Stop failed')
      } finally {
        setStopping(false)
      }
    },
    [refetchLaunch, refetch],
  )
  const liveLaunchSteps = useMemo(() => {
    const steps = new Set<string>([
      ...(launchStatus?.running_steps ?? []),
      ...(launchStatus?.stalled_steps ?? []),
    ])
    return steps
  }, [launchStatus?.running_steps, launchStatus?.stalled_steps])
  // The Transcripts stage is advanced by two steps — per-jurisdiction `captions`
  // and the global `backfill` — which write separate launch logs. Show the
  // backfill log while it's the live (running/stalled) step; otherwise the
  // conventional captions log.
  const transcriptsBackfillLive = liveLaunchSteps.has('backfill')
  // Run all / each write one shared log. Only the *active* phase stage tails it
  // so Videos never dumps Discover output while Discover is still running (#761).
  const fullRunLogStep = liveLaunchSteps.has('each')
    ? 'each'
    : liveLaunchSteps.has('all')
      ? 'all'
      : null
  const { data: fullRunLog } = useQuery({
    queryKey: ['launch-log', fullRunLogStep, 'phase'],
    queryFn: () => fetchLaunchLog(fullRunLogStep as string),
    enabled: !!fullRunLogStep,
    refetchInterval: 4000,
    retry: false,
  })
  const fullRunPhase = useMemo(
    () =>
      fullRunPhaseFromLog(fullRunLog?.lines ?? [], fullRunLog?.current ?? '', {
        step: fullRunLogStep,
      }),
    [fullRunLog?.lines, fullRunLog?.current, fullRunLogStep],
  )
  const expandedOwnsFullRunLog = stageOwnsFullRunLog(expandedStage, fullRunPhase)
  const expandedStep = expandedStage
    ? expandedStage === 'transcripts' && transcriptsBackfillLive
      ? 'backfill'
      : expandedOwnsFullRunLog && fullRunLogStep
        ? fullRunLogStep
        : STAGE_STEP[expandedStage]
    : null
  const { data: stageLog } = useQuery({
    queryKey: ['launch-log', expandedStep],
    queryFn: () => fetchLaunchLog(expandedStep as string),
    enabled: !!expandedStep && !expandedOwnsFullRunLog,
    refetchInterval: 4000,
    retry: false,
  })
  const displayLog = expandedOwnsFullRunLog ? fullRunLog : stageLog

  const selectedBatch = useMemo(() => {
    if (!data?.batches?.length) return null
    if (batchId) {
      return data.batches.find((b) => b.batch_id === batchId) ?? data.batches[0]
    }
    return data.batches[0]
  }, [data, batchId])

  const setBatch = useCallback(
    (id: string) => {
      const next = new URLSearchParams(searchParams)
      next.set('batch', id)
      next.delete('jurisdiction')
      next.delete('state')
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const setStateFilter = useCallback(
    (state: string) => {
      const next = new URLSearchParams(searchParams)
      if (selectedBatch?.batch_id) next.set('batch', selectedBatch.batch_id)
      const st = state.trim().toUpperCase()
      if (st) next.set('state', st)
      else next.delete('state')
      if (jurisdictionId && selectedBatch) {
        const visible = filterJurisdictionsByState(
          sortJurisdictions(selectedBatch.jurisdictions),
          st,
        )
        if (!visible.some((j) => j.jurisdiction_id === jurisdictionId)) {
          next.delete('jurisdiction')
        }
      }
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams, selectedBatch, jurisdictionId],
  )

  const setJurisdiction = useCallback(
    (id: string | null) => {
      const next = new URLSearchParams(searchParams)
      if (selectedBatch?.batch_id) next.set('batch', selectedBatch.batch_id)
      if (id) next.set('jurisdiction', id)
      else next.delete('jurisdiction')
      next.delete('view')
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams, selectedBatch?.batch_id],
  )

  const setShowFailedVideos = useCallback(
    (
      open: boolean,
      opts?: { batchId?: string; jurisdictionId?: string; allBatches?: boolean },
    ) => {
      const next = new URLSearchParams(searchParams)
      if (opts?.batchId) next.set('batch', opts.batchId)
      if (opts?.jurisdictionId) next.set('jurisdiction', opts.jurisdictionId)
      else if (!open) next.delete('jurisdiction')
      if (open) {
        next.set('view', 'failed-videos')
        if (opts?.allBatches) next.set('failed_scope', 'all')
        else next.delete('failed_scope')
      } else {
        next.delete('view')
        next.delete('failed_scope')
      }
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const planStateCodes = useMemo(() => {
    if (!selectedBatch) return [] as string[]
    const fromCfg = Array.isArray(selectedBatch.config?.states)
      ? (selectedBatch.config.states as string[])
          .map((s) => String(s).toUpperCase().trim())
          .filter(Boolean)
      : []
    if (fromCfg.length) return [...new Set(fromCfg)].sort()
    return jurisdictionStateCodes(selectedBatch.jurisdictions)
  }, [selectedBatch])

  const effectiveStateFilter = useMemo(() => {
    if (!selectedBatch || !stateFilter) return ''
    return planStateCodes.includes(stateFilter) ? stateFilter : ''
  }, [selectedBatch, stateFilter, planStateCodes])

  const {
    data: stateJurisdictions,
    isFetching: stateJurisdictionsFetching,
  } = useQuery({
    queryKey: ['batch-jurisdictions', selectedBatch?.batch_id, effectiveStateFilter],
    queryFn: () =>
      fetchBatchJurisdictions(selectedBatch!.batch_id, effectiveStateFilter),
    enabled: !!selectedBatch?.batch_id && !!effectiveStateFilter,
    staleTime: 15_000,
  })

  const selectedBatchForPanel = useMemo(() => {
    if (!selectedBatch) return null
    if (!effectiveStateFilter) return selectedBatch
    if (stateJurisdictions) {
      return mergeBatchJurisdictions(selectedBatch, stateJurisdictions)
    }
    return selectedBatch
  }, [selectedBatch, effectiveStateFilter, stateJurisdictions])

  const visibleJurisdictions = useMemo(() => {
    if (!selectedBatchForPanel || !effectiveStateFilter) return []
    return filterJurisdictionsByState(
      sortJurisdictions(selectedBatchForPanel.jurisdictions),
      effectiveStateFilter,
    )
  }, [selectedBatchForPanel, effectiveStateFilter])

  const effectiveJurisdictionId = useMemo(() => {
    if (!jurisdictionId || !selectedBatch) return null
    if (!effectiveStateFilter) return jurisdictionId
    return visibleJurisdictions.some((j) => j.jurisdiction_id === jurisdictionId)
      ? jurisdictionId
      : null
  }, [jurisdictionId, selectedBatch, effectiveStateFilter, visibleJurisdictions])

  const selectedJurisdictionForVideos = useMemo(() => {
    if (!selectedBatchForPanel || !effectiveJurisdictionId) return null
    return (
      selectedBatchForPanel.jurisdictions.find(
        (j) => j.jurisdiction_id === effectiveJurisdictionId,
      ) ?? null
    )
  }, [selectedBatchForPanel, effectiveJurisdictionId])

  const failedVideosBatchId = failedVideosScopeAll
    ? undefined
    : selectedBatch?.batch_id

  const {
    data: failedVideosPayload,
    isFetching: failedVideosFetching,
  } = useQuery({
    queryKey: ['batch-failed-videos', failedVideosBatchId ?? 'all'],
    queryFn: () => fetchFailedVideos(failedVideosBatchId),
    enabled:
      showFailedVideos &&
      !effectiveJurisdictionId &&
      (data?.totals.videos_fail ?? 0) > 0,
    staleTime: 30_000,
  })

  useEffect(() => {
    if (!selectedBatch?.batch_id) return
    const needsJurisdictionVideos =
      !!effectiveJurisdictionId &&
      !!selectedJurisdictionForVideos &&
      (showFailedVideos
        ? failedVideoCount(selectedJurisdictionForVideos) > 0 &&
          !(selectedJurisdictionForVideos.videos || []).some((v) =>
            isFailedVideoStatus(v.status),
          )
        : (selectedJurisdictionForVideos.videos?.length ?? 0) === 0 &&
          (Number(selectedJurisdictionForVideos.stats?.ok ?? 0) > 0 ||
            failedVideoCount(selectedJurisdictionForVideos) > 0))
    if (!needsJurisdictionVideos) return

    let cancelled = false
    setVideosLoading(true)
    const mode = 'all'
    void fetchBatchJobDetail(selectedBatch.batch_id, mode)
      .then((batch) => {
        if (cancelled) return
        queryClient.setQueryData<BatchJobsDashboardPayload>(
          batchJobsDashboardQueryKey(allScope),
          (prev) => mergeBatchIntoDashboard(prev, batch) ?? prev,
        )
      })
      .finally(() => {
        if (!cancelled) setVideosLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [
    selectedBatch?.batch_id,
    effectiveJurisdictionId,
    showFailedVideos,
    selectedJurisdictionForVideos,
    data?.totals.videos_fail,
    allScope,
    queryClient,
  ])

  const allFailedVideoRows = useMemo((): FailedVideoRow[] => {
    if (effectiveJurisdictionId) {
      return collectFailedVideos(data?.batches ?? [], {
        batchId: selectedBatch?.batch_id,
        jurisdictionId: effectiveJurisdictionId,
      })
    }
    if (failedVideosPayload?.rows?.length) {
      return failedVideosPayload.rows.map((r) => ({
        batch_id: r.batch_id,
        batch_step: r.batch_step,
        state_code: r.state_code,
        jurisdiction_id: r.jurisdiction_id,
        jurisdiction_name: r.jurisdiction_name,
        video: r.video,
      }))
    }
    return collectFailedVideos(data?.batches ?? [], {
      batchId: failedVideosBatchId,
    })
  }, [
    data?.batches,
    selectedBatch?.batch_id,
    effectiveJurisdictionId,
    failedVideosPayload,
    failedVideosBatchId,
  ])

  const failedScopeLabel = useMemo(() => {
    if (effectiveJurisdictionId && selectedBatch) {
      const j = selectedBatch.jurisdictions.find(
        (x) => x.jurisdiction_id === effectiveJurisdictionId,
      )
      return `${selectedBatch.step} · ${j?.jurisdiction_name || effectiveJurisdictionId}`
    }
    if (failedVideosScopeAll) return 'All recent batches'
    if (selectedBatch) return `Batch ${selectedBatch.step} (${selectedBatch.batch_id})`
    return 'All batches'
  }, [effectiveJurisdictionId, selectedBatch, failedVideosScopeAll])

  const failedVideosSubtitle = useMemo(() => {
    if (effectiveJurisdictionId) return undefined
    const total =
      failedVideosPayload?.total_fail_in_summaries ?? data?.totals.videos_fail ?? 0
    const parts: string[] = []
    if (total > allFailedVideoRows.length) {
      parts.push(`${total} in summaries`)
    }
    if (failedVideosPayload?.truncated) {
      parts.push('list capped at 500')
    }
    return parts.length ? parts.join('; ') : undefined
  }, [
    effectiveJurisdictionId,
    failedVideosPayload,
    data?.totals.videos_fail,
    allFailedVideoRows.length,
  ])

  const lastActivityIso = useMemo(() => {
    const fromApi = data?.last_activity_at?.trim()
    if (fromApi) return fromApi
    const fromBatches = latestDashboardActivityIso(data?.batches ?? [])
    if (fromBatches) return fromBatches
    const running = data?.batches?.find((b) => b.status === 'running')
    return running?.updated_at?.trim() || null
  }, [data?.last_activity_at, data?.batches])
  const [agoClockMs, setAgoClockMs] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setAgoClockMs(Date.now()), 10_000)
    return () => window.clearInterval(id)
  }, [])
  const lastUpdateAgo = useMemo(
    () => (lastActivityIso ? formatAgoCompact(lastActivityIso, agoClockMs) : null),
    [lastActivityIso, agoClockMs],
  )
  const lastUpdateAbsolute = useMemo(
    () => (lastActivityIso ? formatUpdatedAt(lastActivityIso) : null),
    [lastActivityIso],
  )
  // Analyze/report runs don't touch the batch tracker (see "Last batch step"), so
  // these "ago" cards read the most recent policy stamps instead — the real signal
  // that the analyze pipeline is alive, including standalone/parallel runs.
  const lastTranscriptIso = data?.totals.last_transcript_at?.trim() || null
  const lastAnalysisIso = data?.totals.last_analysis_at?.trim() || null
  const lastReportIso = data?.totals.last_report_at?.trim() || null
  const lastTranscriptAgo = useMemo(
    () => (lastTranscriptIso ? formatAgoCompact(lastTranscriptIso, agoClockMs) : null),
    [lastTranscriptIso, agoClockMs],
  )
  const lastTranscriptAbsolute = useMemo(
    () => (lastTranscriptIso ? formatUpdatedAt(lastTranscriptIso) : null),
    [lastTranscriptIso],
  )
  const lastAnalysisAgo = useMemo(
    () => (lastAnalysisIso ? formatAgoCompact(lastAnalysisIso, agoClockMs) : null),
    [lastAnalysisIso, agoClockMs],
  )
  const lastReportAgo = useMemo(
    () => (lastReportIso ? formatAgoCompact(lastReportIso, agoClockMs) : null),
    [lastReportIso, agoClockMs],
  )
  const lastAnalysisAbsolute = useMemo(
    () => (lastAnalysisIso ? formatUpdatedAt(lastAnalysisIso) : null),
    [lastAnalysisIso],
  )
  const lastReportAbsolute = useMemo(
    () => (lastReportIso ? formatUpdatedAt(lastReportIso) : null),
    [lastReportIso],
  )

  const runningTiming = useMemo(
    () => aggregateRunningFileTiming(data?.batches ?? []),
    [data?.batches],
  )
  const remainingVideos = useMemo(
    () => remainingVideosForRunningBatches(data?.batches ?? []),
    [data?.batches],
  )
  const globalCurrentFileSeconds = useTickingSeconds(
    runningTiming.activeVideo?.startedAt,
    (data?.totals.running ?? 0) > 0 && !!runningTiming.activeVideo,
  )

  if (jobType === 'deployment' || jobType === 'load') {
    return (
      <div className="min-h-0 w-full space-y-4">
        <JobTypeTabs active={jobType} onChange={setJobType} />
        <DeploymentPanel group={jobType === 'load' ? 'load' : 'deploy'} />
      </div>
    )
  }

  return (
    <div className="min-h-0 w-full space-y-4">
      <JobTypeTabs active={jobType} onChange={setJobType} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-slate-600">
          Live from <code>bronze.youtube_batch_job_runs</code> via{' '}
          <code>GET /api/batch-jobs/stream</code>
          {streamLive && (
            <span className="ml-2 inline-flex items-center gap-1 text-emerald-700">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
              connected
            </span>
          )}
        </p>
      </div>

      {isPending && !data && (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          Loading batch summary…
        </div>
      )}

      {isFetching && data && (
        <p className="text-xs text-slate-500">Refreshing batch summary…</p>
      )}

      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          Could not load batch jobs: {batchJobsFetchErrorMessage(error)}
          <p className="mt-2 text-xs text-red-700">
            Start or restart the API:{' '}
            <code className="rounded bg-red-100 px-1">
              uvicorn api.main:app --reload --port 8001
            </code>
            . Apply migration 073 if needed. Batch runs sync from{' '}
            <code>run_priority_states_last_n.sh</code>.
            {!streamLive && (
              <>
                {' '}
                <button
                  type="button"
                  className="underline"
                  onClick={() => refetch()}
                >
                  Retry load
                </button>
              </>
            )}
          </p>
        </div>
      )}

      {data && (
        <>
          {(() => {
            const report = data.stage_report ?? { states: [], rows: [] }
            // Prefer API cohort state lists; fall back so Data centers still has a
            // Scope list (and ALL rollup) before /cohorts returns.
            const cohortStates =
              cohortsData?.[allScope] ??
              (allScope === 'all'
                ? STATE_CODES
                : allScope === 'data_centers'
                  ? report.states?.length
                    ? report.states
                    : []
                  : PRIORITY_STATE_CODES)
            // Cohort list is source of truth; intersect with report.states to hide empty rows.
            const stateOpts = report.states?.length
              ? cohortStates.filter((s) => report.states!.includes(s))
              : cohortStates
            const scope = stateFilter && stateOpts.includes(stateFilter) ? stateFilter : 'ALL'
            const rowFor = (
              sc: string,
              stage: PipelineStage,
            ): StageReportRow | undefined =>
              report.rows.find((r) => r.scope === sc && r.stage === stage)
            const fmtPct = (done: number, total: number) => {
              if (!total) return '—'
              const r = Math.round((done / total) * 1000) / 10
              return `${Number.isInteger(r) ? r : r.toFixed(1)}%`
            }
            const agoFromIso = (iso?: string) =>
              iso ? formatAgoCompact(iso, agoClockMs) : null
            // #792: the failed count on Videos / Transcripts opens the reason breakdown for the
            // same Filter and Scope (both ride in the URL so the page's title matches the numbers).
            const openReasons = (stage: PipelineStage) => () => {
              const q = new URLSearchParams({ stage, cohort: allScope })
              if (scope !== 'ALL') q.set('state', scope)
              navigate(`/admin/batch-jobs/failures?${q}`)
            }
            const setScope = (sc: string) => {
              const next = new URLSearchParams(searchParams)
              if (sc) next.set('state', sc)
              else next.delete('state')
              setSearchParams(next, { replace: true })
            }
            const stageList: PipelineStage[] = [
              'discover',
              'videos',
              'transcripts',
              'analyses_light',
              'reports_light',
              'analyses_full',
              'reports_full',
            ]
            const stageLabel: Record<string, string> = {
              discover: 'Discover',
              videos: 'Videos',
              transcripts: 'Transcripts',
              analyses_light: 'Analysis light',
              reports_light: 'Reports light',
              analyses_full: 'Analysis full',
              reports_full: 'Reports full',
            }
            // Discover-stage per-entity split labels (counties vs municipalities).
            const entityShort: Record<string, string> = {
              counties: 'Co',
              municipalities: 'Mun',
            }
            const entityLabel: Record<string, string> = {
              counties: 'Counties',
              municipalities: 'Municipalities (cities/towns)',
            }
            // Which runnable step each stage's "Run" button kicks off.
            const stageStep: Record<string, string> = {
              discover: 'discover',
              videos: 'catalog',
              transcripts: 'captions',
              analyses_light: 'analyze-light',
              reports_light: 'reports-light',
              analyses_full: 'analyze-full',
              reports_full: 'reports-full',
            }
            const stepDesc: Record<string, string> = {
              discover:
                'discover channels (scrape sites / search YouTube) then load matches to bronze',
              videos: 'catalog — list videos on the channel',
              transcripts: 'captions — download transcripts',
              analyses_light: 'analyze-light — lite Part 1 (DeepSeek, Jev-gated)',
              reports_light: 'reports-light — Part 2 from light analysis (DeepSeek)',
              analyses_full: 'analyze-full — deep Part 1 on filtered subset',
              reports_full: 'reports-full — Part 2 from full analysis',
            }
            type Def = {
              n: number
              stage: PipelineStage
              unit: string
              sub?: string
              pill: boolean
              drill: (() => void) | null
              failTitle: string
              inRunAll?: boolean
            }
            const defs: Def[] = [
              {
                n: 0,
                stage: 'discover',
                unit: 'jurisdictions',
                sub: 'channel discovery + load — scrape sites / search YouTube, then catalog matches',
                pill: true,
                drill: null,
                failTitle: 'Jurisdictions still missing a YouTube channel',
                inRunAll: true,
              },
              {
                n: 1,
                stage: 'videos',
                unit: 'attempted',
                pill: false,
                drill: openReasons('videos'),
                failTitle: 'Videos whose caption fetch failed — tap to see why',
                inRunAll: true,
              },
              {
                n: 2,
                stage: 'transcripts',
                unit: 'videos',
                sub: 'YouTube caption attempts in this Filter (not LocalView/CivicSearch)',
                pill: true,
                drill: openReasons('transcripts'),
                failTitle: 'Videos with no usable transcript — tap to see why',
                inRunAll: true,
              },
              {
                n: 3,
                stage: 'analyses_light',
                unit: 'videos',
                sub: 'lite Part 1 stamps ÷ transcripts in this Filter (not deep Part 1 / full)',
                pill: true,
                drill: openReasons('analyses_light'),
                failTitle: 'Analysis errors (bronze policy_analysis_error) — tap to see them',
                inRunAll: true,
              },
              {
                n: 4,
                stage: 'reports_light',
                unit: 'videos',
                sub: 'lite Part 2 stamps ÷ analysis light in this Filter',
                pill: true,
                drill: openReasons('reports_light'),
                failTitle: 'Report errors (bronze policy_report_error) — tap to see them',
                inRunAll: true,
              },
              {
                n: 5,
                stage: 'analyses_full',
                unit: 'videos',
                sub: 'deep Part 1 stamps ÷ transcripts · opt-in filters',
                pill: true,
                drill: openReasons('analyses_full'),
                failTitle: 'Full analysis errors (bronze policy_analysis_full_error) — tap to see them',
                inRunAll: false,
              },
              {
                n: 6,
                stage: 'reports_full',
                unit: 'videos',
                sub: 'deep Part 2 stamps ÷ analysis full · opt-in',
                pill: true,
                drill: openReasons('reports_full'),
                failTitle: 'Full report errors (bronze policy_report_full_error) — tap to see them',
                inRunAll: false,
              },
            ]
            // Fixed-width Failed/Run columns so the progress column lines up across rows.
            const cols =
              'grid grid-cols-[1.4fr_0.8fr_minmax(0,1.7fr)_4.5rem_6.5rem] items-center gap-3'
            const ls = launchStatus
            // ALL view scope → an explicit launch target (priority set or 50 + DC)
            // so the backend can't silently fall back to its priority-only default.
            const launchScopeStates = scope === 'ALL' ? cohortStates : [scope]
            const cohortLabel = cohortLaunchLabel(allScope)
            const scopeLaunchLabel =
              scope !== 'ALL' ? `${cohortLabel} · ${scope}` : cohortLabel
            // Each running step maps to the stage(s) it advances. Different steps
            // run concurrently, so we union them for the live "running" markers.
            const stepStages: Record<string, PipelineStage[]> = {
              discover: ['discover'],
              catalog: ['videos'],
              captions: ['videos', 'transcripts'],
              // Global mart-wide sweep — advances only the transcripts stage.
              backfill: ['transcripts'],
              analyze: ['analyses_light'],
              'analyze-light': ['analyses_light'],
              'reports-light': ['reports_light'],
              'analyze-full': ['analyses_full'],
              'reports-full': ['reports_full'],
              // `all` = discover → … → reports-light (#755). Full stages excluded.
              all: [
                'discover',
                'videos',
                'transcripts',
                'analyses_light',
                'reports_light',
              ],
              each: [
                'videos',
                'transcripts',
                'analyses_light',
                'reports_light',
              ],
            }
            const runningSteps = new Set(ls?.running_steps ?? [])
            const stalledSteps = new Set(ls?.stalled_steps ?? [])
            const runningStages = new Set<PipelineStage>()
            runningSteps.forEach((s) => {
              if ((s === 'all' || s === 'each') && fullRunPhase) {
                phasesToRunningStages(fullRunPhase).forEach((g) =>
                  runningStages.add(g),
                )
                return
              }
              ;(stepStages[s] ?? []).forEach((g) => runningStages.add(g))
            })
            // One launch at a time: Stop is the only action while busy (#761).
            const pipelineBusy =
              runningSteps.size > 0 || stalledSteps.size > 0 || !!ls?.busy
            const canRunStage = (_g: PipelineStage) =>
              !!ls?.enabled && !launching && !pipelineBusy
            const canRunBackfill =
              !!ls?.enabled && !launching && !pipelineBusy
            /** Which launch step a stage's ■ Stop should target. */
            const stopStepForStage = (stage: PipelineStage): string | null => {
              const step = stageStep[stage]
              if (runningSteps.has(step) || stalledSteps.has(step)) return step
              if (
                stage === 'transcripts' &&
                (runningSteps.has('backfill') || stalledSteps.has('backfill'))
              ) {
                return 'backfill'
              }
              if (
                (runningSteps.has('all') || stalledSteps.has('all')) &&
                stageOwnsFullRunLog(stage, fullRunPhase)
              ) {
                return 'all'
              }
              if (
                (runningSteps.has('each') || stalledSteps.has('each')) &&
                stageOwnsFullRunLog(stage, fullRunPhase)
              ) {
                return 'each'
              }
              return null
            }
            // Header "last activity" = freshest stage stamp (parsed time, not string).
            const freshestIso = stageList
              .map((s) => rowFor(scope, s)?.last_at || '')
              .filter(Boolean)
              .reduce<(string | null)>((best, iso) => {
                if (!best) return iso
                const a = Date.parse(best)
                const b = Date.parse(iso)
                if (!Number.isFinite(b)) return best
                if (!Number.isFinite(a)) return iso
                return b >= a ? iso : best
              }, null)
            const freshestAgo = agoFromIso(freshestIso ?? undefined)
            // Mirrors the API stall window (_LAUNCH_STALL_SECONDS /
            // BATCH_JOB_INACTIVITY_SECONDS, default 3600s). Warn earlier via
            // launchStatus.warning / vpn_down (#750, default 15m).
            const STALL_SECONDS = 3600
            const freshestAgeSecs =
              freshestIso && Number.isFinite(Date.parse(freshestIso))
                ? Math.max(0, Math.floor((agoClockMs - Date.parse(freshestIso)) / 1000))
                : null
            // A batch row stays status='running' after its worker dies or starts
            // skipping already-done work, so totals.running alone overstates
            // liveness. Count row-running as live only with recent recorded
            // progress; otherwise it's a stalled run the reaper hasn't swept yet.
            const rowsStale =
              data.totals.running > 0 &&
              runningSteps.size === 0 &&
              freshestAgeSecs != null &&
              freshestAgeSecs > STALL_SECONDS
            const liveRunningRows = data.totals.running > 0 && !rowsStale
            // Gate on live rows (not raw totals.running) so a phantom/stale
            // status=running batch after Stop all does not pin Run all (#742).
            const canRunAll =
              !!ls?.enabled &&
              !launching &&
              !pipelineBusy &&
              !liveRunningRows
            const isActive = liveRunningRows || runningSteps.size > 0
            const anyStalled = stalledSteps.size > 0 || rowsStale
            const launchWarning = (
              ls?.warning ||
              ls?.auto_resume_note ||
              ''
            ).trim()
            const vpnDown = !!ls?.vpn_down
            const billingExhausted = !!ls?.billing_exhausted
            const resumedSteps = ls?.resumed_steps ?? []
            const statusText = billingExhausted
              ? 'Billing down'
              : vpnDown
                ? 'VPN down'
                : isActive
                  ? launchWarning
                    ? 'Running · warning'
                    : 'Running'
                  : anyStalled
                    ? 'Stalled'
                    : 'Idle'
            const statusDot = billingExhausted || vpnDown
              ? 'bg-rose-500'
              : isActive
                ? launchWarning
                  ? 'bg-amber-500'
                  : 'bg-emerald-500'
                : anyStalled
                  ? 'bg-amber-500'
                  : 'bg-slate-400'
            return (
              <>
              <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
                {launchWarning ? (
                  <div
                    role="status"
                    className={`border-b px-4 py-2 text-sm ${
                      billingExhausted || vpnDown
                        ? 'border-rose-200 bg-rose-50 text-rose-900'
                        : 'border-amber-200 bg-amber-50 text-amber-950'
                    }`}
                  >
                    <span className="font-semibold">
                      {billingExhausted
                        ? 'Billing error'
                        : vpnDown
                          ? 'VPN error'
                          : resumedSteps.length > 0
                            ? 'Auto-resumed'
                            : 'Inactivity warning'}
                    </span>
                    <span className="mx-1.5 text-current/40">·</span>
                    <span>{launchWarning}</span>
                  </div>
                ) : null}
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
                  <div className="flex flex-wrap items-center gap-1.5 text-sm">
                    <span
                      className={`inline-block h-2.5 w-2.5 rounded-full ${statusDot} ${
                        isActive && !vpnDown ? 'animate-pulse' : ''
                      }`}
                    />
                    <span className="font-semibold text-slate-800">{statusText}</span>
                    {freshestAgo ? (
                      <span className="text-slate-500">· last activity {freshestAgo}</span>
                    ) : null}
                    <span className="text-slate-500">
                      {runningSteps.size > 0
                        ? `· running ${[...runningSteps].join(', ')}`
                        : rowsStale
                          ? `· ${formatCompactNumber(data.totals.running)} running, no progress >1h — likely stalled`
                          : stalledSteps.size > 0
                            ? `· ${[...stalledSteps].join(', ')} timed out (no activity 1h)`
                            : `· ${formatCompactNumber(data.totals.running)} running`}
                    </span>
                    {scope !== 'ALL' ? (
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600">
                        {scopeLaunchLabel}
                      </span>
                    ) : (
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600">
                        {cohortLabel}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {ls?.enabled ? (
                      <label
                        className="flex items-center gap-1.5 text-xs text-slate-500"
                        title="Filter: which places a run targets (priority states, data-center jurisdictions, or all US states). Use Scope to narrow to one state. Applies to the next launch and stage numbers."
                      >
                        <span className="font-medium uppercase tracking-wide text-slate-500">
                          Filter
                        </span>
                        <select
                          aria-label="Filter"
                          value={allScope}
                          onChange={(e) =>
                            setAllScope(
                              e.target.value as BatchCohort,
                              cohortsData?.[e.target.value as BatchCohort],
                            )
                          }
                          className="rounded-md border border-slate-300 bg-white px-1.5 py-1 text-xs font-medium text-slate-700"
                        >
                          <option value="priority">Priority states</option>
                          <option value="data_centers">Data centers</option>
                          <option value="all">All states (50 + DC)</option>
                        </select>
                      </label>
                    ) : null}
                    {ls?.enabled ? (
                      <label
                        className="flex items-center gap-1 text-xs text-slate-500"
                        title="Jurisdictions analyzed in parallel — the main throughput lever (ceiling is Gemini quota). Applies to the next launch."
                      >
                        <span aria-hidden>⚡</span>
                        <select
                          value={parallelism}
                          onChange={(e) => setParallel(Number(e.target.value))}
                          className="rounded-md border border-slate-300 bg-white px-1.5 py-1 text-xs font-medium text-slate-700"
                        >
                          {[2, 4, 6, 8].map((p) => (
                            <option key={p} value={p}>
                              {p}× parallel
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    {ls?.enabled ? (
                      <button
                        type="button"
                        disabled={!canRunAll}
                        onClick={() => runLaunch('all', launchScopeStates)}
                        title={
                          runningSteps.size > 0
                            ? 'Finish the running step(s) before a full-pipeline run'
                            : `Run stages 1–5 in parallel (discover, catalog, captions, analysis light, reports light) for ${scopeLaunchLabel}`
                        }
                        className="inline-flex items-center gap-1 rounded-md bg-[#354F52] px-2.5 py-1.5 text-xs font-semibold uppercase tracking-wide text-white shadow-sm hover:bg-[#2c4346] disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {launching ? 'Launching…' : `▶ Run all · ${scopeLaunchLabel}`}
                      </button>
                    ) : null}
                    {ls?.enabled && (ls?.busy || runningSteps.size > 0 || stalledSteps.size > 0) ? (
                      <button
                        type="button"
                        disabled={stopping}
                        onClick={() => void stopLaunch()}
                        title="Stop all running pipeline jobs (SIGTERM — work checkpoints and exits)"
                        className="inline-flex items-center gap-1 rounded-md bg-rose-600 px-2.5 py-1.5 text-xs font-semibold uppercase tracking-wide text-white shadow-sm hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {stopping ? 'Stopping…' : '■ Stop all'}
                      </button>
                    ) : null}
                    {stateOpts.length > 0 ? (
                      <label
                        className="flex items-center gap-1.5 text-xs text-slate-500"
                        title="Scope the stage numbers (and the detail tables) to one state within the Filter"
                      >
                        <span className="font-medium uppercase tracking-wide text-slate-500">
                          Scope
                        </span>
                        <select
                          aria-label="Scope"
                          value={scope === 'ALL' ? '' : scope}
                          onChange={(e) => setScope(e.target.value)}
                          className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
                        >
                          <option value="">All in filter</option>
                          {stateOpts.map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                  </div>
                </div>
                {launchMsg ? (
                  <div className="border-b border-slate-100 bg-slate-50 px-4 py-1.5 text-xs text-slate-600">
                    {launchMsg}
                  </div>
                ) : null}
                <div
                  className={`${cols} px-4 py-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400`}
                >
                  <div>Stage</div>
                  <div>Last activity</div>
                  <div>Progress</div>
                  <div className="text-right">Failed</div>
                  <div className="text-right">Run</div>
                </div>
                {defs.map((st, idx) => {
                  const r = rowFor(scope, st.stage)
                  const done = r?.done ?? 0
                  const total = r?.total ?? 0
                  const failed = r?.failed ?? 0
                  const pct = total ? (done / total) * 100 : 0
                  const ago = agoFromIso(r?.last_at)
                  const running = runningStages.has(st.stage)
                  const stopStep = stopStepForStage(st.stage)
                  const expanded = expandedStage === st.stage
                  const tm = data.stage_report?.timing?.[st.stage]
                  // Live pace: avg_seconds is the median gap between *completed*
                  // files, so it freezes during a stall (no new gap is ever
                  // recorded). Once a running stage is overdue for its next
                  // completion, our best estimate of the current pace is at
                  // least how long we've already been waiting — fold the open
                  // trailing gap in so /hr and ETA degrade every clock tick and
                  // recover the moment a file lands.
                  const avgSecs = tm?.avg_seconds && tm.avg_seconds > 0 ? tm.avg_seconds : null
                  const lastAtMs = tm?.last_at ? Date.parse(tm.last_at) : NaN
                  const sinceLastSecs = Number.isFinite(lastAtMs)
                    ? Math.max(0, (agoClockMs - lastAtMs) / 1000)
                    : null
                  const effectiveSecs =
                    avgSecs == null
                      ? null
                      : running && sinceLastSecs != null
                        ? Math.max(avgSecs, sinceLastSecs)
                        : avgSecs
                  const stalled =
                    running &&
                    avgSecs != null &&
                    sinceLastSecs != null &&
                    sinceLastSecs > avgSecs * 3
                  return (
                    <Fragment key={st.stage}>
                    <div className={`${cols} border-t border-slate-100 px-4 py-3`}>
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedStage(expanded ? null : st.stage)
                        }
                        className="min-w-0 text-left"
                        title="Show this stage's live log + timing"
                      >
                        <div className="flex items-center gap-1 text-sm font-semibold text-slate-800">
                          <span className="text-slate-400">{expanded ? '▾' : '▸'}</span>
                          {idx + 1} · {stageLabel[st.stage]}
                        </div>
                        {st.sub ? (
                          <div className="mt-0.5 flex items-center gap-1 text-[11px] text-amber-600">
                            <span aria-hidden>⚠️</span>
                            <span className="truncate" title={st.sub}>
                              {st.sub}
                            </span>
                          </div>
                        ) : null}
                      </button>
                      <div className="flex items-center gap-1.5 text-sm">
                        {running ? (
                          <span
                            className="inline-block h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-emerald-500"
                            title="Stage worker is running"
                          />
                        ) : (
                          <span className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
                        )}
                        <span
                          className={
                            running ? 'font-medium tabular-nums text-emerald-700' : 'tabular-nums text-slate-600'
                          }
                          title={running ? 'Last activity (stage is running)' : 'Last activity'}
                        >
                          {ago ?? '—'}
                        </span>
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm tabular-nums text-slate-700">
                          <span className="font-semibold text-slate-900">
                            {formatCompactNumber(done)}
                          </span>{' '}
                          / {formatCompactNumber(total)} {st.unit} · {fmtPct(done, total)}
                          {isFetching ? (
                            <span className="ml-1 text-[10px] font-normal text-slate-400">
                              updating…
                            </span>
                          ) : null}
                        </div>
                        <div className="mt-1.5">
                          <ProgressBar pct={pct} />
                        </div>
                        {st.stage === 'discover' && (r?.breakdown?.length ?? 0) > 0 ? (
                          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-slate-500">
                            {r!.breakdown!.map((b) => (
                              <span
                                key={b.entity}
                                title={`${entityLabel[b.entity] ?? b.entity}: ${formatCompactNumber(b.done)} of ${formatCompactNumber(b.total)} with a channel`}
                              >
                                <span className="font-medium text-slate-600">
                                  {entityLabel[b.entity] ?? b.entity}
                                </span>{' '}
                                {fmtPct(b.done, b.total)}{' '}
                                <span className="tabular-nums text-slate-400">
                                  {formatCompactNumber(b.done)}/{formatCompactNumber(b.total)}
                                </span>
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                      <div className="text-right">
                        {failed > 0 ? (
                          st.drill ? (
                            <button
                              type="button"
                              onClick={st.drill}
                              title={st.failTitle}
                              className={
                                st.pill
                                  ? 'inline-flex items-center gap-0.5 rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700 hover:bg-red-100'
                                  : 'text-sm font-semibold text-red-700 hover:underline'
                              }
                            >
                              {formatCompactNumber(failed)}
                              <span className="text-red-400" aria-hidden>
                                ⌄
                              </span>
                            </button>
                          ) : (
                            <span
                              title={st.failTitle}
                              className="inline-flex items-center rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700"
                            >
                              {formatCompactNumber(failed)}
                            </span>
                          )
                        ) : (
                          <span className="text-xs text-slate-400">0</span>
                        )}
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        {ls?.enabled && stopStep ? (
                          <button
                            type="button"
                            disabled={stopping}
                            onClick={() => void stopLaunch(stopStep)}
                            title={`Stop ${stopStep} (auto-resume off for this step)`}
                            className="whitespace-nowrap rounded-md border border-red-300 bg-red-50 px-2 py-1 text-[11px] font-semibold text-red-700 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            {stopping ? 'Stopping…' : '■ Stop'}
                          </button>
                        ) : null}
                        {ls?.enabled && !stopStep ? (
                          <button
                            type="button"
                            disabled={
                              !canRunStage(st.stage) ||
                              (FULL_STAGE_SET.has(st.stage) && fullFilters.length === 0)
                            }
                            onClick={() => runLaunch(stageStep[st.stage], launchScopeStates)}
                            title={
                              FULL_STAGE_SET.has(st.stage) && fullFilters.length === 0
                                ? 'Select at least one eligibility filter (expand this stage)'
                                : pipelineBusy
                                  ? 'A pipeline job is running — Stop it before starting another'
                                  : `Run ${stepDesc[st.stage]} · ${scopeLaunchLabel}`
                            }
                            className="whitespace-nowrap rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            ▶ Run
                          </button>
                        ) : null}
                        {/* Transcripts only: global mart-wide sweep (also reaches
                            LocalView/union videos captions never visits). The
                            size picker sets how many missing transcripts one
                            click fetches (All = sweep everything). */}
                        {ls?.enabled && st.stage === 'transcripts' ? (
                          <>
                            <button
                              type="button"
                              disabled={!canRunBackfill}
                              onClick={() =>
                                runLaunch(
                                  'backfill',
                                  // The backfill is a flat mart-wide sweep, so
                                  // "All states (50 + DC)" is best expressed as
                                  // an unfiltered national sweep ([] → backend
                                  // omits --states). A literal 50 + DC state
                                  // filter silently drops the CivicSearch videos
                                  // that carry no state_code (~19.5k school +
                                  // ~3k general), which are the priority sources
                                  // here. Priority/single-state scopes still
                                  // filter as before.
                                  scope === 'ALL' && allScope === 'all'
                                    ? []
                                    : launchScopeStates,
                                  backfillSize,
                                )
                              }
                              title={
                                runningSteps.has('backfill')
                                  ? 'backfill is already running'
                                  : `Backfill ${
                                      backfillSize === 0 ? 'all' : backfillSize
                                    } missing transcript(s) across the full event mart (LocalView + YouTube) · ${scopeLaunchLabel}`
                              }
                              className="whitespace-nowrap rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              {runningSteps.has('backfill') ? '· · ·' : '▶ Backfill'}
                            </button>
                            <select
                              value={backfillSize}
                              onChange={(e) => setBackfillSize(Number(e.target.value))}
                              title="How many missing transcripts one Backfill click fetches (All = sweep everything; runs are resumable)"
                              className="w-full rounded-md border border-slate-300 bg-white px-1 py-0.5 text-[10px] font-medium text-slate-600 hover:bg-slate-50"
                            >
                              <option value={100}>100</option>
                              <option value={500}>500</option>
                              <option value={2000}>2,000</option>
                              <option value={4000}>4,000</option>
                              <option value={0}>All</option>
                            </select>
                          </>
                        ) : null}
                      </div>
                    </div>
                    {expanded ? (
                      <div className="border-t border-slate-100 bg-slate-50 px-4 py-3 text-xs text-slate-600">
                        <div className="flex flex-wrap gap-x-6 gap-y-1">
                          <span>
                            avg <b className="text-slate-800">{fmtSecs(avgSecs)}</b>/file
                            {effectiveSecs ? ` · ${Math.round(3600 / effectiveSecs)}/hr` : ''}
                            {stalled ? (
                              <span
                                className="ml-1 font-semibold text-amber-600"
                                title="No new completions — /hr and ETA now reflect the time since the last file, not the historical pace"
                              >
                                · stalled
                              </span>
                            ) : null}
                          </span>
                          {effectiveSecs && total - done > 0 ? (
                            <span>
                              ETA{' '}
                              <b className={stalled ? 'text-amber-600' : 'text-slate-800'}>
                                {fmtEta(((total - done) * effectiveSecs) / 3600)}
                              </b>{' '}
                              for {formatCompactNumber(total - done)} left
                            </span>
                          ) : null}
                          <span>
                            last file:{' '}
                            <b className="text-slate-800" title={tm?.last_path}>
                              {baseName(tm?.last_path)}
                            </b>
                            {tm?.last_at ? ` · ${agoFromIso(tm.last_at) ?? ''}` : ''}
                          </span>
                          {running &&
                          expandedOwnsFullRunLog &&
                          displayLog?.current ? (
                            <span className="min-w-0">
                              current:{' '}
                              <b className="text-emerald-700">{displayLog.current}</b>
                              {displayLog.current_since
                                ? ` · ${agoFromIso(displayLog.current_since) ?? ''} on it`
                                : ''}
                            </span>
                          ) : null}
                        </div>
                        {FULL_STAGE_SET.has(st.stage) ? (
                          <div className="mb-2 rounded border border-slate-200 bg-white px-3 py-2">
                            <p className="mb-1.5 text-[11px] text-slate-600">
                              Full runs only on videos that already have analysis light and
                              match any checked filter.
                            </p>
                            <div className="flex flex-wrap gap-x-4 gap-y-1">
                              {FULL_FILTER_OPTIONS.map((opt) => (
                                <label
                                  key={opt.key}
                                  className="inline-flex items-center gap-1.5 text-[11px] text-slate-700"
                                >
                                  <input
                                    type="checkbox"
                                    checked={fullFilters.includes(opt.key)}
                                    onChange={() => toggleFullFilter(opt.key)}
                                    className="rounded border-slate-300"
                                  />
                                  {opt.label}
                                </label>
                              ))}
                            </div>
                            {fullFilters.length === 0 ? (
                              <p className="mt-1 text-[11px] font-medium text-amber-700">
                                Check at least one filter to enable Run.
                              </p>
                            ) : null}
                          </div>
                        ) : null}
                        {fullRunLogStep && expandedOwnsFullRunLog ? (
                          <p className="mb-1 text-[11px] text-teal-800">
                            Showing the live{' '}
                            <code className="text-[10px]">Run {fullRunLogStep}</code> log
                            {fullRunLogStep === 'all'
                              ? ` · currently in ${fullRunPhaseLabel(fullRunPhase)}`
                              : ''}
                            .
                          </p>
                        ) : null}
                        {fullRunLogStep && !expandedOwnsFullRunLog ? (
                          <p className="mb-1 text-[11px] text-amber-800">
                            Run {fullRunLogStep} is still in{' '}
                            <b>{fullRunPhaseLabel(fullRunPhase)}</b>
                            {' — '}
                            this stage has not started yet. Open that stage for the live log.
                          </p>
                        ) : null}
                        {displayLog?.blocker &&
                        !(fullRunLogStep && !expandedOwnsFullRunLog) ? (
                          <p
                            role="status"
                            className="mb-1 rounded border border-rose-200 bg-rose-50 px-2 py-1.5 text-[11px] text-rose-900"
                          >
                            <span className="font-semibold">Blocker</span>
                            <span className="mx-1 text-rose-300">·</span>
                            {displayLog.blocker}
                          </p>
                        ) : null}
                        <pre className="mt-2 max-h-56 overflow-auto rounded bg-slate-900 p-2 text-[10px] leading-snug text-slate-100">
                          {fullRunLogStep && !expandedOwnsFullRunLog
                            ? `(waiting) Run ${fullRunLogStep} is in ${fullRunPhaseLabel(fullRunPhase)} — no ${st.stage} output yet.`
                            : displayLog?.lines?.length
                              ? displayLog.lines.join('\n')
                              : 'No log for this step yet — launch it to see live output.'}
                        </pre>
                        {!(fullRunLogStep && !expandedOwnsFullRunLog) && displayLog?.path ? (
                          <div className="mt-1 text-[10px] text-slate-400">
                            log: {displayLog.path}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                    </Fragment>
                  )
                })}
                <div className="border-t border-slate-100 px-4 py-2 text-[11px] text-slate-400">
                  <span className="text-emerald-500" aria-hidden>
                    ●
                  </span>{' '}
                  retryable{'   '}
                  <span className="text-slate-500" aria-hidden>
                    ▪
                  </span>{' '}
                  terminal · tap a failed count to drill in
                  {ls && !ls.enabled ? ' · launch disabled (set BATCH_JOBS_ALLOW_LAUNCH=1)' : ''}
                </div>
              </section>

              {stateOpts.length > 0 ? (
                <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-100 px-4 py-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                    State coverage · {stateOpts.length} states · click a row to scope
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-[10px] uppercase tracking-wide text-slate-400">
                          <th className="px-4 py-2 text-left font-semibold">State</th>
                          {stageList.map((s) => (
                            <th key={s} className="px-3 py-2 text-right font-semibold">
                              {stageLabel[s]}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {stateOpts.map((stCode) => (
                          <tr
                            key={stCode}
                            onClick={() => setScope(stCode)}
                            className={`cursor-pointer border-t border-slate-100 hover:bg-slate-50 ${
                              scope === stCode ? 'bg-slate-50' : ''
                            }`}
                          >
                            <td className="px-4 py-2 font-semibold text-slate-800">{stCode}</td>
                            {stageList.map((s) => {
                              const r = rowFor(stCode, s)
                              const done = r?.done ?? 0
                              const total = r?.total ?? 0
                              const bd = s === 'discover' ? r?.breakdown ?? [] : []
                              return (
                                <td key={s} className="px-3 py-2 text-right tabular-nums">
                                  <div className="text-slate-700">{fmtPct(done, total)}</div>
                                  <div className="text-[10px] text-slate-400">
                                    {formatCompactNumber(done)}/{formatCompactNumber(total)}
                                  </div>
                                  {bd.length > 0 ? (
                                    <div className="mt-0.5 space-y-px">
                                      {bd.map((b) => (
                                        <div
                                          key={b.entity}
                                          className="text-[10px] text-slate-400"
                                          title={`${entityLabel[b.entity] ?? b.entity}: ${formatCompactNumber(b.done)} of ${formatCompactNumber(b.total)} with a channel`}
                                        >
                                          <span className="text-slate-500">
                                            {entityShort[b.entity] ?? b.entity}
                                          </span>{' '}
                                          {fmtPct(b.done, b.total)}{' '}
                                          <span className="text-slate-300">
                                            {formatCompactNumber(b.done)}/{formatCompactNumber(b.total)}
                                          </span>
                                        </div>
                                      ))}
                                    </div>
                                  ) : null}
                                </td>
                              )
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ) : null}
              </>
            )
          })()}

          <details className="group">
            <summary className="cursor-pointer select-none py-1 text-xs font-medium text-slate-500 hover:text-slate-700">
              All metrics
            </summary>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
            {lastActivityIso && lastUpdateAgo ? (
              <SummaryCard
                label="Last batch step"
                value={lastUpdateAgo}
                title={
                  lastUpdateAbsolute?.title
                    ? `${lastUpdateAbsolute.title} · last catalog/captions batch step (NOT the analyze pipeline — see Last analysis/report)${
                        data.source === 'database' ? ' · from database' : ''
                      }`
                    : 'Last catalog/captions batch step (NOT the analyze pipeline — see Last analysis/report)'
                }
              />
            ) : null}
            {lastTranscriptIso && lastTranscriptAgo ? (
              <SummaryCard
                label="Last transcript"
                value={lastTranscriptAgo}
                title={
                  lastTranscriptAbsolute?.title
                    ? `${lastTranscriptAbsolute.title} · most recent transcript downloaded (transcript_download_at)`
                    : 'Most recent transcript downloaded (transcript_download_at)'
                }
              />
            ) : null}
            {lastAnalysisIso && lastAnalysisAgo ? (
              <SummaryCard
                label="Last analysis"
                value={lastAnalysisAgo}
                title={
                  lastAnalysisAbsolute?.title
                    ? `${lastAnalysisAbsolute.title} · most recent AI analysis written (policy_analysis_at; includes standalone/parallel analyze runs)`
                    : 'Most recent AI analysis written (includes standalone/parallel analyze runs)'
                }
              />
            ) : null}
            {lastReportIso && lastReportAgo ? (
              <SummaryCard
                label="Last report"
                value={lastReportAgo}
                title={
                  lastReportAbsolute?.title
                    ? `${lastReportAbsolute.title} · most recent report generated (policy_report_at; includes standalone/parallel analyze runs)`
                    : 'Most recent report generated (includes standalone/parallel analyze runs)'
                }
              />
            ) : null}
            <SummaryCard
              label="Batches"
              value={formatCompactNumber(data.totals.batches)}
              title={metricCountTitle(data.totals.batches, 'Batches')}
            />
            <SummaryCard
              label="Running"
              value={formatCompactNumber(data.totals.running)}
              title={
                runningTiming.idleRunningBatchCount > 0
                  ? `${formatFullNumber(data.totals.running)} batch(es) with status running; ${runningTiming.idleRunningBatchCount} idle (no active file). Idle runs auto-cancel after 1h without progress.`
                  : metricCountTitle(data.totals.running, 'Running batches')
              }
            />
            <SummaryCard
              label="States started"
              value={formatCompactPair(
                data.totals.states_started ?? 0,
                data.totals.states_planned ?? data.totals.states ?? 0,
              )}
              title="States with at least one jurisdiction running or finished in the batch plan"
            />
            <SummaryCard
              label="States completed"
              value={formatCompactPair(
                data.totals.states_completed ?? 0,
                data.totals.states_planned ?? data.totals.states ?? 0,
              )}
              title="States where every planned jurisdiction row is finished (none pending or running)"
            />
            {data.totals.running > 0 ? (
              <>
                <SummaryCard
                  label="Avg / file"
                  value={formatDuration(runningTiming.avgSecondsPerFile)}
                />
                <SummaryCard
                  label="Current file"
                  value={
                    runningTiming.activeVideo
                      ? formatDuration(globalCurrentFileSeconds)
                      : 'Idle'
                  }
                  title={
                    runningTiming.activeVideo
                      ? [
                          'Time on this in-flight video since it started (can exceed Avg / file if yt-dlp is slow or stuck).',
                          runningTiming.activeVideo.title,
                          runningTiming.activeVideo.videoId,
                          runningTiming.activeVideo.jurisdictionId,
                        ]
                          .filter(Boolean)
                          .join(' · ') || 'In-flight video'
                      : runningTiming.idleRunningBatchCount > 0
                        ? `${runningTiming.idleRunningBatchCount} running batch(es) with no in-flight video (between jurisdictions or waiting).`
                        : 'No in-flight video with a start time'
                  }
                />
                <SummaryCard
                  label="Videos remaining"
                  value={
                    remainingVideos != null ? formatCompactNumber(remainingVideos) : '—'
                  }
                  title={metricCountTitle(remainingVideos, 'Videos remaining')}
                />
              </>
            ) : null}
            <SummaryCard
              label="Jurisdictions done"
              value={formatCompactNumber(data.totals.processed_jurisdictions)}
              title={metricCountTitle(data.totals.processed_jurisdictions, 'Jurisdictions done')}
            />
            <SummaryCard
              label="Jurisdictions failed"
              value={formatCompactNumber(data.totals.failed_jurisdictions)}
              title={metricCountTitle(data.totals.failed_jurisdictions, 'Jurisdictions failed')}
            />
            <SummaryCard
              label="Jurisdictions remaining"
              value={formatCompactNumber(data.totals.remaining_jurisdictions)}
              title={metricCountTitle(
                data.totals.remaining_jurisdictions,
                'Jurisdictions remaining',
              )}
            />
            <SummaryCard
              label="Videos OK"
              value={formatCompactNumber(data.totals.videos_ok)}
              title={metricCountTitle(data.totals.videos_ok, 'Videos OK')}
            />
            <SummaryCard
              label="Videos failed"
              value={formatCompactNumber(data.totals.videos_fail)}
              title={metricCountTitle(data.totals.videos_fail, 'Videos failed')}
              emphasis={data.totals.videos_fail > 0 ? 'danger' : 'default'}
              active={showFailedVideos}
              onClick={
                data.totals.videos_fail > 0
                  ? () =>
                      setShowFailedVideos(!showFailedVideos, {
                        allBatches: !showFailedVideos,
                      })
                  : undefined
              }
            />
            <SummaryCard
              label="Videos attempted"
              value={formatCompactNumber(data.totals.videos_attempted ?? 0)}
              title={
                metricCountTitle(data.totals.videos_attempted, 'Videos attempted') ??
                'Caption fetch outcomes this batch (ok + fail + tombstoned + empty + rate limit)'
              }
            />
            <SummaryCard
              label="Transcripts"
              value={formatCompactNumber(data.totals.files_transcripts_disk ?? 0)}
              title={
                metricCountTitle(data.totals.files_transcripts_disk, 'Transcripts') ??
                'Distinct videos with a downloaded transcript (bronze transcript_download_at, all time) — the denominator for analysis/report progress'
              }
            />
            <SummaryCard
              label="Transcript hours"
              value={formatCompactHours(data.totals.transcript_hours ?? 0)}
              title={
                metricCountTitle(data.totals.transcript_hours, 'Transcript hours') ??
                'Sum of catalog duration_minutes for batch OK videos (from per-video rows or bronze since batch start).'
              }
            />
            <SummaryCard
              label="Bronze download rows"
              value={formatCompactNumber(data.totals.bronze_download_rows ?? 0)}
              title={
                metricCountTitle(data.totals.bronze_download_rows, 'Bronze download rows') ??
                'bronze_event_youtube rows with transcript_download_at (all time)'
              }
            />
            <SummaryCard
              label="Analyses"
              value={formatCompactNumber(data.totals.files_analysis)}
              title={
                metricCountTitle(data.totals.files_analysis, 'Analyses') ??
                'Videos with an AI analysis (bronze policy_analysis_at, all time, live)'
              }
            />
            <SummaryCard
              label="Reports"
              value={formatCompactNumber(data.totals.files_reports)}
              title={
                metricCountTitle(data.totals.files_reports, 'Reports') ??
                'Videos with a generated report (bronze policy_report_at, all time, live)'
              }
            />
            <SummaryCard
              label="Analysis light %"
              value={
                data.totals.files_transcripts_disk > 0
                  ? `${Math.round((data.totals.files_analysis / data.totals.files_transcripts_disk) * 100)}%`
                  : '—'
              }
              title={`${formatCompactNumber(data.totals.files_analysis)} of ${formatCompactNumber(
                data.totals.files_transcripts_disk ?? 0,
              )} transcripts have a light-tier analysis stamp (policy_analysis_at). Pre-split deep Part 1 rows are reclassified onto full stamps (#766).`}
            />
            <SummaryCard
              label="Reports light %"
              value={
                data.totals.files_transcripts_disk > 0
                  ? `${Math.round((data.totals.files_reports / data.totals.files_transcripts_disk) * 100)}%`
                  : '—'
              }
              title={`${formatCompactNumber(data.totals.files_reports)} of ${formatCompactNumber(
                data.totals.files_transcripts_disk ?? 0,
              )} transcripts have a light-tier report stamp (policy_report_at; same denominator as Analysis light %).`}
            />
            <SummaryCard
              label="Analysis (24h)"
              value={formatCompactNumber(data.totals.files_analysis_recent ?? 0)}
              title={
                metricCountTitle(data.totals.files_analysis_recent, 'AI analyses') ??
                'AI summary analyses written in the last 24 hours (by file mtime)'
              }
            />
            <SummaryCard
              label="Reports (24h)"
              value={formatCompactNumber(data.totals.files_reports_recent ?? 0)}
              title={
                metricCountTitle(data.totals.files_reports_recent, 'Reports') ??
                'Reports generated in the last 24 hours (by file mtime)'
              }
            />
            </div>
          </details>

          {showFailedVideos && !effectiveJurisdictionId && (
            <FailedVideosPanel
              rows={allFailedVideoRows}
              scopeLabel={failedScopeLabel}
              subtitle={
                failedVideosFetching
                  ? 'loading…'
                  : failedVideosSubtitle
              }
              onClose={() => setShowFailedVideos(false)}
              onSelectJurisdiction={(bid, jid) => {
                setShowFailedVideos(true, { batchId: bid, jurisdictionId: jid })
              }}
            />
          )}

          <div className="grid min-h-0 gap-4 lg:grid-cols-[minmax(220px,280px)_1fr]">
            {videosLoading || stateJurisdictionsFetching ? (
              <p className="text-xs text-slate-500 lg:col-span-2">
                {videosLoading
                  ? 'Loading per-video details…'
                  : 'Loading jurisdictions for selected state…'}
              </p>
            ) : null}
            <aside className="rounded-lg border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-100 px-3 py-2 text-sm font-semibold text-slate-800">
                Batches
              </div>
              <ul className="max-h-[min(520px,60vh)] overflow-auto p-2">
                {data.batches.length === 0 ? (
                  <li className="px-2 py-4 text-center text-xs text-slate-500">No batches yet</li>
                ) : (
                  data.batches.map((b) => {
                    const sum = b.summary || {}
                    const t = Number(sum.total_jurisdictions) || 0
                    const p = Number(sum.processed_jurisdictions) || 0
                    const pct = t > 0 ? Math.round((100 * p) / t) : 0
                    const active = selectedBatch?.batch_id === b.batch_id
                    return (
                      <li key={b.batch_id} className="mb-1">
                        <button
                          type="button"
                          onClick={() => setBatch(b.batch_id)}
                          className={`w-full rounded-md border px-2 py-2 text-left text-sm transition-colors ${
                            active
                              ? 'border-teal-500 bg-teal-50'
                              : 'border-transparent hover:bg-slate-50'
                          }`}
                        >
                          <div className="flex items-center gap-1">
                            <span className="font-medium text-slate-900">{b.step}</span>
                            <span
                              className={`rounded px-1 text-[10px] font-medium ${statusBadgeClass(b.status)}`}
                            >
                              {b.status}
                            </span>
                          </div>
                          <div className="mt-0.5 truncate font-mono text-[10px] text-slate-500">
                            {b.batch_id}
                          </div>
                          <div className="mt-1 text-[11px] text-slate-600">
                            {p}/{t || '?'} jurisdictions · {pct}%
                          </div>
                        </button>
                      </li>
                    )
                  })
                )}
              </ul>
            </aside>

            <section className="min-w-0">
              {selectedBatchForPanel ? (
                <BatchDetailPanel
                  batch={selectedBatchForPanel}
                  selectedJurisdictionId={effectiveJurisdictionId}
                  onSelectJurisdiction={setJurisdiction}
                  stateFilter={effectiveStateFilter}
                  onStateFilterChange={setStateFilter}
                  showFailedVideos={showFailedVideos}
                  onToggleFailedVideos={() =>
                      setShowFailedVideos(!showFailedVideos, {
                        batchId: selectedBatchForPanel.batch_id,
                        allBatches: false,
                      })
                    }
                  onShowFailedForJurisdiction={(jid) => {
                    setShowFailedVideos(true, {
                      batchId: selectedBatchForPanel.batch_id,
                      jurisdictionId: jid,
                    })
                    requestAnimationFrame(() => {
                      document
                        .getElementById('batch-jurisdiction-drilldown')
                        ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
                    })
                  }}
                />
              ) : (
                <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
                  Select a batch
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  )
}
