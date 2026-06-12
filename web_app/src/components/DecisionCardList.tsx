import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { MagnifyingGlassIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { fetchDecisions, type DecisionSort } from '../api/decisions'
import { StoryCard, toRenderCards, CONTESTED_LENS } from './StoryLenses'

/**
 * DecisionCardList — a reusable, meeting-level decision browser.
 *
 * Renders the SAME Contested-lens StoryCard used on the homepage, backed by
 * `GET /api/decisions` (via `fetchDecisions`). Scope it to a topic, a policy
 * question, a place, or a free-text seed; it adds a search bar, a sort control,
 * and "Load more" pagination on top.
 *
 * 100% live data — honest loading / error / empty states, never fabricated
 * cards or counts (CLAUDE.md: No Fabricated Data).
 */

const PAGE_SIZE = 24

const SORTS: { id: DecisionSort; label: string }[] = [
  { id: 'contested', label: 'Most contested' },
  { id: 'recent', label: 'Most recent' },
  { id: 'interesting', label: 'Most interesting' },
]

interface DecisionCardListProps {
  topicId?: number
  questionId?: string
  /** 2-letter state code or full state name. */
  state?: string
  city?: string
  /** Heading shown above the list, e.g. "Decisions on Affordable housing". */
  title?: string
  /** Seeds the search box / `q` param (used by the causes page, which has no
   *  dedicated cause filter on the decisions endpoint). */
  initialQuery?: string
}

export default function DecisionCardList({
  topicId,
  questionId,
  state,
  city,
  title,
  initialQuery,
}: DecisionCardListProps) {
  const navigate = useNavigate()

  const [rawQuery, setRawQuery] = useState(initialQuery ?? '')
  // Debounced text actually sent to the API, so we don't fire per keystroke.
  const [debouncedQuery, setDebouncedQuery] = useState(initialQuery ?? '')
  const [sort, setSort] = useState<DecisionSort>('contested')
  const [page, setPage] = useState(0)

  // Session-local "saved" bookmarks, keyed like the homepage carousel.
  const [savedKeys, setSavedKeys] = useState<Set<string>>(() => new Set())
  const toggleSave = (key: string) =>
    setSavedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

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
  }, [topicId, questionId, state, city, sort])

  const q = debouncedQuery || undefined

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ['decisions', topicId ?? null, questionId ?? null, state ?? null, city ?? null, q ?? null, sort, page],
    queryFn: () =>
      fetchDecisions({
        topicId,
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

  const unscoped = !state && !city
  const cards = useMemo(() => toRenderCards(data?.items ?? [], unscoped), [data, unscoped])

  const total = data?.pagination.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const cardKey = (url: string | undefined, i: number) => url || `decision-${page}-${i}`

  return (
    <div>
      {/* Heading + real total count */}
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        {title ? <h2 className="text-xl font-bold text-gray-900">{title}</h2> : <span />}
        {!isLoading && !isError && (
          <span className="text-sm text-gray-500">
            {total.toLocaleString()} {total === 1 ? 'decision' : 'decisions'}
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
            placeholder="Search these decisions…"
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

      {/* Body — honest loading / error / empty / grid states */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-48 animate-pulse rounded-2xl border border-gray-200 bg-gray-100" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center text-sm text-red-700">
          Couldn&apos;t load decisions. Please try again.
        </div>
      ) : cards.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-500">
          {debouncedQuery
            ? `No decisions match “${debouncedQuery}”.`
            : 'No decisions here yet.'}
        </div>
      ) : (
        <>
          <div
            className={`grid grid-cols-1 gap-4 transition-opacity sm:grid-cols-2 lg:grid-cols-3 ${
              isFetching ? 'opacity-60' : ''
            }`}
          >
            {cards.map((card, i) => {
              const key = cardKey(card.url, i)
              return (
                <StoryCard
                  key={key}
                  card={card}
                  lens={CONTESTED_LENS}
                  saved={savedKeys.has(key)}
                  onToggleSave={() => toggleSave(key)}
                  onOpen={() => card.url && navigate(card.url)}
                />
              )
            })}
          </div>

          {/* Pagination — only when there's more than one page of real results. */}
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
