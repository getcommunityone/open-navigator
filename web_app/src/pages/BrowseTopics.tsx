import { Fragment, useMemo, useState } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Dialog, Transition } from '@headlessui/react'
import {
  ArrowLeftIcon,
  MagnifyingGlassIcon,
  AdjustmentsHorizontalIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { fetchTopics, type TopicSummary } from '../api/topics'
import DecisionCardList from '../components/DecisionCardList'

// How many topic pills to surface inline before the rest move to the flyout.
// The API returns topics sorted by transcript_occurrences desc, so the first
// few are the most-discussed.
const TOP_PILL_COUNT = 4

export default function BrowseTopics() {
  const [query, setQuery] = useState('')
  // Picking a topic SCOPES the decision cards shown below — it no longer drills
  // into a separate view. The cards stay at the top the whole time.
  const [selectedTopic, setSelectedTopic] = useState<TopicSummary | null>(null)
  // The full topic catalog + keyword search lives in a slide-over flyout so the
  // main view stays focused on the top handful of topics.
  const [flyoutOpen, setFlyoutOpen] = useState(false)
  const navigate = useNavigate()
  const routerLocation = useLocation()
  // Place filter carried over from the homepage (e.g. ?state=GA&city=Atlanta).
  // The topic catalog is state-grain, but the decision cards scope to the city
  // when we have one — so browsing from Atlanta filters to Atlanta, not all GA.
  const [searchParams] = useSearchParams()
  const stateCode = (searchParams.get('state') || '').trim().toUpperCase() || undefined
  const cityName = (searchParams.get('city') || '').trim() || undefined
  // When a city is carried in, default the decision scope to that city (e.g.
  // Atlanta, not all of GA) but let the user broaden to the state — some cities
  // have little analyzed data yet, so we never dead-end on an empty page.
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

  const { data, isLoading, isError, error } = useQuery<TopicSummary[]>({
    queryKey: ['topics', stateCode ?? null],
    queryFn: () => fetchTopics(stateCode),
  })

  const topics = useMemo(() => data ?? [], [data])

  // Full catalog filtered by the flyout keyword search.
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return topics
    return topics.filter((t) => {
      if (t.name.toLowerCase().includes(q)) return true
      return t.keywords.some((k) => k.toLowerCase().includes(q))
    })
  }, [topics, query])

  // Inline pills: the top N most-discussed topics, plus the active one if the
  // user picked something further down the list via the flyout.
  const topPills = useMemo(() => {
    const top = topics.slice(0, TOP_PILL_COUNT)
    if (selectedTopic && !top.some((t) => t.topic_id === selectedTopic.topic_id)) {
      return [...top, selectedTopic]
    }
    return top
  }, [topics, selectedTopic])

  // Pill styling for the topic filter row — solid teal (theme) when active.
  const chipClass = (on: boolean) =>
    `inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
      on
        ? 'border-primary-500 bg-primary-500 text-white'
        : 'border-gray-200 bg-white text-gray-700 hover:border-primary-500 hover:text-primary-700'
    }`

  // Full-width row styling for the flyout catalog — long topic names made the
  // old wrap-of-chips layout collapse into a ragged column, so the catalog is a
  // proper vertical list: name left, count right, uniform hit targets.
  const rowClass = (on: boolean) =>
    `flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
      on
        ? 'bg-primary-50 font-semibold text-primary-700'
        : 'text-gray-700 hover:bg-gray-50'
    }`

  // Small count badge shown after a topic name (transcript snippets tagged).
  const countBadge = (n: number, on: boolean) => (
    <span
      className={`rounded-full px-1.5 py-0.5 text-xs font-semibold tabular-nums ${
        on ? 'bg-white/20 text-white' : 'bg-gray-100 text-gray-500'
      }`}
    >
      {n.toLocaleString()}
    </span>
  )

  const pickTopic = (topic: TopicSummary | null) => {
    setSelectedTopic(topic)
    setFlyoutOpen(false)
  }

  const listTitle = selectedTopic
    ? `Decisions on ${selectedTopic.name}`
    : `Most contested decisions${placeLabel ? ` · ${placeLabel}` : ''}`

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        <button
          type="button"
          onClick={handleBack}
          className="inline-flex items-center gap-2 mb-4 text-sm font-medium text-gray-600 hover:text-primary-600 transition-colors"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          Back
        </button>

        {/* Header card — title + place toggle on one row, then the topic pills. */}
        <div className="bg-white rounded-lg shadow-sm p-4 mb-4">
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
            <h1 className="text-2xl font-bold text-gray-900">
              Browse Topics{placeLabel ? ` · ${placeLabel}` : ''}
            </h1>
            {/* Place scope — default to the city we arrived with, with a one-click
                broaden to the whole state (handy when a city is sparsely analyzed). */}
            {cityName && stateCode && (
              <div className="inline-flex rounded-full border border-gray-200 bg-gray-50 p-0.5 text-sm">
                <button
                  type="button"
                  onClick={() => setPlaceScope('city')}
                  className={`rounded-full px-3 py-1 font-medium transition-colors ${
                    placeScope === 'city' ? 'bg-primary-500 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  📍 {cityName}
                </button>
                <button
                  type="button"
                  onClick={() => setPlaceScope('state')}
                  className={`rounded-full px-3 py-1 font-medium transition-colors ${
                    placeScope === 'state' ? 'bg-primary-500 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  All of {stateCode}
                </button>
              </div>
            )}
          </div>

          {/* Top topics inline — pick one to scope the decision cards below. The
              rest of the catalog + keyword search live in the "More topics" flyout. */}
          {isError ? (
            <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Couldn&apos;t load topics.{' '}
            {(error as { message?: string } | undefined)?.message ?? 'Please try again.'}
          </div>
          ) : (
            <div className="mt-3 flex flex-wrap items-center gap-2">
            {isLoading ? (
              <span className="px-2 py-1.5 text-sm text-gray-400">Loading topics…</span>
            ) : (
              topPills.map((topic) => {
                const on = selectedTopic?.topic_id === topic.topic_id
                return (
                  <button
                    key={topic.topic_id}
                    type="button"
                    // Clicking the active pill clears it (back to all topics) —
                    // replaces the removed "All topics" reset button.
                    onClick={() => pickTopic(on ? null : topic)}
                    className={chipClass(on)}
                  >
                    {topic.name}
                    {countBadge(topic.transcript_occurrences, on)}
                  </button>
                )
              })
            )}
            {!isLoading && topics.length > 0 && (
              <button
                type="button"
                onClick={() => setFlyoutOpen(true)}
                className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border border-dashed border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:border-primary-500 hover:text-primary-700"
              >
                <AdjustmentsHorizontalIcon className="h-4 w-4" />
                More topics
              </button>
            )}
          </div>
          )}
        </div>

        {/* Decision cards — the shared Contested StoryCard grid with YouTube
            meeting previews, shown immediately. Picking a topic scopes this
            list; the `key` remounts it so the new scope applies cleanly. */}
        <DecisionCardList
          key={`${selectedTopic?.topic_id ?? 'all-topics'}-${scopedCity ?? 'state'}`}
          topicId={selectedTopic?.topic_id}
          state={stateCode}
          city={scopedCity}
          title={listTitle}
          showAdvancedFilters
        />
      </div>

      {/* Filter flyout — full topic catalog + keyword search, slid in from the
          right. Drilldowns (selecting any topic) happen here too. */}
      <Transition appear show={flyoutOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => setFlyoutOpen(false)}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/30" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-hidden">
            <div className="absolute inset-y-0 right-0 flex max-w-full pl-10">
              <Transition.Child
                as={Fragment}
                enter="transform transition ease-out duration-200"
                enterFrom="translate-x-full"
                enterTo="translate-x-0"
                leave="transform transition ease-in duration-150"
                leaveFrom="translate-x-0"
                leaveTo="translate-x-full"
              >
                <Dialog.Panel className="flex h-full w-screen max-w-md flex-col bg-white shadow-xl">
                  <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
                    <Dialog.Title className="text-lg font-semibold text-gray-900">
                      All topics{placeLabel ? ` · ${placeLabel}` : ''}
                    </Dialog.Title>
                    <button
                      type="button"
                      onClick={() => setFlyoutOpen(false)}
                      className="rounded-full p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
                    >
                      <XMarkIcon className="h-6 w-6" />
                    </button>
                  </div>

                  <div className="border-b border-gray-200 px-6 py-4">
                    <div className="relative">
                      <MagnifyingGlassIcon className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
                      <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Filter topics or keywords (e.g. housing, transit)…"
                        className="w-full rounded-lg border-2 border-gray-300 px-10 py-2 text-sm text-gray-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                  </div>

                  <div className="flex-1 overflow-y-auto px-3 py-2">
                    <button
                      type="button"
                      onClick={() => pickTopic(null)}
                      className={rowClass(selectedTopic === null)}
                    >
                      <span className="truncate">All topics</span>
                    </button>
                    {filtered.map((topic) => {
                      const on = selectedTopic?.topic_id === topic.topic_id
                      return (
                        <button
                          key={topic.topic_id}
                          type="button"
                          onClick={() => pickTopic(topic)}
                          className={rowClass(on)}
                        >
                          <span className="truncate">{topic.name}</span>
                          <span className="shrink-0 tabular-nums text-xs font-medium text-gray-400">
                            {topic.transcript_occurrences.toLocaleString()}
                          </span>
                        </button>
                      )
                    })}
                    {filtered.length === 0 && (
                      <p className="px-3 py-3 text-sm text-gray-400">
                        No topics match &ldquo;{query.trim()}&rdquo;.
                      </p>
                    )}
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </div>
  )
}
