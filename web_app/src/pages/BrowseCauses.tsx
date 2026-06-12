import { useMemo, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeftIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { fetchTrendingCauses, type CauseItem } from '../api/trending'

// A human label for each EveryOrg category slug. Anything not listed falls back
// to a title-cased version of the slug itself.
const CATEGORY_LABELS: Record<string, string> = {
  communities: 'Communities & People',
  environment: 'Environment',
  humanitarian: 'Humanitarian',
  health: 'Health',
  justice: 'Justice',
  arts: 'Arts & Culture',
  animals: 'Animals',
  education: 'Education',
  religion: 'Religion',
  general: 'General',
}

const labelFor = (slug: string) =>
  CATEGORY_LABELS[slug] ?? slug.charAt(0).toUpperCase() + slug.slice(1)

export default function BrowseCauses() {
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

  // Group the (filtered) causes by category so the directory reads like the
  // topic taxonomy — a labelled section per category rather than one flat list.
  const grouped = useMemo(() => {
    const byCat = new Map<string, CauseItem[]>()
    for (const c of filtered) {
      const cat = c.category || 'general'
      if (!byCat.has(cat)) byCat.set(cat, [])
      byCat.get(cat)!.push(c)
    }
    return [...byCat.entries()]
      .map(([cat, items]) => ({
        cat,
        label: labelFor(cat),
        items: items.sort((a, b) => a.name.localeCompare(b.name)),
      }))
      .sort((a, b) => a.label.localeCompare(b.label))
  }, [filtered])

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
          Cause directory
        </p>
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Browse Causes</h1>
        <p className="text-gray-500 mb-6 text-sm">
          The causes we track, grouped by category. Pick one to see the local nonprofits, grants, and
          charitable work behind it.
        </p>

        {/* Search box */}
        <div className="relative mb-6 max-w-xl">
          <MagnifyingGlassIcon className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search causes (e.g. environment, health, education)…"
            className="w-full rounded-full border border-gray-300 bg-white py-2.5 pl-10 pr-4 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        {isLoading ? (
          <div className="flex justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-indigo-600" />
          </div>
        ) : isError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700">
            Couldn&apos;t load causes.{' '}
            {(error as { message?: string } | undefined)?.message ?? 'Please try again.'}
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-lg border border-gray-200 bg-white p-10 text-center text-gray-500">
            No causes found{query ? ` for “${query}”` : ''}.
          </div>
        ) : (
          <>
            <p className="mb-4 text-xs text-gray-400">
              {filtered.length} {filtered.length === 1 ? 'cause' : 'causes'} in {grouped.length}{' '}
              {grouped.length === 1 ? 'category' : 'categories'}
              {query ? ` matching “${query}”` : ''}
            </p>
            <div className="space-y-8">
              {grouped.map((group) => (
                <section key={group.cat}>
                  <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {group.label}
                    <span className="ml-2 font-normal text-gray-400">{group.items.length}</span>
                  </h2>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {group.items.map((cause) => (
                      <button
                        key={cause.name}
                        type="button"
                        onClick={() =>
                          navigate(`/search?types=causes&q=${encodeURIComponent(cause.name)}`, {
                            state: { fromHome: true },
                          })
                        }
                        className="flex items-start gap-3 rounded-lg border border-gray-200 bg-white p-5 text-left shadow-sm transition hover:border-indigo-300 hover:shadow"
                      >
                        <span
                          aria-hidden="true"
                          className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-lg bg-indigo-50 text-xl"
                        >
                          {cause.icon}
                        </span>
                        <span className="min-w-0">
                          <span className="block font-semibold text-gray-900">{cause.name}</span>
                          {cause.description ? (
                            <span className="mt-0.5 block text-xs text-gray-500 line-clamp-2">
                              {cause.description}
                            </span>
                          ) : null}
                        </span>
                      </button>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
