import { useMemo, useState } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeftIcon } from '@heroicons/react/24/outline'
import { fetchTrendingCauses, type CauseItem } from '../api/trending'
import DecisionCardList from '../components/DecisionCardList'

export default function BrowseCauses() {
  // Picking a cause SCOPES the decision cards shown below — it no longer drills
  // into a separate view. The cards stay at the top the whole time (matching
  // Browse Topics). A picked cause filters via ?cause_id= (cause -> decision ->
  // meeting, transcript fallback), not a free-text seed.
  const [selectedCause, setSelectedCause] = useState<CauseItem | null>(null)
  const navigate = useNavigate()
  const routerLocation = useLocation()

  // Place filter carried over from the homepage (e.g. ?state=AL&city=Tuscaloosa),
  // identical to Browse Topics: the cause pills + decision cards scope to that
  // place. Default the decision scope to the city we arrived with (so Tuscaloosa
  // filters to Tuscaloosa, not all of AL), with a one-click broaden to the state.
  const [searchParams] = useSearchParams()
  const stateCode = (searchParams.get('state') || '').trim().toUpperCase() || undefined
  const cityName = (searchParams.get('city') || '').trim() || undefined
  const [placeScope, setPlaceScope] = useState<'city' | 'state'>('city')
  const scopedCity = cityName && placeScope === 'city' ? cityName : undefined
  const placeLabel = scopedCity || stateCode

  // Go back to wherever the user came from; fall back to the home page when
  // this is the first in-app view (direct link / refresh).
  const handleBack = () => {
    if (routerLocation.key !== 'default') {
      navigate(-1)
    } else {
      navigate('/')
    }
  }

  // Surface only the top causes (matching Browse Topics' top-pills row), ranked
  // by their REAL meeting count (gold.meeting_cause_link). When a place is in
  // scope the API returns only causes discussed there, with place-scoped counts.
  const TOP_CAUSE_COUNT = 5

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['browse-causes', stateCode ?? null, scopedCity ?? null],
    queryFn: () =>
      fetchTrendingCauses({
        source: 'everyorg',
        limit: TOP_CAUSE_COUNT,
        state: stateCode,
        city: scopedCity,
      }),
  })

  const causes = useMemo(
    () =>
      [...(data?.causes ?? [])]
        .sort((a, b) => (b.meeting_count ?? 0) - (a.meeting_count ?? 0))
        .slice(0, TOP_CAUSE_COUNT),
    [data],
  )

  // Pill styling for the cause filter row — solid teal when active (theme).
  const chipClass = (on: boolean) =>
    `inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
      on
        ? 'border-primary-500 bg-primary-500 text-white'
        : 'border-gray-200 bg-white text-gray-700 hover:border-primary-500 hover:text-primary-700'
    }`

  // Small count badge after the cause name — the real number of analyzed
  // meetings that discuss it (mirrors the Browse Topics count badge).
  const countBadge = (n: number, on: boolean) => (
    <span
      className={`rounded-full px-1.5 py-0.5 text-xs font-semibold tabular-nums ${
        on ? 'bg-white/20 text-white' : 'bg-gray-100 text-gray-500'
      }`}
    >
      {n.toLocaleString()}
    </span>
  )

  const listTitle = selectedCause
    ? `Decisions on ${selectedCause.name}${placeLabel ? ` in ${placeLabel}` : ''}`
    : `Most contested decisions${placeLabel ? ` in ${placeLabel}` : ''}`

  return (
    <div className="min-h-screen bg-gray-50 py-5">
      <div className="max-w-7xl mx-auto px-4">
        <button
          type="button"
          onClick={handleBack}
          className="inline-flex items-center gap-2 mb-3 text-sm font-medium text-gray-600 hover:text-primary-600 transition-colors"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          Back
        </button>

        {/* Header — title only; the cause pills below scope the cards, and
            the search lives in the card list (one search bar, Search-page style). */}
        <h1 className="text-3xl font-bold text-gray-900 mb-4">
          Browse Causes{placeLabel ? <span className="text-gray-400 font-normal"> · {placeLabel}</span> : null}
        </h1>

        {/* Place scope — default to the city we arrived with, with a one-click
            broaden to the whole state (handy when a city is sparsely analyzed).
            Mirrors Browse Topics. Only shown when we arrived with a city+state. */}
        {cityName && stateCode && (
          <div className="mb-4 inline-flex items-center gap-1 rounded-lg bg-gray-100 p-1 text-sm">
            <button
              type="button"
              onClick={() => setPlaceScope('city')}
              className={`rounded-md px-3 py-1 font-medium transition-colors ${
                placeScope === 'city' ? 'bg-primary-500 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              📍 {cityName}
            </button>
            <button
              type="button"
              onClick={() => setPlaceScope('state')}
              className={`rounded-md px-3 py-1 font-medium transition-colors ${
                placeScope === 'state' ? 'bg-primary-500 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              All of {stateCode}
            </button>
          </div>
        )}

        {/* Cause filter pills — pick one to scope the decision cards below. The
            cards render immediately (no click-into-a-separate-view needed). */}
        {isError ? (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Couldn&apos;t load causes.{' '}
            {(error as { message?: string } | undefined)?.message ?? 'Please try again.'}
          </div>
        ) : (
          <div className="mb-4 flex flex-wrap items-center gap-2">
            {isLoading ? (
              <span className="px-2 py-1.5 text-sm text-gray-400">Loading causes…</span>
            ) : causes.length === 0 ? (
              <span className="px-2 py-1.5 text-sm text-gray-400">
                No causes discussed{placeLabel ? ` in ${placeLabel}` : ''} yet.
              </span>
            ) : (
              causes.map((cause) => {
                const on = selectedCause?.name === cause.name
                return (
                  <button
                    key={cause.name}
                    type="button"
                    // Clicking the active pill clears it (back to all causes) —
                    // replaces the removed "All causes" reset button.
                    onClick={() => setSelectedCause(on ? null : cause)}
                    className={chipClass(on)}
                  >
                    <span aria-hidden="true">{cause.icon}</span>
                    {cause.name}
                    {cause.meeting_count != null && cause.meeting_count > 0 && countBadge(cause.meeting_count, on)}
                  </button>
                )
              })
            )}
          </div>
        )}

        {/* Decision cards — the shared Contested StoryCard grid with YouTube
            meeting previews, shown immediately. A picked cause filters via
            ?cause_id= (cause -> decision -> meeting, transcript fallback); the
            place scope narrows by state/city. `key` remounts on any scope change. */}
        <DecisionCardList
          key={`${selectedCause?.cause_id ?? 'all-causes'}-${stateCode ?? 'us'}-${scopedCity ?? 'state'}`}
          causeId={selectedCause?.cause_id ?? undefined}
          state={stateCode}
          city={scopedCity}
          title={listTitle}
          showAdvancedFilters
        />
      </div>
    </div>
  )
}
