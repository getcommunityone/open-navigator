import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import api from '../lib/api'

interface Document {
  id: string
  state: string
  municipality: string
  title: string
  meeting_date: string
  url: string
  topics: string[]
  sentiment: string
}

export default function Documents() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || '')
  const [page, setPage] = useState(1)
  const [activeFilter, setActiveFilter] = useState('all') // all, meetings, budgets, people, organizations

  useEffect(() => {
    const searchFromUrl = searchParams.get('search')
    if (searchFromUrl) {
      setSearchQuery(searchFromUrl)
    }
  }, [searchParams])

  const { data, isLoading } = useQuery({
    queryKey: ['documents', searchQuery, page],
    queryFn: async () => {
      const response = await api.get('/documents', {
        params: { search: searchQuery, page, limit: 20 },
      })
      return response.data
    },
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    if (searchQuery) {
      setSearchParams({ search: searchQuery })
    } else {
      setSearchParams({})
    }
  }

  return (
    <div className="min-h-screen p-8" style={{ backgroundColor: '#F1F5F9' }}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Meeting Minutes</h1>
          <p className="text-gray-600">
            Search what local governments are discussing - 90,000+ cities, counties, and school districts
          </p>
        </div>

        {/* Search Bar */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <form onSubmit={handleSearch}>
            <div className="relative">
              <input
                type="text"
                placeholder="Search by location, topic, keyword..."
                className="w-full px-4 py-3 pl-12 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <MagnifyingGlassIcon className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" />
              <button
                type="submit"
                className="absolute right-2 top-2 bg-neutral-600 text-white px-6 py-2 rounded-md hover:bg-neutral-700 transition-colors"
              >
                Search
              </button>
            </div>
          </form>
        </div>

        {/* Filter Pills */}
        <div className="bg-white rounded-lg shadow-sm p-4 mb-6 border-b border-gray-200">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setActiveFilter('all')}
              className={`px-4 py-2 rounded-full font-medium transition-colors ${
                activeFilter === 'all'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setActiveFilter('meetings')}
              className={`px-4 py-2 rounded-full font-medium transition-colors ${
                activeFilter === 'meetings'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Meeting Minutes
            </button>
            <button
              onClick={() => setActiveFilter('budgets')}
              className={`px-4 py-2 rounded-full font-medium transition-colors ${
                activeFilter === 'budgets'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Budgets
            </button>
            <button
              onClick={() => setActiveFilter('people')}
              className={`px-4 py-2 rounded-full font-medium transition-colors ${
                activeFilter === 'people'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              People
            </button>
            <button
              onClick={() => setActiveFilter('organizations')}
              className={`px-4 py-2 rounded-full font-medium transition-colors ${
                activeFilter === 'organizations'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Organizations
            </button>
            <button
              onClick={() => setActiveFilter('charities')}
              className={`px-4 py-2 rounded-full font-medium transition-colors ${
                activeFilter === 'charities'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Charities
            </button>
            <button
              onClick={() => setActiveFilter('events')}
              className={`px-4 py-2 rounded-full font-medium transition-colors ${
                activeFilter === 'events'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Events
            </button>
            <button
              className="px-4 py-2 rounded-full font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors flex items-center gap-1"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
              All filters
            </button>
          </div>
        </div>

        {/* Results */}
        <div className="space-y-4">
          {isLoading ? (
            <div className="card">Loading documents...</div>
          ) : (
            <>
              {data?.documents?.map((doc: Document) => (
              <div key={doc.id} className="card hover:shadow-lg transition-shadow">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-900">{doc.title}</h3>
                    <p className="text-sm text-gray-600 mt-1">
                      {doc.municipality}, {doc.state} • {new Date(doc.meeting_date).toLocaleDateString()}
                    </p>
                    
                    <div className="mt-3 flex flex-wrap gap-2">
                      {doc.topics.map((topic) => (
                        <span
                          key={topic}
                          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800"
                        >
                          {topic.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  </div>
                  
                  <a
                    href={doc.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-primary ml-4"
                  >
                    View Document
                  </a>
                </div>
              </div>
            ))}

            {/* Pagination */}
            <div className="flex justify-center gap-2 mt-6">
              <button
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
                className="btn-secondary disabled:opacity-50"
              >
                Previous
              </button>
              <span className="flex items-center px-4">
                Page {page} of {data?.total_pages || 1}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page >= (data?.total_pages || 1)}
                className="btn-secondary disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </>
          )}
        </div>
      </div>
    </div>
  )
}
