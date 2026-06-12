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
import MeetingCardList from '../components/MeetingCardList'

// How many topic pills to surface inline before the rest move to the flyout.
// The API returns topics sorted by transcript_occurrences desc, so the first
// few are the most-discussed.
const TOP_PILL_COUNT = 5

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
  // Place filter carried over from the homepage (e.g. ?state=GA). When present,
  // the catalog is scoped to topics actually discussed in that state.
  const [searchParams] = useSearchParams()
  const stateCode = (searchParams.get('state') || '').trim().toUpperCase() || undefined

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

  const topics = data ?? []

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return topics
    return topics.filter((t) => {
      if (t.name.toLowerCase().includes(q)) return true
      return t.keywords.some((k) => k.toLowerCase().includes(q))
    })
  }, [topics, query])

  // Pill styling for the topic filter row — solid indigo when active.
  const chipClass = (on: boolean) =>
    `inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
      on
        ? 'border-indigo-600 bg-indigo-600 text-white'
        : 'border-gray-200 bg-white text-gray-700 hover:border-indigo-300 hover:text-indigo-700'
    }`

  const listTitle = selectedTopic
    ? `Meetings on ${selectedTopic.name}`
    : `Recent meetings${stateCode ? ` · ${stateCode}` : ''}`

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

        {/* Header card — title + topic filter */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-4">
            Browse Topics{stateCode ? ` · ${stateCode}` : ''}
          </h1>
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter topics or keywords (e.g. housing, transit, climate)…"
              className="w-full px-12 py-3 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-lg text-gray-900"
            />
          </div>
        </div>

        {/* Topic filter pills — pick one to scope the decision cards below. The
            cards render immediately (no click-into-a-separate-view needed). */}
        {isError ? (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Couldn&apos;t load topics.{' '}
            {(error as { message?: string } | undefined)?.message ?? 'Please try again.'}
          </div>
        ) : (
          <div className="mb-6 flex flex-wrap gap-2">
            <button type="button" onClick={() => setSelectedTopic(null)} className={chipClass(selectedTopic === null)}>
              All topics
            </button>
            {isLoading ? (
              <span className="px-2 py-1.5 text-sm text-gray-400">Loading topics…</span>
            ) : (
              filtered.map((topic) => (
                <button
                  key={topic.topic_id}
                  type="button"
                  onClick={() => setSelectedTopic(topic)}
                  className={chipClass(selectedTopic?.topic_id === topic.topic_id)}
                >
                  {topic.name}
                </button>
              ))
            )}
          </div>
        )}

        {/* Meeting cards — meeting-grain, transcript-linked to the topic; each
            meeting drills into its own decisions. Picking a topic scopes this
            list; the `key` remounts it so the new scope applies cleanly. */}
        <MeetingCardList
          key={selectedTopic?.topic_id ?? 'all-topics'}
          topicId={selectedTopic?.topic_id}
          state={stateCode}
          title={listTitle}
        />
      </div>
    </div>
  )
}
