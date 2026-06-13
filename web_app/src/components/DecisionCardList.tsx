import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import {
  AdjustmentsHorizontalIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { fetchDecisions, type DecisionSort } from '../api/decisions'
import { StoryCard, toRenderCards, CONTESTED_LENS } from './StoryLenses'
import StateSelect from './StateSelect'

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
  /** One or more civicsearch topic ids — decisions matching ANY are shown. */
  topicIds?: number[]
  /** EveryOrg cause slug — scopes decisions to that cause via the decision-text
   *  keyword path (cause -> decision -> meeting, transcript fallback). */
  causeId?: string
  questionId?: string
  /** Meeting id — drill into a single meeting's decisions. */
  meetingId?: number
  /** 2-letter state code or full state name. */
  state?: string
  city?: string
  /** Heading shown above the list, e.g. "Decisions on Affordable housing". */
  title?: string
  /** Seeds the search box / `q` param (used by the causes page, which has no
   *  dedicated cause filter on the decisions endpoint). */
  initialQuery?: string
  /** Show the "Advanced filters" toggle (state / city) next to the search box.
   *  Off by default so scoped pages (a single state/city) aren't cluttered. */
  showAdvancedFilters?: boolean
}

export default function DecisionCardList({
  topicIds,
  causeId,
  questionId,
  meetingId,
  state,
  city,
  title,
  initialQuery,
  showAdvancedFilters = false,
}: DecisionCardListProps) {
  const navigate = useNavigate()

  const [rawQuery, setRawQuery] = useState(initialQuery ?? '')
  // Debounced text actually sent to the API, so we don't fire per keystroke.
  const [debouncedQuery, setDebouncedQuery] = useState(initialQuery ?? '')
  const [sort, setSort] = useState<DecisionSort>('contested')
  const [page, setPage] = useState(0)

  // State / city filters live in the flyout and are the single source of truth.
  // They SEED from the `state`/`city` props (e.g. a place carried in from the
  // homepage URL) but stay user-editable — so the flyout works on every page,
  // not just the unscoped ones. The parent remounts us (via `key`) when its own
  // scope changes, which re-seeds these. City stays free-text; state is a
  // canonical dropdown. Raw inputs are debounced before hitting the API.
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [rawState, setRawState] = useState(state ?? '')
  const [rawCity, setRawCity] = useState(city ?? '')
  const [debouncedState, setDebouncedState] = useState(state ?? '')
  const [debouncedCity, setDebouncedCity] = useState(city ?? '')

  // Session-local "saved" bookmarks, keyed like the homepage carousel.
  const [savedKeys, setSavedKeys] = useState<Set<string>>(() => new Set())
  const toggleSave = (key: string) =>
    setSavedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  // Debounce the search box + advanced filters (~300ms) and reset to the first
  // page whenever any of them change.
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedQuery(rawQuery.trim())
      setDebouncedState(rawState.trim())
      setDebouncedCity(rawCity.trim())
      setPage(0)
    }, 300)
    return () => clearTimeout(t)
  }, [rawQuery, rawState, rawCity])

  // Stable key/value for the topic-id set (order-independent) used in the
  // query cache key and effect deps.
  const topicKey = (topicIds ?? []).join(',')

  // Reset to the first page when the scope or sort changes.
  useEffect(() => {
    setPage(0)
  }, [topicKey, causeId, questionId, meetingId, sort])

  const q = debouncedQuery || undefined
  // The flyout inputs (seeded from props) are authoritative for state/city.
  const effectiveState = debouncedState || undefined
  const effectiveCity = debouncedCity || undefined
  // Count of active filters, for the Filters button badge: non-default sort
  // plus any state/city narrowing.
  const advancedCount = (rawState.trim() ? 1 : 0) + (rawCity.trim() ? 1 : 0)
  const activeFilterCount = advancedCount + (sort !== 'contested' ? 1 : 0)

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: [
      'decisions',
      topicKey || null,
      causeId ?? null,
      questionId ?? null,
      meetingId ?? null,
      effectiveState ?? null,
      effectiveCity ?? null,
      q ?? null,
      sort,
      page,
    ],
    queryFn: () =>
      fetchDecisions({
        topicIds: topicIds && topicIds.length ? topicIds : undefined,
        causeId,
        questionId,
        meetingId,
        state: effectiveState,
        city: effectiveCity,
        q,
        sort,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  })

  const unscoped = !effectiveState && !effectiveCity
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

      {/* Search bar + a single Filters button on the same row — matches the
          Search page. Sort and the optional state/city filters live inside the
          flyout panel, so the row stays clean. */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          // Flush the debounce so the button / Enter searches immediately.
          setDebouncedQuery(rawQuery.trim())
          setDebouncedState(rawState.trim())
          setDebouncedCity(rawCity.trim())
          setPage(0)
        }}
        className="mb-5 flex items-stretch gap-3"
      >
        <div className="relative flex-1">
          <input
            type="text"
            value={rawQuery}
            onChange={(e) => setRawQuery(e.target.value)}
            placeholder="Search these decisions…"
            className="w-full rounded-lg border-2 border-gray-300 bg-white py-3 pl-4 pr-10 text-base text-gray-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary-500"
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
        <button
          type="submit"
          aria-label="Search"
          className="flex shrink-0 items-center justify-center rounded-lg bg-primary-600 px-4 text-white transition-colors hover:bg-primary-700"
        >
          <MagnifyingGlassIcon className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          aria-expanded={advancedOpen}
          className={`flex shrink-0 items-center gap-2 rounded-lg border-2 px-3 py-3 text-sm font-medium transition-colors sm:px-4 ${
            advancedOpen
              ? 'border-primary-500 bg-primary-50 text-primary-700'
              : 'border-gray-300 text-gray-700 hover:border-gray-400 hover:bg-gray-50'
          }`}
        >
          <AdjustmentsHorizontalIcon className="h-5 w-5" />
          <span>Filters</span>
          {activeFilterCount > 0 && (
            <span className="ml-0.5 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-primary-600 px-1 text-xs font-bold text-white">
              {activeFilterCount}
            </span>
          )}
        </button>
      </form>

      {/* Filter panel — a right-side flyout (matches the Search & Jurisdictions
          pages): backdrop + fixed drawer. Sort (always) + optional state/city
          server-side filters live inside. */}
      {advancedOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black bg-opacity-50"
            onClick={() => setAdvancedOpen(false)}
            aria-hidden="true"
          />
          <div
            className="fixed right-0 top-0 z-50 h-full w-full overflow-y-auto bg-white shadow-2xl md:w-96"
            role="dialog"
            aria-label="Filters"
          >
            <div className="flex items-center justify-between border-b border-gray-200 p-4">
              <h3 className="text-lg font-bold text-gray-900">Filters</h3>
              <button
                type="button"
                onClick={() => setAdvancedOpen(false)}
                aria-label="Close filters"
                className="rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-6 p-6">
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Sort by</div>
                <div className="inline-flex flex-wrap rounded-full border border-gray-200 bg-white p-1">
                  {SORTS.map((s) => {
                    const on = sort === s.id
                    return (
                      <button
                        key={s.id}
                        type="button"
                        onClick={() => setSort(s.id)}
                        className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                          on ? 'bg-primary-500 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
                        }`}
                      >
                        {s.label}
                      </button>
                    )
                  })}
                </div>
              </div>

              {showAdvancedFilters && (
                <div className="grid grid-cols-1 gap-3">
                  <label className="flex flex-col gap-1 text-xs font-semibold text-gray-600">
                    State
                    <StateSelect
                      value={rawState}
                      onChange={setRawState}
                      className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-normal text-gray-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-xs font-semibold text-gray-600">
                    City
                    <input
                      type="text"
                      value={rawCity}
                      onChange={(e) => setRawCity(e.target.value)}
                      placeholder="e.g. Sherborn"
                      className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-normal text-gray-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </label>
                </div>
              )}

              {activeFilterCount > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    setRawState('')
                    setRawCity('')
                    setSort('contested')
                  }}
                  className="text-xs font-semibold text-primary-600 hover:text-primary-700"
                >
                  Reset filters
                </button>
              )}
            </div>
          </div>
        </>
      )}

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
