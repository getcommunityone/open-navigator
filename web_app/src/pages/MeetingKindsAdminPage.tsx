/**
 * /admin/meeting-kinds — troubleshoot Jev ``not_government`` screens (#668).
 * Sort by probability; override false labels without re-running Jev.
 */
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteMeetingKindOverride,
  fetchMeetingKindReviews,
  putMeetingKindOverride,
  type MeetingKindSort,
  type MeetingKindSource,
  type OverrideKind,
} from '../api/meetingKindReviews'

const QUERY_KEY = ['admin', 'meeting-kind-reviews'] as const

const OVERRIDE_OPTIONS: { value: OverrideKind; label: string }[] = [
  { value: 'government_meeting', label: 'government_meeting (keep)' },
  { value: 'town_hall', label: 'town_hall (keep)' },
  { value: 'government_other', label: 'government_other' },
  { value: 'not_government', label: 'not_government' },
]

function fmtP(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(3)
}

function errorText(err: unknown): string {
  const e = err as { message?: string; response?: { data?: { detail?: unknown } } } | undefined
  const detail = e?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return e?.message ?? 'Something went wrong.'
}

export default function MeetingKindsAdminPage() {
  const qc = useQueryClient()
  const [source, setSource] = useState<MeetingKindSource>('transcript')
  const [kind, setKind] = useState('not_government')
  const [sort, setSort] = useState<MeetingKindSort>('not_government_p')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')
  const [state, setState] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [draftOverride, setDraftOverride] = useState<Record<string, OverrideKind>>({})
  const [draftNote, setDraftNote] = useState<Record<string, string>>({})

  const queryParams = useMemo(
    () => ({
      source,
      kind,
      sort,
      order,
      state: state.trim().toUpperCase() || undefined,
      limit: 100,
    }),
    [source, kind, sort, order, state],
  )

  const { data, isLoading, isError, error } = useQuery({
    queryKey: [...QUERY_KEY, queryParams],
    queryFn: () => fetchMeetingKindReviews(queryParams),
  })

  const refresh = () => qc.invalidateQueries({ queryKey: QUERY_KEY })

  const saveOverride = useMutation({
    mutationFn: ({
      videoId,
      override_kind,
      note,
    }: {
      videoId: string
      override_kind: OverrideKind
      note?: string
    }) => putMeetingKindOverride(videoId, { override_kind, note: note || null }),
    onSuccess: (_d, vars) => {
      setMessage(`Override saved for ${vars.videoId} → ${vars.override_kind}`)
      refresh()
    },
    onError: (err) => setMessage(errorText(err)),
  })

  const clearOverride = useMutation({
    mutationFn: (videoId: string) => deleteMeetingKindOverride(videoId),
    onSuccess: (_d, videoId) => {
      setMessage(`Override cleared for ${videoId}`)
      refresh()
    },
    onError: (err) => setMessage(errorText(err)),
  })

  const toggleSort = (field: MeetingKindSort) => {
    if (sort === field) {
      setOrder((o) => (o === 'desc' ? 'asc' : 'desc'))
    } else {
      setSort(field)
      setOrder('desc')
    }
  }

  const sortMark = (field: MeetingKindSort) =>
    sort === field ? (order === 'desc' ? ' ↓' : ' ↑') : ''

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden rounded-lg border border-slate-300/80 bg-white p-3 shadow-sm sm:p-4">
      <div className="shrink-0 space-y-2">
        <h2 className="text-base font-semibold text-slate-900">Meeting kinds</h2>
        <p className="text-xs text-slate-600">
          Review Jev screens labeled <code className="rounded bg-slate-100 px-1">not_government</code>{' '}
          (or another kind). Sort by probability, then override false labels. Keep overrides
          (<code className="rounded bg-slate-100 px-1">government_meeting</code> /{' '}
          <code className="rounded bg-slate-100 px-1">town_hall</code>) are honored by the analysis
          skip gate.
        </p>
        <div className="flex flex-wrap items-end gap-2 text-xs">
          <label className="flex flex-col gap-0.5">
            <span className="font-medium text-slate-700">Source</span>
            <select
              className="rounded border border-slate-300 px-2 py-1.5"
              value={source}
              onChange={(e) => setSource(e.target.value as MeetingKindSource)}
            >
              <option value="transcript">Transcript</option>
              <option value="meta">Metadata</option>
            </select>
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="font-medium text-slate-700">Screen kind</span>
            <select
              className="rounded border border-slate-300 px-2 py-1.5"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              <option value="not_government">not_government</option>
              <option value="government_other">government_other</option>
              <option value="government_meeting">government_meeting</option>
              <option value="town_hall">town_hall</option>
            </select>
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="font-medium text-slate-700">State</span>
            <input
              className="w-16 rounded border border-slate-300 px-2 py-1.5 uppercase"
              value={state}
              onChange={(e) => setState(e.target.value.slice(0, 2))}
              placeholder="AL"
              maxLength={2}
            />
          </label>
        </div>
        {message && (
          <p className="rounded border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs text-slate-800" role="status">
            {message}
          </p>
        )}
        {isError && (
          <p className="text-xs text-rose-700" role="alert">
            {errorText(error)}
          </p>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        {isLoading ? (
          <p className="text-sm text-slate-600">Loading…</p>
        ) : !data?.items.length ? (
          <p className="text-sm text-slate-600">
            No {kind} screens for this source
            {state ? ` in ${state.toUpperCase()}` : ''}. Nothing to show.
          </p>
        ) : (
          <>
            <p className="mb-2 text-[11px] text-slate-600">
              Showing {data.items.length} of {data.total}
            </p>
            <table className="w-full border-collapse text-left text-xs">
              <thead className="sticky top-0 bg-slate-100 text-[11px] uppercase tracking-wide text-slate-600">
                <tr>
                  <th className="border-b border-slate-300 px-2 py-1.5 font-semibold">Title</th>
                  <th className="border-b border-slate-300 px-2 py-1.5 font-semibold">State</th>
                  <th className="border-b border-slate-300 px-2 py-1.5 font-semibold">
                    <button type="button" className="font-semibold hover:underline" onClick={() => toggleSort('not_government_p')}>
                      P(not_gov){sortMark('not_government_p')}
                    </button>
                  </th>
                  <th className="border-b border-slate-300 px-2 py-1.5 font-semibold">
                    <button type="button" className="font-semibold hover:underline" onClick={() => toggleSort('keep_score')}>
                      Keep score{sortMark('keep_score')}
                    </button>
                  </th>
                  <th className="border-b border-slate-300 px-2 py-1.5 font-semibold">Effective</th>
                  <th className="border-b border-slate-300 px-2 py-1.5 font-semibold">Override</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => {
                  const chosen =
                    draftOverride[row.video_id] ??
                    (row.override_kind as OverrideKind | null) ??
                    'government_meeting'
                  return (
                    <tr key={row.video_id} className="border-b border-slate-100 align-top hover:bg-slate-50/80">
                      <td className="px-2 py-2">
                        <a
                          href={row.youtube_url}
                          target="_blank"
                          rel="noreferrer"
                          className="font-medium text-teal-800 hover:underline"
                        >
                          {row.title || row.video_id}
                        </a>
                        <div className="mt-0.5 font-mono text-[10px] text-slate-500">{row.video_id}</div>
                      </td>
                      <td className="px-2 py-2">{row.state_code ?? '—'}</td>
                      <td className="px-2 py-2 font-mono tabular-nums">{fmtP(row.not_government_p)}</td>
                      <td className="px-2 py-2 font-mono tabular-nums">{fmtP(row.keep_score)}</td>
                      <td className="px-2 py-2">
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px]">
                          {row.effective_kind ?? '—'}
                        </span>
                        {row.override_kind && (
                          <div className="mt-0.5 text-[10px] text-amber-800">overridden</div>
                        )}
                      </td>
                      <td className="px-2 py-2">
                        <div className="flex min-w-[12rem] flex-col gap-1">
                          <select
                            className="rounded border border-slate-300 px-1.5 py-1"
                            value={chosen}
                            onChange={(e) =>
                              setDraftOverride((d) => ({
                                ...d,
                                [row.video_id]: e.target.value as OverrideKind,
                              }))
                            }
                          >
                            {OVERRIDE_OPTIONS.map((o) => (
                              <option key={o.value} value={o.value}>
                                {o.label}
                              </option>
                            ))}
                          </select>
                          <input
                            className="rounded border border-slate-300 px-1.5 py-1"
                            placeholder="Note (optional)"
                            value={draftNote[row.video_id] ?? row.override_note ?? ''}
                            onChange={(e) =>
                              setDraftNote((d) => ({ ...d, [row.video_id]: e.target.value }))
                            }
                          />
                          <div className="flex gap-1">
                            <button
                              type="button"
                              className="rounded bg-teal-700 px-2 py-1 text-[11px] font-medium text-white hover:bg-teal-800 disabled:opacity-50"
                              disabled={saveOverride.isPending}
                              onClick={() =>
                                saveOverride.mutate({
                                  videoId: row.video_id,
                                  override_kind: chosen,
                                  note: draftNote[row.video_id] ?? undefined,
                                })
                              }
                            >
                              Save
                            </button>
                            {row.override_kind && (
                              <button
                                type="button"
                                className="rounded border border-slate-300 px-2 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                                disabled={clearOverride.isPending}
                                onClick={() => clearOverride.mutate(row.video_id)}
                              >
                                Clear
                              </button>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  )
}
