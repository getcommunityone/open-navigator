import { useMemo, useState } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeftIcon, MagnifyingGlassIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { fetchTopics, type TopicSummary } from '../api/topics'
import DecisionCardList from '../components/DecisionCardList'

export default function BrowseTopics() {
  const [query, setQuery] = useState('')
  // When a topic is picked, the page drills into its meeting-level decision
  // cards (search + filters) instead of the taxonomy grid.
  const [selectedTopic, setSelectedTopic] = useState<TopicSummary | null>(null)
  // The chip row always shows just the 5 most-discussed topics; "Show all"
  // opens a dismissible flyout with the full catalog rather than expanding the
  // row inline. The filter box always searches the full catalog regardless.
  const [flyoutOpen, setFlyoutOpen] = useState(false)
  // Search box scoped to the flyout's full-catalog grid.
  const [flyoutQuery, setFlyoutQuery] = useState('')
  const navigate = useNavigate()
  const routerLocation = useLocation()
  // Place filter carried over from the homepage (e.g. ?state=GA). When present,
  // the catalog is scoped to topics actually discussed in that state.
  const [searchParams] = useSearchParams()
  const stateCode = (searchParams.get('state') || '').trim().toUpperCase() || undefined
  // City name carried over from the homepage (e.g. ?city=Tuscaloosa). When
  // present, both the topic catalog and the decisions below scope to that city.
  const cityName = (searchParams.get('city') || '').trim() || undefined
  const placeLabel = cityName ?? stateCode

  // Go back to wherever the user came from; fall back to the home page when
  // this is the first in-app view (direct link / refresh).
  const handleBack = () => {
    if (routerLocation.key !== 'default') {
      navigate(-1)
    } else {
      navigate('/')
    }
  }

  const { data, isLoading, isError, error } = useQuery<TopicSummary[]>({
    queryKey: ['topics', stateCode ?? null, cityName ?? null],
    queryFn: () => fetchTopics(stateCode, cityName),
  })

  const topics = useMemo(() => data ?? [], [data])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return topics
    return topics.filter((t) => {
      if (t.name.toLowerCase().includes(q)) return true
      return t.keywords.some((k) => k.toLowerCase().includes(q))
    })
  }, [topics, query])

  const isFiltering = query.trim().length > 0

  // Topics in most-discussed order (the API already sorts by occurrences desc,
  // but sort defensively). The chip row shows the top 5; the rest live in the
  // flyout. A search in the page-level box shows every match inline.
  const ranked = useMemo(
    () => [...topics].sort((a, b) => b.transcript_occurrences - a.transcript_occurrences),
    [topics],
  )
  const TOP_N = 5
  const visibleTopics = isFiltering ? filtered : ranked.slice(0, TOP_N)
  const hiddenCount = ranked.length - TOP_N

  // Full catalog for the flyout, filtered by its own search box.
  const flyoutTopics = useMemo(() => {
    const q = flyoutQuery.trim().toLowerCase()
    if (!q) return ranked
    return ranked.filter((t) => {
      if (t.name.toLowerCase().includes(q)) return true
      return t.keywords.some((k) => k.toLowerCase().includes(q))
    })
  }, [ranked, flyoutQuery])

  // Selecting a topic (from a chip or the flyout) scopes the decisions below and
  // dismisses the flyout.
  const pickTopic = (topic: TopicSummary | null) => {
    setSelectedTopic(topic)
    setFlyoutOpen(false)
  }

  // Pill styling for the topic filter row — solid indigo when active.
  const chipClass = (on: boolean) =>
    `rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
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
          <h1 className="text-3xl font-bold text-gray-900 mb-4">
            Browse Topics{placeLabel ? ` · ${placeLabel}` : ''}
          </h1>
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter topics (e.g. housing, transit, climate)…"
              className="w-full px-12 py-3 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-lg text-gray-900"
            />
          </div>
        </div>

        {/* Topic filter chips — pick one to scope the decisions below. The big
            keyword-pill category grid was replaced by these compact pills so the
            decision cards show immediately (no click needed). */}
        {isError ? (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Couldn&apos;t load topics.{' '}
            {(error as { message?: string } | undefined)?.message ?? 'Please try again.'}
          </div>
        ) : (
          <div className="mb-6 flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => pickTopic(null)} className={chipClass(selectedTopic === null)}>
              All topics
            </button>
            {isLoading ? (
              <span className="px-2 py-1.5 text-sm text-gray-400">Loading topics…</span>
            ) : (
              <>
                {visibleTopics.map((topic) => {
                  const on = selectedTopic?.topic_id === topic.topic_id
                  return (
                    <button
                      key={topic.topic_id}
                      type="button"
                      onClick={() => pickTopic(topic)}
                      className={`inline-flex items-center gap-1.5 ${chipClass(on)}`}
                    >
                      <span>{topic.name}</span>
                      <span
                        className={`rounded-full px-1.5 py-0.5 text-xs font-semibold tabular-nums ${
                          on ? 'bg-white/20 text-white' : 'bg-gray-100 text-gray-500'
                        }`}
                        title={`${topic.transcript_occurrences.toLocaleString()} transcript mentions`}
                      >
                        {topic.transcript_occurrences.toLocaleString()}
                      </span>
                    </button>
                  )
                })}

                {/* Open the full catalog in a flyout — hidden while filtering,
                    since the page search already narrows the list inline. */}
                {!isFiltering && hiddenCount > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      setFlyoutQuery('')
                      setFlyoutOpen(true)
                    }}
                    className="rounded-full border border-dashed border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-600 transition-colors hover:border-indigo-300 hover:text-indigo-700"
                  >
                    {`View all ${ranked.length} topics`}
                  </button>
                )}

                {isFiltering && visibleTopics.length === 0 && (
                  <span className="px-2 py-1.5 text-sm text-gray-400">No topics match “{query.trim()}”.</span>
                )}
              </>
            )}
          </div>
        )}

        {/* Honest empty-state when a place has decisions but no topic-tagged
            transcripts (topic linkage comes from CivicSearch, which doesn't
            cover every city). The decisions below are still place-scoped. */}
        {!isError && !isLoading && placeLabel && topics.length === 0 && (
          <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600">
            No topic breakdown is available for{' '}
            <span className="font-medium text-gray-900">{placeLabel}</span> yet — showing all
            of its decisions below.
          </div>
        )}

        {/* Keywords for the active topic (informative; mirrors the old card). */}
        {selectedTopic && selectedTopic.keywords.length > 0 && (
          <div className="mb-5 flex flex-wrap gap-1.5">
            {selectedTopic.keywords.map((kw) => (
              <span key={kw} className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700">
                {kw}
              </span>
            ))}
          </div>
        )}

        {/* Decision cards — the shared Contested StoryCard, shown immediately. */}
        <DecisionCardList
          topicId={selectedTopic?.topic_id}
          state={stateCode}
          city={cityName}
          title={selectedTopic ? `Decisions on ${selectedTopic.name}` : 'Most contested decisions'}
        />
      </div>

      {/* Full-catalog flyout — a dismissible right-side drawer that replaces the
          old inline "Show all" expansion. */}
      {flyoutOpen && (
        <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setFlyoutOpen(false)}
            aria-hidden="true"
          />
          <div className="relative flex h-full w-full max-w-md flex-col bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
              <h2 className="text-lg font-semibold text-gray-900">All topics</h2>
              <button
                type="button"
                onClick={() => setFlyoutOpen(false)}
                className="rounded-full p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
                aria-label="Close"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="border-b border-gray-200 px-5 py-3">
              <div className="relative">
                <MagnifyingGlassIcon className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
                <input
                  type="text"
                  value={flyoutQuery}
                  onChange={(e) => setFlyoutQuery(e.target.value)}
                  placeholder="Filter topics…"
                  autoFocus
                  className="w-full rounded-lg border-2 border-gray-300 py-2 pl-10 pr-3 text-sm text-gray-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
            <div className="flex flex-wrap content-start gap-2 overflow-y-auto px-5 py-4">
              {flyoutTopics.length === 0 ? (
                <span className="px-1 py-1.5 text-sm text-gray-400">
                  No topics match “{flyoutQuery.trim()}”.
                </span>
              ) : (
                flyoutTopics.map((topic) => {
                  const on = selectedTopic?.topic_id === topic.topic_id
                  return (
                    <button
                      key={topic.topic_id}
                      type="button"
                      onClick={() => pickTopic(topic)}
                      className={`inline-flex items-center gap-1.5 ${chipClass(on)}`}
                    >
                      <span>{topic.name}</span>
                      <span
                        className={`rounded-full px-1.5 py-0.5 text-xs font-semibold tabular-nums ${
                          on ? 'bg-white/20 text-white' : 'bg-gray-100 text-gray-500'
                        }`}
                        title={`${topic.transcript_occurrences.toLocaleString()} transcript mentions`}
                      >
                        {topic.transcript_occurrences.toLocaleString()}
                      </span>
                    </button>
                  )
                })
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
