import { useMemo, useState } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeftIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { fetchTopics, type TopicSummary } from '../api/topics'
import DecisionCardList from '../components/DecisionCardList'

export default function BrowseTopics() {
  const [query, setQuery] = useState('')
  // When a topic is picked, the page drills into its meeting-level decision
  // cards (search + filters) instead of the taxonomy grid.
  const [selectedTopic, setSelectedTopic] = useState<TopicSummary | null>(null)
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
            Browse Topics{stateCode ? ` · ${stateCode}` : ''}
          </h1>
          {!selectedTopic && (
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search topics or keywords (e.g. housing, transit, climate)…"
                className="w-full px-12 py-3 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-lg text-gray-900"
              />
            </div>
          )}
        </div>

        {selectedTopic ? (
          /* Drill-down: this topic's meeting-level decision cards. */
          <div>
            <button
              type="button"
              onClick={() => setSelectedTopic(null)}
              className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-indigo-600 hover:text-indigo-800"
            >
              <ArrowLeftIcon className="h-4 w-4" />
              All topics
            </button>
            {selectedTopic.keywords.length > 0 && (
              <div className="mb-5 flex flex-wrap gap-1.5">
                {selectedTopic.keywords.map((kw) => (
                  <span
                    key={kw}
                    className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            )}
            <DecisionCardList
              topicId={selectedTopic.topic_id}
              state={stateCode}
              title={`Decisions on ${selectedTopic.name}`}
            />
          </div>
        ) : (
          <>
        {isLoading ? (
          <div className="flex justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-indigo-600" />
          </div>
        ) : isError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700">
            Couldn&apos;t load topics.{' '}
            {(error as { message?: string } | undefined)?.message ?? 'Please try again.'}
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-lg border border-gray-200 bg-white p-10 text-center text-gray-500">
            No topics found{query ? ` for “${query}”` : ''}.
          </div>
        ) : (
          <>
            <p className="mb-3 text-xs text-gray-400">
              {filtered.length} {filtered.length === 1 ? 'topic' : 'topics'}
              {query ? ` matching “${query}”` : ''}
            </p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((topic) => (
                <button
                  key={topic.topic_id}
                  type="button"
                  onClick={() => setSelectedTopic(topic)}
                  className="rounded-lg border border-gray-200 bg-white p-5 text-left shadow-sm transition hover:border-indigo-300 hover:shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                >
                  <h2 className="mb-3 font-semibold text-gray-900">{topic.name}</h2>
                  {topic.keywords.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {topic.keywords.map((kw) => (
                        <span
                          key={kw}
                          className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700"
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-gray-400">No keywords</span>
                  )}
                </button>
              ))}
            </div>
          </>
        )}
          </>
        )}
      </div>
    </div>
  )
}
