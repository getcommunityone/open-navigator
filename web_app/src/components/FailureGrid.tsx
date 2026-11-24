import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  fetchFailureGrid,
  type FailureGridRow,
  type FailureGridStage,
} from '../api/batchJobs'

// #800: sortable, pageable grid of failed items for any stage. Sort, page, size and filters live in the
// URL (?q, group, sort, dir, page, size) so a refresh or shared link shows the same rows.

const SIZES = [25, 50, 100]
const GROUPS: { key: string; label: string }[] = [
  { key: '', label: 'All reasons' },
  { key: 'bot_block', label: 'Bot check' },
  { key: 'rate_limit', label: 'Rate limited' },
  { key: 'network', label: 'Network / VPN' },
  { key: 'not_yet_available', label: 'Not yet available' },
  { key: 'no_captions', label: 'No captions' },
  { key: 'unavailable', label: 'Private / removed' },
  { key: 'unknown', label: 'No reason recorded' },
  { key: 'other', label: 'Other' },
]

const watchUrl = (id: string) => `https://www.youtube.com/watch?v=${id}`
const dash = (v: string) => (v ? v : '—')
const fmtDate = (iso: string) => (iso ? iso.slice(0, 10) : '—')
const fmtWhen = (iso: string) => (iso ? iso.replace('T', ' ').slice(0, 16) : '—')

function Copy({ text, label }: { text: string; label: string }) {
  return (
    <button
      type="button"
      onClick={() => void navigator.clipboard?.writeText(text)}
      className="ml-2 rounded border border-slate-200 px-1.5 py-0.5 text-[11px] text-slate-600 hover:bg-slate-100"
      title={`Copy ${label}`}
    >
      Copy
    </button>
  )
}

function Detail({ row, where }: { row: FailureGridRow; where: string }) {
  const ids: [string, string][] = [
    ['Video id', row.video_id],
    ['Event id', row.event_id],
    ['Jurisdiction id', row.jurisdiction_id],
    ['Channel id', row.channel_id],
  ]
  return (
    <div className="space-y-2 border-t border-slate-100 bg-slate-50 px-4 py-3 text-xs text-slate-700">
      <div>
        <div className="font-semibold text-slate-900">Full error</div>
        <pre className="mt-1 whitespace-pre-wrap break-words rounded bg-white p-2 text-[11px]">
          {row.error || '—'}
        </pre>
        {row.error ? <Copy text={row.error} label="error" /> : null}
      </div>
      <div>
        <span className="font-semibold text-slate-900">{row.group_label}.</span> {row.advice}{' '}
        {row.retryable ? '(Retryable: use Retry on the reasons above, then Backfill.)' : '(Not retryable.)'}
      </div>
      <div>
        <span className="font-semibold text-slate-900">Where to look:</span> {where}
      </div>
      <dl className="grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
        {ids.map(([k, v]) => (
          <div key={k} className="flex items-center">
            <dt className="w-32 shrink-0 text-slate-500">{k}</dt>
            <dd className="min-w-0 break-all font-mono">{dash(v)}</dd>
            {v ? <Copy text={v} label={k} /> : null}
          </div>
        ))}
      </dl>
      <div className="flex gap-4">
        {row.video_id ? (
          <a href={watchUrl(row.video_id)} target="_blank" rel="noreferrer" className="font-medium text-teal-700 hover:underline">
            ▶ Watch on YouTube
          </a>
        ) : null}
        {row.channel_url ? (
          <a href={row.channel_url} target="_blank" rel="noreferrer" className="font-medium text-teal-700 hover:underline">
            Channel
          </a>
        ) : null}
      </div>
    </div>
  )
}

