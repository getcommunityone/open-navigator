import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  fetchFailureReasons,
  fetchFailureRows,
  retryFailures,
  type FailureReasonGroup,
  type FailureStage,
} from '../api/batchJobs'
import { LinkifiedText } from '../utils/linkifiedText'

const watchUrl = (videoId: string) => `https://www.youtube.com/watch?v=${videoId}`

// #792: the page behind the red failed count on the Videos and Transcripts rows of Batch Job Status.
// The scope (stage, cohort, state) lives in the URL and the title states it exactly, so the label
// and the numbers always describe the same filter (CLAUDE.md "Scope Label Must Match the Active Filter").

const STAGE_LABEL: Record<FailureStage, string> = {
  videos: 'Videos',
  transcripts: 'Transcripts',
}

const COHORT_LABEL: Record<string, string> = {
  data_centers: 'Data centers',
  priority: 'Priority states',
  all: 'All 50 states + DC',
}

const PAGE_SIZE = 50

function asStage(raw: string | null): FailureStage {
  return raw === 'videos' ? 'videos' : 'transcripts'
}

function ReasonVideos({
  stage,
  cohort,
  state,
  reasonId,
}: {
  stage: FailureStage
  cohort: string
  state: string
  reasonId: string
}) {
  const [offset, setOffset] = useState(0)
  const { data, isLoading, error } = useQuery({
    queryKey: ['batch-failure-rows', stage, cohort, state, reasonId, offset],
    queryFn: () => fetchFailureRows(stage, cohort, state, reasonId, offset, PAGE_SIZE),
  })
  if (isLoading) return <p className="px-3 py-2 text-xs text-slate-500">Loading videos…</p>
  if (error)
    return (
      <p className="px-3 py-2 text-xs text-red-700">
        Could not load these videos: {(error as Error).message}
      </p>
    )
  const rows = data?.rows ?? []
  const total = data?.total ?? 0
  if (rows.length === 0)
    return <p className="px-3 py-2 text-xs text-slate-500">No videos for this reason.</p>
  return (
    <div className="border-t border-slate-100 bg-slate-50/60">
      <table className="min-w-full text-xs">
        <thead className="text-left uppercase text-slate-500">
          <tr>
            <th className="px-3 py-1.5 font-medium">Video</th>
            <th className="px-3 py-1.5 font-medium">Title</th>
            <th className="px-3 py-1.5 font-medium">Jurisdiction</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.video_id} className="border-t border-slate-100 align-top">
              <td className="whitespace-nowrap px-3 py-1.5 font-mono">
                <a
                  href={`https://www.youtube.com/watch?v=${r.video_id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-teal-700 hover:underline"
                >
                  {r.video_id}
                </a>
              </td>
              <td className="px-3 py-1.5 text-slate-800">{r.title || '—'}</td>
              <td className="px-3 py-1.5">
                <div className="text-slate-800">{r.jurisdiction_name || r.jurisdiction_id || '—'}</div>
                <div className="font-mono text-[10px] text-slate-500">
                  {r.state_code || '—'} · {r.jurisdiction_id || '—'}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center justify-between px-3 py-2 text-xs text-slate-600">
        <span>
          {offset + 1}–{offset + rows.length} of {total.toLocaleString()}
        </span>
        <span className="flex gap-2">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="rounded border border-slate-300 bg-white px-2 py-0.5 disabled:opacity-40"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={offset + rows.length >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="rounded border border-slate-300 bg-white px-2 py-0.5 disabled:opacity-40"
          >
            Next
          </button>
        </span>
      </div>
    </div>
  )
}

type RetryTarget = { group?: string; reasonId?: string; label: string }

function GroupCard({
  group,
  total,
  stage,
  cohort,
  state,
}: {
  group: FailureReasonGroup
  total: number
  stage: FailureStage
  cohort: string
  state: string
}) {
  const [open, setOpen] = useState(false)
  const [openReason, setOpenReason] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const pct = total > 0 ? (group.count / total) * 100 : 0
  const backHref = `/admin/batch-jobs?cohort=${encodeURIComponent(cohort)}${state ? `&state=${state}` : ''}`

  // Retry = release these videos from the 30-day cooldown so the next Backfill fetches them. Asks first
  // (a dry run says exactly how many), changes nothing else, deletes nothing.
  const retry = async (target: RetryTarget) => {
    setBusy(true)
    setNote(null)
    try {
      const body = {
        stage,
        cohort,
        state,
        group: target.group,
        reason_id: target.reasonId,
      }
      const dry = await retryFailures({ ...body, dry_run: true })
      const careful =
        group.key === 'rate_limit'
          ? '\n\nYouTube is rate limiting: retrying straight away can hit the limit again. Wait a while first if you can.'
          : ''
      const ok = window.confirm(
        `Retry ${dry.matched.toLocaleString()} video${dry.matched === 1 ? '' : 's'} (${target.label})?\n\n` +
          `${dry.made_due.toLocaleString()} are waiting out the 30-day cooldown and will be released; ` +
          `${dry.already_due.toLocaleString()} are ready already. Nothing is deleted. They are fetched the ` +
          `next time Backfill runs on the Transcripts row.${careful}`,
      )
      if (!ok) return
      const done = await retryFailures({ ...body, dry_run: false })
      setNote(
        `Queued ${done.matched.toLocaleString()} video${done.matched === 1 ? '' : 's'} for retry ` +
          `(${done.made_due.toLocaleString()} released from the cooldown). Press Backfill on the Transcripts row to fetch them.`,
      )
    } catch (e) {
      setNote(`Could not queue the retry: ${(e as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex items-start justify-between gap-3 px-4 py-3">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="min-w-0 flex-1 text-left"
          aria-expanded={open}
        >
          <div className="text-sm font-semibold text-slate-900">
            <span className="mr-1 text-slate-400">{open ? '▾' : '▸'}</span>
            {group.label}
          </div>
          <p className="mt-0.5 text-xs text-slate-600">{group.advice}</p>
        </button>
        <div className="flex shrink-0 items-start gap-3">
          {group.retryable ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => void retry({ group: group.key, label: group.label })}
              title="Release these videos from the retry cooldown so the next Backfill fetches them again"
              className="rounded-md border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-800 hover:bg-emerald-100 disabled:opacity-50"
            >
              {busy ? 'Working…' : `↻ Retry ${group.count.toLocaleString()}`}
            </button>
          ) : (
            <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-500">
              Can&apos;t be retried
            </span>
          )}
          <div className="text-right">
            <div className="text-lg font-semibold tabular-nums text-red-700">
              {group.count.toLocaleString()}
            </div>
            <div className="text-[11px] tabular-nums text-slate-500">{pct.toFixed(1)}%</div>
          </div>
        </div>
      </div>
      {note ? (
        <div className="border-t border-emerald-100 bg-emerald-50 px-4 py-2 text-xs text-emerald-900">
          {note}{' '}
          <Link to={backHref} className="font-medium underline">
            Go to the Transcripts row
          </Link>
        </div>
      ) : null}
      {open ? (
        <div className="border-t border-slate-100">
          {group.reasons.map((r) => (
            <div key={r.reason_id} className="border-b border-slate-100 last:border-b-0">
              <div className="flex items-start gap-2 px-4 py-2 hover:bg-slate-50">
                <button
                  type="button"
                  onClick={() => setOpenReason(openReason === r.reason_id ? null : r.reason_id)}
                  className="mt-0.5 shrink-0 text-xs text-slate-400"
                  aria-expanded={openReason === r.reason_id}
                  aria-label="Show the videos for this reason"
                >
                  {openReason === r.reason_id ? '▾' : '▸'}
                </button>
                <div className="min-w-0 flex-1 break-words text-xs text-slate-800">
                  <LinkifiedText text={r.example || r.reason} />
                  <div className="mt-1 flex flex-wrap items-center gap-3">
                    {r.example_video_id ? (
                      <a
                        href={watchUrl(r.example_video_id)}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-teal-700 hover:underline"
                      >
                        ▶ Watch an example
                      </a>
                    ) : null}
                    {group.retryable ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void retry({ reasonId: r.reason_id, label: 'this reason' })}
                        className="font-medium text-emerald-700 hover:underline disabled:opacity-50"
                      >
                        ↻ Retry these {r.count.toLocaleString()}
                      </button>
                    ) : null}
                  </div>
                </div>
                <span className="shrink-0 text-sm font-medium tabular-nums text-slate-800">
                  {r.count.toLocaleString()}
                </span>
              </div>
              {openReason === r.reason_id ? (
                <ReasonVideos stage={stage} cohort={cohort} state={state} reasonId={r.reason_id} />
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export default function BatchFailureReasonsPage() {
  const [params] = useSearchParams()
  const stage = asStage(params.get('stage'))
  const cohort = params.get('cohort') || 'all'
  const state = (params.get('state') || '').toUpperCase()

  const { data, isLoading, error } = useQuery({
    queryKey: ['batch-failure-reasons', stage, cohort, state],
    queryFn: () => fetchFailureReasons(stage, cohort, state),
  })

  const cohortLabel = COHORT_LABEL[cohort] ?? cohort
  const stateLabel = state ? state : 'All states'
  const back = `/admin/batch-jobs?cohort=${encodeURIComponent(cohort)}${state ? `&state=${state}` : ''}`

  return (
    <div className="mx-auto max-w-5xl space-y-4 px-4 py-6">
      <div>
        <Link to={back} className="text-xs font-medium text-teal-700 hover:underline">
          ← Back to Batch Job Status
        </Link>
        <h1 className="mt-1 text-xl font-semibold text-slate-900">
          {STAGE_LABEL[stage]} failures
          <span className="ml-2 text-base font-normal text-slate-500">
            · {cohortLabel} · {stateLabel}
          </span>
        </h1>
        <p className="text-xs text-slate-500">
          Why videos in this scope failed, from the error saved on each video. The reasons add up to the
          failed count on the stage row.
        </p>
      </div>

      {isLoading ? <p className="text-sm text-slate-500">Loading reasons…</p> : null}
      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          Failure reasons are unavailable: {(error as Error).message}
        </div>
      ) : null}

      {data && data.total === 0 ? (
        <div className="rounded-md border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-600">
          No failed videos recorded for this scope.
        </div>
      ) : null}

      {data && data.total > 0 ? (
        <>
          <div className="text-sm text-slate-700">
            <span className="font-semibold tabular-nums text-red-700">{data.total.toLocaleString()}</span>{' '}
            failed video{data.total === 1 ? '' : 's'}
            {data.truncated ? ' (very rare messages are combined in the last group)' : ''}
          </div>
          <div className="space-y-3">
            {data.groups.map((g) => (
              <GroupCard
                key={g.key}
                group={g}
                total={data.total}
                stage={stage}
                cohort={cohort}
                state={state}
              />
            ))}
          </div>
        </>
      ) : null}
    </div>
  )
}
