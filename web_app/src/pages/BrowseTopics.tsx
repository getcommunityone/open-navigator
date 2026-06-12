import { useMemo, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeftIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { fetchTopics, type TopicSummary } from '../api/topics'

export default function BrowseTopics() {
  const [query, setQuery] = useState('')
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

  const { data, isLoading, isError, error } = useQuery<TopicSummary[]>({
    queryKey: ['topics'],
    queryFn: fetchTopics,
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
        <p className="text-xs uppercase tracking-wide text-indigo-600 font-semibold">
          Policy topic taxonomy
        </p>
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Browse Topics</h1>
        <p className="text-gray-500 mb-6 text-sm">
          The policy topics we track, each with the keywords that map discussion and decisions onto
          it.
        </p>

        {/* Search box */}
        <div className="relative mb-6 max-w-xl">
          <MagnifyingGlassIcon className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search topics or keywords (e.g. housing, transit, climate)…"
            className="w-full rounded-full border border-gray-300 bg-white py-2.5 pl-10 pr-4 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

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
                <div
                  key={topic.topic_id}
                  className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm transition hover:border-indigo-300 hover:shadow"
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
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
