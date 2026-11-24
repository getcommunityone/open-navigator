import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { fetchStepResult, type StepResultReason } from '../api/deployments'

const PAGE_SIZE = 50

/** The counts a step row shows, in reading order. Keys a step did not record are left out. */
const COUNT_LABELS: Array<[key: string, label: string, tone: 'plain' | 'good' | 'warn' | 'bad']> = [
  ['read', 'read', 'plain'],
  ['models', 'models', 'plain'],
  ['loaded', 'loaded', 'good'],
  ['success', 'built', 'good'],
  ['skipped', 'skipped', 'warn'],
  ['errors', 'errors', 'bad'],
  ['error', 'failed', 'bad'],
]

const TONE: Record<string, string> = {
  plain: 'border-slate-200 bg-white text-slate-700',
  good: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  warn: 'border-amber-200 bg-amber-50 text-amber-800',
  bad: 'border-red-200 bg-red-50 text-red-800',
}

/** Compact count chips for a step header. Renders nothing when the step recorded no counts. */
export function StepCounts({ counts }: { counts?: Record<string, number> | null }) {
  if (!counts) return null
  const shown = COUNT_LABELS.filter(([key]) => typeof counts[key] === 'number')
  if (shown.length === 0) return null
  return (
    <span className="flex flex-wrap items-center gap-1">
      {shown.map(([key, label, tone]) => {
        const n = counts[key] as number
        // A zero is a real, measured zero here; quiet it so the non-zero problems stand out.
        const cls = n === 0 && (tone === 'warn' || tone === 'bad') ? TONE.plain : TONE[tone]
        const text = n === 1 && label.endsWith('s') ? label.slice(0, -1) : label
        return (
          <span key={key} className={`rounded-full border px-2 py-0.5 text-[11px] font-medium tabular-nums ${cls}`}>
            {n.toLocaleString()} {text}
          </span>
        )
      })}
    </span>
  )
}

function ReasonButton({ r, active, onClick }: { r: StepResultReason; active: boolean; onClick: () => void }) {
  const bad = r.outcome === 'error'
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      title={r.advice}
      className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-left text-xs ${
        active ? 'border-slate-800 bg-slate-800 text-white' : bad ? 'border-red-200 bg-red-50 text-red-900' : 'border-slate-200 bg-white text-slate-800'
      }`}
    >
      <span className="font-semibold tabular-nums">{r.count.toLocaleString()}</span>
      <span>{r.label}</span>
      <span className={`rounded px-1 text-[10px] uppercase tracking-wide ${active ? 'bg-white/20' : bad ? 'bg-red-100' : 'bg-slate-100 text-slate-500'}`}>
        {bad ? 'error' : 'skipped'}
      </span>
    </button>
  )
}

/**
 * Drill-down for one step of a Load run (#823): every reason with its count and what to do, then a
 * searchable, paged list of the items that were not loaded. Reads the step's result file through the API.
 */
export default function StepResultPanel({
  jobId,
  step,
  live,
  recorded,
}: {
  jobId: string
  step: string
  live: boolean
  /** True once the step has recorded counts; part of the query key so the panel refetches when they land. */
  recorded: boolean
}) {
  const [reason, setReason] = useState<string>('')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['deployment-step-result', jobId, step, recorded, reason, q, page],
    queryFn: () => fetchStepResult(jobId, step, { reason: reason || undefined, q: q.trim() || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    refetchInterval: live ? 5_000 : false,
    // Keep the last page on screen while a new filter loads, so the search box is never unmounted mid-typing.
    placeholderData: keepPreviousData,
  })

  if (isLoading && !data) return <p className="text-xs text-slate-400">Loading counts…</p>
  if (isError) {
    return (
      <p className="text-xs text-red-700" role="status">
        Couldn&apos;t load the counts for this step. {(error as Error | undefined)?.message ?? ''}
      </p>
    )
  }
  if (!data || !data.available) {
    return (
      <p className="text-xs text-slate-500" role="status">
        No counts recorded for this run{live ? ' yet — they are written when the step finishes' : ' (it ran before counts were recorded, or was a dry run)'}.
      </p>
    )
  }

  const active = data.reasons.find((r) => r.reason === reason)
  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE))
  const pick = (next: string) => {
    setReason(next)
    setPage(0)
  }

  return (
    <div className="space-y-2">
      {data.dry_run && <p className="text-[11px] text-amber-800">Dry run: nothing was written to the database.</p>}
      {data.reasons.length === 0 ? (
        <p className="text-xs text-emerald-800" role="status">
          Nothing was skipped and nothing failed in this step.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by reason">
            <button
              type="button"
              onClick={() => pick('')}
              aria-pressed={reason === ''}
              className={`rounded-md border px-2.5 py-1.5 text-xs ${reason === '' ? 'border-slate-800 bg-slate-800 text-white' : 'border-slate-200 bg-white text-slate-800'}`}
            >
              All reasons
            </button>
            {data.reasons.map((r) => (
              <ReasonButton key={`${r.outcome}:${r.reason}`} r={r} active={reason === r.reason} onClick={() => pick(reason === r.reason ? '' : r.reason)} />
            ))}
          </div>
          {active?.advice && (
            <p className="rounded border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700">
              <span className="font-semibold">{active.label}:</span> {active.advice}
            </p>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <input
              type="search"
              value={q}
              onChange={(e) => {
                setQ(e.target.value)
                setPage(0)
              }}
              placeholder="Search file, video id or error text"
              aria-label="Search items"
              className="w-72 max-w-full rounded border border-slate-300 px-2 py-1 text-xs"
            />
            <span className="text-[11px] text-slate-600">
              {data.total.toLocaleString()} {data.total === 1 ? 'item' : 'items'}
              {reason ? ` · ${active?.label ?? reason}` : ' · all reasons'}
              {q.trim() ? ` · matching “${q.trim()}”` : ''}
            </span>
          </div>
          {data.rows.length === 0 ? (
            <p className="text-xs text-slate-500">No items match.</p>
          ) : (
            <div className="max-h-96 overflow-auto rounded border border-slate-200 bg-white">
              <table className="w-full border-collapse text-left text-[11px]">
                <thead className="sticky top-0 bg-slate-100 text-slate-600">
                  <tr>
                    <th className="p-1.5">Outcome</th>
                    <th className="p-1.5">Reason</th>
                    <th className="p-1.5">Item</th>
                    <th className="p-1.5">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row, i) => (
                    <tr key={`${row.file}-${i}`} className="border-t border-slate-100 align-top">
                      <td className={`p-1.5 font-medium ${row.outcome === 'error' ? 'text-red-700' : 'text-amber-700'}`}>{row.outcome}</td>
                      <td className="p-1.5">{data.reasons.find((r) => r.reason === row.reason)?.label ?? row.reason}</td>
                      <td className="p-1.5">
                        <span className="break-all font-mono">{row.file}</span>
                        {row.video_id && (
                          <a
                            className="ml-1.5 text-teal-800 underline"
                            href={`https://www.youtube.com/watch?v=${encodeURIComponent(row.video_id)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            video
                          </a>
                        )}
                        {row.tier && <span className="ml-1.5 text-slate-400">{row.tier}</span>}
                      </td>
                      <td className="break-words p-1.5 text-slate-700">{row.detail ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {pages > 1 && (
            <div className="flex items-center gap-2 text-[11px] text-slate-600">
              <button type="button" className="rounded border px-2 py-0.5 disabled:opacity-40" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                Previous
              </button>
              <span>
                Page {page + 1} of {pages}
              </span>
              <button type="button" className="rounded border px-2 py-0.5 disabled:opacity-40" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
