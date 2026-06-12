import { useEffect, useMemo, useState } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import {
  MagnifyingGlassIcon,
  XMarkIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  MapPinIcon,
} from '@heroicons/react/24/outline'
import { fetchMeetings, type MeetingSort, type MeetingCard } from '../api/meetings'
import DecisionCardList from './DecisionCardList'

/**
 * MeetingCardList — a reusable, meeting-grain browser.
 *
 * Backed by `GET /api/meetings`, where meetings are linked to a topic / policy
 * question through their transcript. Each card shows the meeting's real decision
 * and question counts; a meeting with decisions expands inline into its own
 * decision cards (DecisionCardList scoped by meetingId).
 *
 * 100% live data — honest loading / error / empty states, never fabricated
 * cards or counts (CLAUDE.md: No Fabricated Data).
 */

const PAGE_SIZE = 24

const SORTS: { id: MeetingSort; label: string }[] = [
  { id: 'recent', label: 'Most recent' },
  { id: 'decisions', label: 'Most decisions' },
  { id: 'interesting', label: 'Most interesting' },
]

interface MeetingCardListProps {
  topicId?: number
  theme?: string
  questionId?: string
  /** 2-letter state code or full state name. */
  state?: string
  city?: string
  /** Heading shown above the list, e.g. "Meetings on Affordable housing". */
  title?: string
}

// A clean place label from the card's jurisdiction + state.
function placeLabel(m: MeetingCard): string {
  const place = m.city || m.jurisdiction || ''
  return [place, m.state_code].filter(Boolean).join(', ')
}

// Friendly date from an ISO yyyy-mm-dd string (the API already coerces).
function fmtDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function MeetingRow({ meeting }: { meeting: MeetingCard }) {
  const [open, setOpen] = useState(false)
  const canDrill = meeting.has_decisions && meeting.decision_count > 0
  const date = fmtDate(meeting.date)

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm transition hover:border-indigo-200">
      <button
        type="button"
        onClick={() => canDrill && setOpen((v) => !v)}
        aria-expanded={canDrill ? open : undefined}
        className={`flex w-full items-start gap-3 p-5 text-left ${
          canDrill ? 'cursor-pointer' : 'cursor-default'
        }`}
      >
        {canDrill ? (
          open ? (
            <ChevronDownIcon className="mt-0.5 h-5 w-5 flex-shrink-0 text-indigo-500" />
          ) : (
            <ChevronRightIcon className="mt-0.5 h-5 w-5 flex-shrink-0 text-gray-400" />
          )
        ) : (
          <span className="mt-0.5 h-5 w-5 flex-shrink-0" aria-hidden />
        )}
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-gray-900">{meeting.title || 'Untitled meeting'}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
            {placeLabel(meeting) && (
              <span className="inline-flex items-center gap-1">
                <MapPinIcon className="h-3.5 w-3.5" />
                {placeLabel(meeting)}
              </span>
            )}
            {date && <span>{date}</span>}
          </div>
          {/* Real counts — 0 is honest, not hidden. */}
          <div className="mt-2 flex flex-wrap gap-2">
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                meeting.decision_count > 0
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'bg-gray-100 text-gray-500'
              }`}
            >
              {meeting.decision_count} {meeting.decision_count === 1 ? 'decision' : 'decisions'}
            </span>
            {meeting.question_count > 0 && (
              <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
                {meeting.question_count} {meeting.question_count === 1 ? 'question' : 'questions'}
              </span>
            )}
          </div>
        </div>
      </button>

      {/* Inline drill-down: this meeting's decisions. */}
      {canDrill && open && (
        <div className="border-t border-gray-100 bg-gray-50/60 p-5">
          <DecisionCardList meetingId={meeting.meeting_id} />
        </div>
      )}
    </div>
  )
}

export default function MeetingCardList({
  topicId,
  theme,
  questionId,
  state,
  city,
  title,
}: MeetingCardListProps) {
  const [rawQuery, setRawQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [sort, setSort] = useState<MeetingSort>('recent')
  const [page, setPage] = useState(0)

  // Debounce the search box (~300ms) and reset to the first page on a new term.
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedQuery(rawQuery.trim())
      setPage(0)
    }, 300)
    return () => clearTimeout(t)
  }, [rawQuery])

  // Reset to the first page when the scope or sort changes.
  useEffect(() => {
    setPage(0)
  }, [topicId, theme, questionId, state, city, sort])

  const q = debouncedQuery || undefined

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: [
      'meetings',
      topicId ?? null,
      theme ?? null,
      questionId ?? null,
      state ?? null,
      city ?? null,
      q ?? null,
      sort,
      page,
    ],
    queryFn: () =>
      fetchMeetings({
        topicId,
        theme,
        questionId,
        state,
        city,
        q,
        sort,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  })

  const meetings = useMemo(() => data?.items ?? [], [data])
  const total = data?.pagination.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div>
      {/* Heading + real total count */}
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        {title ? <h2 className="text-xl font-bold text-gray-900">{title}</h2> : <span />}
        {!isLoading && !isError && (
          <span className="text-sm text-gray-500">
            {total.toLocaleString()} {total === 1 ? 'meeting' : 'meetings'}
          </span>
        )}
      </div>

      {/* Search bar + sort filters */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={rawQuery}
            onChange={(e) => setRawQuery(e.target.value)}
            placeholder="Search these meetings…"
            className="w-full rounded-full border border-gray-300 bg-white py-2.5 pl-10 pr-10 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          {rawQuery && (
            <button
              type="button"
              onClick={() => setRawQuery('')}
              aria-label="Clear search"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          )}
        </div>
        <div className="inline-flex shrink-0 rounded-full border border-gray-200 bg-white p-1">
          {SORTS.map((s) => {
            const on = sort === s.id
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => setSort(s.id)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                  on ? 'bg-indigo-600 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                {s.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Body — honest loading / error / empty / list states */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg border border-gray-200 bg-gray-100" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center text-sm text-red-700">
          Couldn&apos;t load meetings. Please try again.
        </div>
      ) : meetings.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-500">
          {debouncedQuery ? `No meetings match “${debouncedQuery}”.` : 'No meetings here yet.'}
        </div>
      ) : (
        <>
          <div className={`space-y-3 transition-opacity ${isFetching ? 'opacity-60' : ''}`}>
            {meetings.map((m) => (
              <MeetingRow key={m.meeting_id} meeting={m} />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="mt-8 flex items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:text-gray-300"
              >
                Previous
              </button>
              <span className="text-sm text-gray-500">
                Page {page + 1} of {totalPages.toLocaleString()}
              </span>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:text-gray-300"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
