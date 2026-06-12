import { useMemo, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeftIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { fetchTrendingCauses, type CauseItem } from '../api/trending'
import DecisionCardList from '../components/DecisionCardList'

export default function BrowseCauses() {
  const [query, setQuery] = useState('')
  // When a cause is picked, drill into the meeting-level decisions that mention
  // it. The decisions endpoint has no cause filter, so we seed its free-text
  // search with the cause name.
  const [selectedCause, setSelectedCause] = useState<CauseItem | null>(null)
  const navigate = useNavigate()
  const routerLocation = useLocation()

  // Go back to wherever the user came from; fall back to the home page when
  // this is the first in-app view (direct link / refresh).
  const handleBack = () => {
    if (routerLocation.key !== 'default') {
      navigate(-1)
    } else {
      navigate('/')
    }
  }

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['browse-causes'],
    queryFn: () => fetchTrendingCauses({ source: 'everyorg', limit: 100 }),
  })

  const causes = useMemo(() => data?.causes ?? [], [data])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return causes
    return causes.filter((c) => {
      if (c.name.toLowerCase().includes(q)) return true
      if (c.category.toLowerCase().includes(q)) return true
      return (c.description ?? '').toLowerCase().includes(q)
    })
  }, [causes, query])

  // Pill styling for the cause filter row — solid indigo when active.
  const chipClass = (on: boolean) =>
    `inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
      on
        ? 'border-indigo-600 bg-indigo-600 text-white'
        : 'border-gray-200 bg-white text-gray-700 hover:border-indigo-300 hover:text-indigo-700'
    }`

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        <button
          type="button"
          onClick={handleBack}
          className="inline-flex items-center gap-2 mb-4 text-sm font-medium text-gray-600 hover:text-indigo-600 transition-colors"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          Back
        </button>

        {/* Header card — title + search, matching the Search page */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-4">Browse Causes</h1>
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter causes (e.g. environment, health, education)…"
              className="w-full px-12 py-3 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-lg text-gray-900"
            />
          </div>
        </div>

        {/* Cause filter chips — pick one to scope the decisions below. The big
            grouped cause grid was replaced by these compact pills so the
            decision cards show immediately (no click needed). */}
        {isError ? (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Couldn&apos;t load causes.{' '}
            {(error as { message?: string } | undefined)?.message ?? 'Please try again.'}
          </div>
        ) : (
          <div className="mb-6 flex flex-wrap gap-2">
            <button type="button" onClick={() => setSelectedCause(null)} className={chipClass(selectedCause === null)}>
              All causes
            </button>
            {isLoading ? (
              <span className="px-2 py-1.5 text-sm text-gray-400">Loading causes…</span>
            ) : (
              filtered.map((cause) => (
                <button
                  key={cause.name}
                  type="button"
                  onClick={() => setSelectedCause(cause)}
                  className={chipClass(selectedCause?.name === cause.name)}
                >
                  <span aria-hidden="true">{cause.icon}</span>
                  {cause.name}
                </button>
              ))
            )}
          </div>
        )}

        {/* Decision cards — the shared Contested StoryCard, shown immediately.
            The decisions endpoint has no cause filter, so a picked cause seeds
            the free-text search; `key` remounts the list so that seed applies. */}
        <DecisionCardList
          key={selectedCause?.name ?? 'all-causes'}
          initialQuery={selectedCause?.name}
          title={selectedCause ? `Decisions on ${selectedCause.name}` : 'Most contested decisions'}
        />
      </div>
    </div>
  )
}
