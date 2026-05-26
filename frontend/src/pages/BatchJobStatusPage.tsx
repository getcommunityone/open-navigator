import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  batchJobsStreamUrl,
  batchJobsFetchErrorMessage,
  fetchBatchJobsDashboard,
  type BatchJob,
  type BatchJurisdictionRun,
  type BatchJobsDashboardPayload,
  type BatchVideoResult,
} from '../api/batchJobs'
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
  onClose,
  onSelectJurisdiction,
}: {
  rows: FailedVideoRow[]
  scopeLabel: string
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
            <th className="px-3 py-2 font-medium">Updated</th>
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
                    <span className="text-slate-500">nothing to do</span>
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
                <td className="px-3 py-2 text-xs text-slate-600">
                  disk T {fc.transcripts_disk ?? fc.transcripts ?? 0} · A{' '}
                  {fc.analysis_disk ?? fc.analysis ?? 0} · R {fc.reports_disk ?? fc.reports ?? 0}
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
    const fromRows = jurisdictionStateCodes(batch.jurisdictions)
    const fromCfg = Array.isArray(cfg.states)
      ? (cfg.states as string[]).map((s) => String(s).toUpperCase().trim()).filter(Boolean)
      : []
    return [...new Set([...fromCfg, ...fromRows])].sort()
  }, [batch.jurisdictions, cfg.states])
  const sortedJurisdictions = useMemo(
    () => sortJurisdictions(batch.jurisdictions),
    [batch.jurisdictions],
  )
  const displayedJurisdictions = useMemo(
    () => filterJurisdictionsByState(sortedJurisdictions, stateFilter),
    [sortedJurisdictions, stateFilter],
  )

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
            <span className="ml-1 font-normal text-slate-500">
              {stateFilter ? (
                <>
                  ({displayedJurisdictions.length} in {stateFilter}
                  {total > 0 ? ` · ${total} total` : ''})
                </>
              ) : (
                <>({sortedJurisdictions.length}{total > 0 ? ` · ${total} total` : ''})</>
              )}
            </span>
          </h3>
          <div className="flex items-center gap-2">
            <label
              htmlFor="batch-jobs-state-filter"
              className="text-[10px] font-medium uppercase tracking-wide text-slate-500"
            >
              State
            </label>
            <select
              id="batch-jobs-state-filter"
              value={stateFilter}
              onChange={(e) => onStateFilterChange(e.target.value)}
              className="min-w-[7rem] rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-800 shadow-sm"
            >
              <option value="">All states</option>
              {stateCodes.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </div>
        </div>
        <JurisdictionTable
          jurisdictions={displayedJurisdictions}
          selectedId={selectedJurisdictionId}
          onSelect={(id) => onSelectJurisdiction(id)}
          onShowFailedVideos={onShowFailedForJurisdiction}
          emptyMessage={
            sortedJurisdictions.length > 0 && stateFilter
              ? `No jurisdictions in ${stateFilter} for this batch.`
              : undefined
          }
        />
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

export default function BatchJobStatusPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const batchId = searchParams.get('batch') ?? ''
  const jurisdictionId = searchParams.get('jurisdiction') ?? ''
  const stateFilter = (searchParams.get('state') ?? '').toUpperCase()
  const showFailedVideos = searchParams.get('view') === 'failed-videos'
  const queryClient = useQueryClient()
  const [streamLive, setStreamLive] = useState(false)

  const { data, isPending, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['batch-jobs-dashboard'],
    queryFn: () => fetchBatchJobsDashboard(false),
    staleTime: Infinity,
    refetchOnWindowFocus: true,
    retry: 1,
  })

  useEffect(() => {
    const url = batchJobsStreamUrl()
    const es = new EventSource(url)

    es.onopen = () => setStreamLive(true)
    es.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data) as BatchJobsDashboardPayload
        queryClient.setQueryData(['batch-jobs-dashboard'], payload)
      } catch {
        /* ignore malformed events */
      }
    }
    es.onerror = () => {
      setStreamLive(false)
      es.close()
    }

    return () => {
      setStreamLive(false)
      es.close()
    }
  }, [queryClient])

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
    (open: boolean, opts?: { batchId?: string; jurisdictionId?: string }) => {
      const next = new URLSearchParams(searchParams)
      if (opts?.batchId) next.set('batch', opts.batchId)
      if (opts?.jurisdictionId) next.set('jurisdiction', opts.jurisdictionId)
      else if (!open) next.delete('jurisdiction')
      if (open) next.set('view', 'failed-videos')
      else next.delete('view')
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const visibleJurisdictions = useMemo(() => {
    if (!selectedBatch) return []
    return filterJurisdictionsByState(
      sortJurisdictions(selectedBatch.jurisdictions),
      stateFilter,
    )
  }, [selectedBatch, stateFilter])

  const effectiveJurisdictionId =
    jurisdictionId &&
    visibleJurisdictions.some((j) => j.jurisdiction_id === jurisdictionId)
      ? jurisdictionId
      : null

  const planStateCodes = useMemo(() => {
    if (!selectedBatch) return [] as string[]
    const fromRows = jurisdictionStateCodes(selectedBatch.jurisdictions)
    const fromCfg = Array.isArray(selectedBatch.config?.states)
      ? (selectedBatch.config.states as string[])
          .map((s) => String(s).toUpperCase().trim())
          .filter(Boolean)
      : []
    return [...new Set([...fromCfg, ...fromRows])].sort()
  }, [selectedBatch])

  const effectiveStateFilter = useMemo(() => {
    if (!selectedBatch || !stateFilter) return ''
    return planStateCodes.includes(stateFilter) ? stateFilter : ''
  }, [selectedBatch, stateFilter, planStateCodes])

  const allFailedVideoRows = useMemo(
    () =>
      collectFailedVideos(data?.batches ?? [], {
        batchId: selectedBatch?.batch_id,
        jurisdictionId: effectiveJurisdictionId || undefined,
      }),
    [data?.batches, selectedBatch?.batch_id, effectiveJurisdictionId],
  )

  const failedScopeLabel = useMemo(() => {
    if (effectiveJurisdictionId && selectedBatch) {
      const j = selectedBatch.jurisdictions.find(
        (x) => x.jurisdiction_id === effectiveJurisdictionId,
      )
      return `${selectedBatch.step} · ${j?.jurisdiction_name || effectiveJurisdictionId}`
    }
    if (selectedBatch) return `Batch ${selectedBatch.step} (${selectedBatch.batch_id})`
    return 'All batches'
  }, [effectiveJurisdictionId, selectedBatch])

  const lastActivityIso = useMemo(() => {
    const fromApi = data?.last_activity_at?.trim()
    if (fromApi) return fromApi
    return latestDashboardActivityIso(data?.batches ?? [])
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

  return (
    <div className="min-h-0 w-full space-y-4">
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
          Loading batch status…
          <p className="mt-2 text-xs text-slate-400">
            First load can take up to a minute while batch rows are read from Postgres.
          </p>
        </div>
      )}

      {isFetching && data && (
        <p className="text-xs text-slate-500">Refreshing batch metrics…</p>
      )}

      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          Could not load batch jobs: {batchJobsFetchErrorMessage(error)}
          <p className="mt-2 text-xs text-red-700">
            Start or restart the API:{' '}
            <code className="rounded bg-red-100 px-1">
              uvicorn api.main:app --reload --port 8000
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
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
            {lastActivityIso && lastUpdateAgo ? (
              <SummaryCard
                label="Last update"
                value={lastUpdateAgo}
                title={
                  lastUpdateAbsolute?.title
                    ? `${lastUpdateAbsolute.title}${data.source === 'database' ? ' · pipeline progress from database' : ''}`
                    : undefined
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
                  ? () => setShowFailedVideos(!showFailedVideos)
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
              label="Transcripts on disk"
              value={formatCompactNumber(data.totals.files_transcripts_disk ?? 0)}
              title={
                metricCountTitle(data.totals.files_transcripts_disk, 'Transcript files') ??
                'JSON files under 01_transcripts/ in the policy cache (all time, per jurisdiction folder)'
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
                'bronze_events_youtube rows with transcript_download_at (all time)'
              }
            />
            <SummaryCard
              label="Analysis on disk"
              value={formatCompactNumber(data.totals.files_analysis)}
              title={metricCountTitle(data.totals.files_analysis, 'Analysis files')}
            />
            <SummaryCard
              label="Reports on disk"
              value={formatCompactNumber(data.totals.files_reports)}
              title={metricCountTitle(data.totals.files_reports, 'Report files')}
            />
          </div>

          {showFailedVideos && !effectiveJurisdictionId && (
            <FailedVideosPanel
              rows={allFailedVideoRows}
              scopeLabel={failedScopeLabel}
              onClose={() => setShowFailedVideos(false)}
              onSelectJurisdiction={(bid, jid) => {
                setShowFailedVideos(true, { batchId: bid, jurisdictionId: jid })
              }}
            />
          )}

          <div className="grid min-h-0 gap-4 lg:grid-cols-[minmax(220px,280px)_1fr]">
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
              {selectedBatch ? (
                <BatchDetailPanel
                  batch={selectedBatch}
                  selectedJurisdictionId={effectiveJurisdictionId}
                  onSelectJurisdiction={setJurisdiction}
                  stateFilter={effectiveStateFilter}
                  onStateFilterChange={setStateFilter}
                  showFailedVideos={showFailedVideos}
                  onToggleFailedVideos={() =>
                    setShowFailedVideos(!showFailedVideos, {
                      batchId: selectedBatch.batch_id,
                    })
                  }
                  onShowFailedForJurisdiction={(jid) => {
                    setShowFailedVideos(true, {
                      batchId: selectedBatch.batch_id,
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