export default function FailureGrid({
  stage,
  cohort,
  state,
}: {
  stage: FailureGridStage
  cohort: string
  state: string
}) {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const group = params.get('group') || ''
  const sort = params.get('sort') || 'last_updated'
  const dir = params.get('dir') === 'asc' ? 'asc' : 'desc'
  const size = SIZES.includes(Number(params.get('size'))) ? Number(params.get('size')) : 50
  const page = Math.max(1, Number(params.get('page')) || 1)
  const [qDraft, setQDraft] = useState(q)
  const [openId, setOpenId] = useState<string | null>(null)
  useEffect(() => setQDraft(q), [q])

  const set = (patch: Record<string, string | null>, resetPage = true) => {
    const next = new URLSearchParams(params)
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === '') next.delete(k)
      else next.set(k, v)
    }
    if (resetPage) next.delete('page')
    setParams(next, { replace: true })
  }

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ['batch-failure-grid', stage, cohort, state, q, group, sort, dir, size, page],
    queryFn: () =>
      fetchFailureGrid({ stage, cohort, state, q, group, sort, dir, limit: size, offset: (page - 1) * size }),
    placeholderData: (prev) => prev,
  })

  const total = data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / size))
  const from = total === 0 ? 0 : (page - 1) * size + 1
  const to = Math.min(total, page * size)
  const go = (n: number) => set({ page: n <= 1 ? null : String(Math.min(n, pages)) }, false)

  const header = (key: string, label: string, sortable: boolean) => {
    const active = sort === key
    if (!sortable) return <div key={key} className="font-medium">{label}</div>
    return (
      <div key={key} className="font-medium" aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'} role="columnheader">
        <button
          type="button"
          onClick={() => set({ sort: key, dir: active && dir === 'asc' ? 'desc' : 'asc' })}
          className="inline-flex items-center gap-1 hover:text-slate-900"
        >
          {label}
          <span className="text-[10px]">{active ? (dir === 'asc' ? '▲' : '▼') : '↕'}</span>
        </button>
      </div>
    )
  }

  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold text-slate-900">All failed items</h2>
      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          set({ q: qDraft.trim() })
        }}
      >
        <input
          value={qDraft}
          onChange={(e) => setQDraft(e.target.value)}
          placeholder="Search title, video id, jurisdiction, error"
          className="min-w-[16rem] flex-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
          aria-label="Search failed items"
        />
        <button type="submit" className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-sm hover:bg-slate-50">
          Search
        </button>
        <select
          value={group}
          onChange={(e) => set({ group: e.target.value })}
          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          aria-label="Reason group"
        >
          {GROUPS.map((g) => (
            <option key={g.key} value={g.key}>
              {g.label}
            </option>
          ))}
        </select>
        {q || group ? (
          <button type="button" onClick={() => set({ q: null, group: null })} className="text-sm text-teal-700 hover:underline">
            Clear filters
          </button>
        ) : null}
      </form>

      <div className="text-sm text-slate-700">
        <span className="font-semibold tabular-nums text-red-700">{total.toLocaleString()}</span> failed item
        {total === 1 ? '' : 's'}
        {q ? <> matching “{q}”</> : null}
        {group ? <> in “{GROUPS.find((g) => g.key === group)?.label ?? group}”</> : null}
        {isFetching ? <span className="ml-2 text-xs text-slate-400">updating…</span> : null}
      </div>

      {isLoading ? <p className="text-sm text-slate-500">Loading failed items…</p> : null}
      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          Failed items are unavailable: {(error as Error).message}
        </div>
      ) : null}
      {data && total === 0 ? (
        <div className="rounded-md border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-600">
          {q || group ? 'No failed items match these filters.' : 'No failed items recorded for this scope.'}
        </div>
      ) : null}

      {data && total > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="min-w-[72rem] text-xs" role="table">
            <div className="grid min-w-[72rem] grid-cols-[1.2fr_2fr_1.5fr_0.5fr_1fr_1fr_1fr_3fr_1.3fr_1fr] gap-3 px-3 bg-slate-50 py-2 text-slate-600" role="row">
              {data.columns.map((c) => header(c.key, c.label, c.sortable))}
            </div>
            {data.rows.map((r) => {
              const id = `${r.video_id}|${r.event_id}`
              const open = openId === id
              return (
                <div key={id} className="border-t border-slate-100" role="row">
                  <button
                    type="button"
                    onClick={() => setOpenId(open ? null : id)}
                    aria-expanded={open}
                    className="grid min-w-[72rem] grid-cols-[1.2fr_2fr_1.5fr_0.5fr_1fr_1fr_1fr_3fr_1.3fr_1fr] gap-3 px-3 w-full py-2 text-left hover:bg-slate-50"
                  >
                    <span className="font-mono">{r.video_id}</span>
                    <span className="break-words">{dash(r.title)}</span>
                    <span className="break-words">{dash(r.jurisdiction_name)}</span>
                    <span>{dash(r.state_code)}</span>
                    <span className="break-all font-mono">{dash(r.channel_id)}</span>
                    <span>{fmtDate(r.event_date)}</span>
                    <span>{dash(r.meeting_type)}</span>
                    <span className="line-clamp-2 break-words">{dash(r.error)}</span>
                    <span>{r.group_label}</span>
                    <span>{fmtWhen(r.last_updated)}</span>
                  </button>
                  {open ? <Detail row={r} where={data.where_to_look} /> : null}
                </div>
              )
            })}
          </div>
        </div>
      ) : null}

      {total > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-700">
          <div className="tabular-nums">
            {from.toLocaleString()}–{to.toLocaleString()} of {total.toLocaleString()}
          </div>
          <div className="flex items-center gap-1">
            <button type="button" disabled={page <= 1} onClick={() => go(1)} className="rounded border px-2 py-1 disabled:opacity-40">« First</button>
            <button type="button" disabled={page <= 1} onClick={() => go(page - 1)} className="rounded border px-2 py-1 disabled:opacity-40">‹ Previous</button>
            <span className="px-2 tabular-nums">Page {page} of {pages}</span>
            <button type="button" disabled={page >= pages} onClick={() => go(page + 1)} className="rounded border px-2 py-1 disabled:opacity-40">Next ›</button>
            <button type="button" disabled={page >= pages} onClick={() => go(pages)} className="rounded border px-2 py-1 disabled:opacity-40">Last »</button>
          </div>
          <label className="flex items-center gap-1">
            Rows
            <select value={size} onChange={(e) => set({ size: e.target.value === '50' ? null : e.target.value })} className="rounded border border-slate-300 px-1 py-0.5">
              {SIZES.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
        </div>
      ) : null}
    </section>
  )
}
