import { useState, useRef, useEffect, useMemo } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import {
  MagnifyingGlassIcon,
  XMarkIcon,
  AdjustmentsHorizontalIcon,
  CheckIcon,
  MapPinIcon,
  ArrowLeftIcon
} from '@heroicons/react/24/outline'
import JurisdictionDiscovery from '../components/JurisdictionDiscovery'
import PlaceClusterMap from '../components/PlaceClusterMap'
import StateSelect from '../components/StateSelect'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'

/** A single state group of real indexed places for the browse list. */
interface PlaceGroup {
  stateCode: string
  stateName: string
  places: JurisdictionResult[]
}

const MAX_CITIES_PER_STATE = 12

interface JurisdictionResult {
  type: 'jurisdiction'
  title: string
  subtitle: string
  description: string
  url: string
  score: number
  metadata: {
    level?: string
    state?: string
    state_code?: string
    /** Census GEOID — the stable jurisdiction identifier used for scoped routes. */
    geoid?: string
    type?: string
    county?: string
    population?: number
    website?: string
    youtube_channels?: string[]
    facebook?: string
    twitter?: string
    agenda_portal?: string
    meeting_platform?: string
    completeness?: number
  }
}

interface SearchResponse {
  query: string
  total_results: number
  results: {
    jurisdictions: JurisdictionResult[]
  }
  pagination: {
    page: number
    limit: number
    offset: number
    total_pages: number
    has_next: boolean
    has_prev: boolean
  }
  filters: {
    state?: string
    jurisdiction_levels?: string[]
  }
}

const JURISDICTION_LEVELS = [
  { id: 'city', label: 'Cities', icon: '🏙️' },
  { id: 'county', label: 'Counties', icon: '🏛️' },
  { id: 'state', label: 'States', icon: '🗺️' },
  { id: 'school_district', label: 'School Districts', icon: '🎓' },
  { id: 'special_district', label: 'Special Districts', icon: '⚙️' },
  { id: 'town', label: 'Towns', icon: '🏘️' },
  { id: 'village', label: 'Villages', icon: '🏡' },
] as const

export default function JurisdictionsSearch() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  // "Find a state" filter for the browse chip list (client-side only).
  const [stateFilter, setStateFilter] = useState('')
  const browseRef = useRef<HTMLDivElement>(null)

  // Initialize state from URL params
  const [query, setQuery] = useState(() => searchParams.get('q') || '')
  const [activeQuery, setActiveQuery] = useState(() => searchParams.get('q') || '')
  const [selectedLevels, setSelectedLevels] = useState<string[]>(() => {
    const levelsParam = searchParams.get('levels')
    if (levelsParam) {
      return levelsParam.split(',').filter(l => 
        JURISDICTION_LEVELS.some(jl => jl.id === l)
      )
    }
    return []
  })
  const [selectedState, setSelectedState] = useState(() => searchParams.get('state') || '')
  // `selectedCity` is the APPLIED city (drives the query/URL/chip); `cityDraft`
  // is the textbox value, committed on Enter / Apply so we don't fire a search
  // per keystroke.
  const [selectedCity, setSelectedCity] = useState(() => searchParams.get('city') || '')
  const [cityDraft, setCityDraft] = useState(() => searchParams.get('city') || '')
  const [selectedCounty, setSelectedCounty] = useState(() => searchParams.get('county') || '')
  const [currentPage, setCurrentPage] = useState(() => parseInt(searchParams.get('page') || '1'))
  const [showFilters, setShowFilters] = useState(false)
  const [hasWebsite, setHasWebsite] = useState(false)
  const [hasYouTube, setHasYouTube] = useState(false)
  const [hasMeetingPlatform, setHasMeetingPlatform] = useState(false)
  
  const searchInputRef = useRef<HTMLInputElement>(null)

  // Initialize from URL parameters on mount
  useEffect(() => {
    const queryParam = searchParams.get('q')
    const stateParam = searchParams.get('state')
    const cityParam = searchParams.get('city')
    const countyParam = searchParams.get('county')
    const levelsParam = searchParams.get('levels')
    const pageParam = searchParams.get('page')
    
    if (queryParam) {
      setQuery(queryParam)
      setActiveQuery(queryParam)
    }
    if (stateParam) {
      setSelectedState(stateParam)
    }
    if (cityParam) {
      setSelectedCity(cityParam)
      setCityDraft(cityParam)
    }
    if (countyParam) {
      setSelectedCounty(countyParam)
    }
    if (levelsParam) {
      const levels = levelsParam.split(',').filter(l => 
        JURISDICTION_LEVELS.some(jl => jl.id === l)
      )
      if (levels.length > 0) {
        setSelectedLevels(levels)
      }
    }
    if (pageParam) {
      setCurrentPage(parseInt(pageParam))
    }
  }, [searchParams])

  // Main search results
  const { data: searchResults, isLoading: isSearching, error } = useQuery<SearchResponse>({
    queryKey: ['jurisdictions-search', activeQuery, selectedLevels, selectedState, selectedCity, selectedCounty, currentPage],
    queryFn: async () => {
      // Allow searching with query OR with filters (browse mode)
      if (!activeQuery && !selectedState && !selectedCity && !selectedCounty && !selectedLevels.length) {
        return null
      }
      
      const params: any = {
        types: 'jurisdictions',
        limit: 20,
        page: currentPage
      }
      
      // Query is optional - can browse by state/level/city/county
      if (activeQuery) {
        params.q = activeQuery
      }
      
      if (selectedState) {
        params.state = selectedState
      }
      
      if (selectedCity) {
        params.city = selectedCity
      }
      
      if (selectedCounty) {
        params.county = selectedCounty
      }
      
      if (selectedLevels.length > 0) {
        params.jurisdiction_levels = selectedLevels.join(',')
      }
      
      const response = await api.get('/search/', { params })
      return response.data
    },
    // Enable if we have query OR filters (browse mode)
    enabled: (activeQuery && activeQuery.length >= 2) || selectedState !== '' || selectedCity !== '' || selectedCounty !== '' || selectedLevels.length > 0
  })

  // BROWSE MODE: shown only when there is no active query and no active filters.
  // Pulls a real (capped) sample of indexed places from the same search API the
  // homepage "Browse places" uses, grouped by state.
  const isBrowseMode =
    !activeQuery && !selectedState && !selectedCity && !selectedCounty && selectedLevels.length === 0

  const { data: browseData, isLoading: isBrowseLoading } = useQuery<SearchResponse>({
    queryKey: ['jurisdictions-browse-places'],
    queryFn: async () => {
      // limit is capped at 100 by the /search API; this is the browse sample
      // (real indexed places), grouped by state below — not an exhaustive list.
      const response = await api.get('/search/', {
        params: { types: 'jurisdictions', limit: 100 }
      })
      return response.data
    },
    enabled: isBrowseMode,
    staleTime: 1000 * 60 * 30 // 30 min — this is a slow-moving index
  })

  // Group the real places by state_code, preserving API order within each state.
  const placeGroups = useMemo<PlaceGroup[]>(() => {
    const rows = browseData?.results?.jurisdictions ?? []
    const byState = new Map<string, JurisdictionResult[]>()
    for (const row of rows) {
      const code = row.metadata?.state_code
      // Need both a state and a geoid: the chips link to /jurisdiction/{geoid}/
      // meetings, so a place without a geoid isn't linkable — skip it (no
      // fabricated links).
      if (!code || !row.metadata?.geoid) continue
      if (!byState.has(code)) byState.set(code, [])
      byState.get(code)!.push(row)
    }
    const groups: PlaceGroup[] = []
    for (const [stateCode, places] of byState.entries()) {
      groups.push({
        stateCode,
        stateName: STATE_CODE_TO_NAME[stateCode] || stateCode,
        places: places.slice(0, MAX_CITIES_PER_STATE)
      })
    }
    // Sort alphabetically by full state name.
    groups.sort((a, b) => a.stateName.localeCompare(b.stateName))
    return groups
  }, [browseData])

  // Apply the client-side "find a state" substring filter (on full state name).
  const visibleGroups = useMemo(() => {
    const q = stateFilter.trim().toLowerCase()
    if (!q) return placeGroups
    return placeGroups.filter((g) => g.stateName.toLowerCase().includes(q))
  }, [placeGroups, stateFilter])

  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault()
    // Allow search with query OR just filters (browse mode)
    if (query.trim().length >= 2 || selectedState || selectedCity || selectedCounty || selectedLevels.length > 0) {
      setActiveQuery(query)
      setCurrentPage(1) // Reset to first page on new search
      
      // Update URL
      const params: any = {}
      if (query.trim()) params.q = query
      if (selectedState) params.state = selectedState
      if (selectedCity) params.city = selectedCity
      if (selectedCounty) params.county = selectedCounty
      if (selectedLevels.length > 0) {
        params.levels = selectedLevels.join(',')
      }
      setSearchParams(params)
    }
  }

  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage)
    
    // Update URL — keep every active filter, not just state/levels.
    const params: any = {}
    if (activeQuery) params.q = activeQuery
    if (selectedState) params.state = selectedState
    if (selectedCity) params.city = selectedCity
    if (selectedCounty) params.county = selectedCounty
    if (selectedLevels.length > 0) {
      params.levels = selectedLevels.join(',')
    }
    if (newPage > 1) params.page = newPage.toString()
    setSearchParams(params)

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const toggleLevel = (level: string) => {
    const newLevels = selectedLevels.includes(level)
      ? selectedLevels.filter(l => l !== level)
      : [...selectedLevels, level]
    
    setSelectedLevels(newLevels)
    setCurrentPage(1)

    // Update URL with all current filters (preserve city/county too).
    const params: any = {}
    if (activeQuery) params.q = activeQuery
    if (selectedState) params.state = selectedState
    if (selectedCity) params.city = selectedCity
    if (selectedCounty) params.county = selectedCounty
    if (newLevels.length > 0) {
      params.levels = newLevels.join(',')
    }
    setSearchParams(params)
  }

  const getLevelColor = (level: string) => {
    const colors: Record<string, string> = {
      city: 'bg-blue-100 text-blue-700 border-blue-200',
      county: 'bg-purple-100 text-purple-700 border-purple-200',
      state: 'bg-green-100 text-green-700 border-green-200',
      school_district: 'bg-yellow-100 text-yellow-700 border-yellow-200',
      special_district: 'bg-orange-100 text-orange-700 border-orange-200',
      town: 'bg-teal-100 text-teal-700 border-teal-200',
      village: 'bg-pink-100 text-pink-700 border-pink-200',
    }
    return colors[level] || 'bg-gray-100 text-gray-700 border-gray-200'
  }

  // Badge count on the single "Filters" button — how many filters are engaged.
  const activeFilterCount = [
    selectedState,
    selectedCity,
    selectedCounty,
    selectedLevels.length > 0 ? 'levels' : null,
    hasWebsite ? 'website' : null,
    hasYouTube ? 'youtube' : null,
    hasMeetingPlatform ? 'platform' : null,
  ].filter(Boolean).length

  return (
    <div
      className={`min-h-screen bg-gray-50 transition-[padding] duration-300 ${
        showFilters ? 'md:pr-96' : ''
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 pb-6">
        {/* Back button — very first element on the page */}
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors pt-4 pb-3"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          Back
        </button>

        {/* Header card — title + search, matching Browse Topics/Causes style. */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Places</h1>

          {/* Search Bar + single Filters button on one row (matches the main
              Search page). All filter controls — levels, state, and the advanced
              data-availability toggles — live in the flyout below. */}
          <div className="flex items-stretch gap-3 mt-4">
            <form onSubmit={handleSearch} className="flex flex-1 items-stretch gap-3">
              <div className="relative flex-1">
                <input
                  ref={searchInputRef}
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search for cities, counties, states, school districts..."
                  className="w-full pl-4 pr-12 py-3 rounded-lg border-2 border-gray-200 bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-lg text-gray-900 shadow-sm"
                />

                {query && (
                  <button
                    type="button"
                    onClick={() => {
                      setQuery('')
                      setActiveQuery('')
                      searchInputRef.current?.focus()
                    }}
                    className="absolute right-4 top-3.5 text-gray-400 hover:text-gray-600"
                  >
                    <XMarkIcon className="h-6 w-6" />
                  </button>
                )}
              </div>
              <button
                type="submit"
                aria-label="Search"
                className="flex shrink-0 items-center justify-center rounded-lg bg-primary-600 px-5 text-white transition-colors hover:bg-primary-700"
              >
                <MagnifyingGlassIcon className="h-6 w-6" />
              </button>
            </form>

            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex-shrink-0 flex items-center gap-2 px-3 sm:px-4 py-3 rounded-lg border-2 transition-colors text-sm ${
                showFilters
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-300 text-gray-700 hover:border-gray-400 hover:bg-gray-50'
              }`}
            >
              <AdjustmentsHorizontalIcon className="h-4 w-4 sm:h-5 sm:w-5" />
              <span>Filters</span>
              {activeFilterCount > 0 && (
                <span className="ml-1 px-2 py-0.5 bg-primary-600 text-white text-xs rounded-full">
                  {activeFilterCount}
                </span>
              )}
            </button>
          </div>

          {/* Active Filters Display */}
          {(selectedState || selectedCity || selectedCounty || selectedLevels.length > 0) && (
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              <span className="text-sm text-gray-600">Active filters:</span>
              {selectedState && (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                  State: {selectedState}
                  <button
                    onClick={() => {
                      setSelectedState('')
                      setTimeout(() => handleSearch(), 0)
                    }}
                    className="hover:bg-blue-200 rounded-full p-0.5"
                  >
                    <XMarkIcon className="h-3 w-3" />
                  </button>
                </span>
              )}
              {selectedCity && (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">
                  City: {selectedCity}
                  <button
                    onClick={() => {
                      setSelectedCity('')
                      setCityDraft('')
                      setTimeout(() => handleSearch(), 0)
                    }}
                    className="hover:bg-green-200 rounded-full p-0.5"
                  >
                    <XMarkIcon className="h-3 w-3" />
                  </button>
                </span>
              )}
              {selectedCounty && (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm">
                  County: {selectedCounty}
                  <button
                    onClick={() => {
                      setSelectedCounty('')
                      setTimeout(() => handleSearch(), 0)
                    }}
                    className="hover:bg-amber-200 rounded-full p-0.5"
                  >
                    <XMarkIcon className="h-3 w-3" />
                  </button>
                </span>
              )}
              {selectedLevels.length > 0 && (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm">
                  {selectedLevels.length} Level{selectedLevels.length > 1 ? 's' : ''}
                  <button
                    onClick={() => {
                      setSelectedLevels([])
                      setTimeout(() => handleSearch(), 0)
                    }}
                    className="hover:bg-purple-200 rounded-full p-0.5"
                  >
                    <XMarkIcon className="h-3 w-3" />
                  </button>
                </span>
              )}
            </div>
          )}

          {/* Filters Flyout — levels, state, and advanced data-availability
              filters consolidated into a single right-hand panel, matching the
              main Search page. */}
          {showFilters && (
            <>
              {/* Backdrop — only on mobile, where the panel covers the screen.
                  On md+ the panel docks and the page content (incl. the map)
                  reflows beside it, so we never dim/cover the map there. */}
              <div
                className="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden"
                onClick={() => setShowFilters(false)}
              />

              {/* Sidebar */}
              <div className="fixed right-0 top-0 h-full w-full md:w-96 bg-white shadow-2xl z-50 overflow-y-auto">
                <div className="p-6">
                  {/* Header */}
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-xl font-bold text-gray-900">Filters</h3>
                    <button
                      onClick={() => setShowFilters(false)}
                      className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
                    >
                      <XMarkIcon className="h-6 w-6" />
                    </button>
                  </div>

                  {/* Filters */}
                  <div className="space-y-6">
                    {/* Jurisdiction Levels */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-3">
                        Levels
                      </label>
                      <div className="flex flex-wrap gap-2">
                        {JURISDICTION_LEVELS.map((level) => (
                          <button
                            key={level.id}
                            onClick={() => toggleLevel(level.id)}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border-2 transition-all text-sm ${
                              selectedLevels.includes(level.id)
                                ? `${getLevelColor(level.id)} border-current font-medium shadow-sm`
                                : 'border-gray-300 bg-white text-gray-600 hover:border-gray-400 hover:bg-gray-50'
                            }`}
                          >
                            {selectedLevels.includes(level.id) && (
                              <CheckIcon className="h-4 w-4 flex-shrink-0" />
                            )}
                            <span>{level.icon}</span>
                            <span>{level.label}</span>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* State Filter */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        State
                      </label>
                      <StateSelect
                        value={selectedState}
                        onChange={(code) => {
                          setSelectedState(code)
                          setCurrentPage(1)
                          setTimeout(() => handleSearch(), 0)
                        }}
                      />
                    </div>

                    {/* City Filter — free text (matched ILIKE on city /
                        jurisdiction name server-side). Applied on Enter or via
                        the Apply Filters button so we don't search per keystroke. */}
                    <div>
                      <label htmlFor="places-city-filter" className="block text-sm font-medium text-gray-700 mb-2">
                        City
                      </label>
                      <input
                        id="places-city-filter"
                        type="text"
                        value={cityDraft}
                        onChange={(e) => setCityDraft(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            setSelectedCity(cityDraft.trim())
                            setCurrentPage(1)
                            setTimeout(() => handleSearch(), 0)
                          }
                        }}
                        placeholder="e.g. Tuscaloosa"
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-gray-900 bg-white"
                      />
                    </div>

                    {/* Data Availability Filters */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-3">
                        Data Availability
                      </label>
                      <div className="space-y-3">
                        <label className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer transition-colors">
                          <input
                            type="checkbox"
                            checked={hasWebsite}
                            onChange={(e) => {
                              setHasWebsite(e.target.checked)
                              setCurrentPage(1)
                            }}
                            className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                          />
                          <div className="flex-1">
                            <div className="text-sm font-medium text-gray-900">Has Official Website</div>
                            <div className="text-xs text-gray-500">Show jurisdictions with .gov domains</div>
                          </div>
                        </label>
                        
                        <label className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer transition-colors">
                          <input
                            type="checkbox"
                            checked={hasYouTube}
                            onChange={(e) => {
                              setHasYouTube(e.target.checked)
                              setCurrentPage(1)
                            }}
                            className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                          />
                          <div className="flex-1">
                            <div className="text-sm font-medium text-gray-900">Has YouTube Channel</div>
                            <div className="text-xs text-gray-500">Meeting recordings available</div>
                          </div>
                        </label>
                        
                        <label className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer transition-colors">
                          <input
                            type="checkbox"
                            checked={hasMeetingPlatform}
                            onChange={(e) => {
                              setHasMeetingPlatform(e.target.checked)
                              setCurrentPage(1)
                            }}
                            className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                          />
                          <div className="flex-1">
                            <div className="text-sm font-medium text-gray-900">Has Meeting Platform</div>
                            <div className="text-xs text-gray-500">Legistar, Granicus, etc.</div>
                          </div>
                        </label>
                      </div>
                    </div>

                    {/* Oral Health Focus States */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-3">
                        Quick Filters
                      </label>
                      <button
                        onClick={() => {
                          setSelectedState('')
                          setSelectedLevels(['city'])
                          setTimeout(() => handleSearch(), 0)
                        }}
                        className="w-full px-4 py-2.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors font-medium text-left"
                      >
                        🦷 Oral Health Focus States
                        <div className="text-xs text-blue-600 mt-1">AL, GA, IN, MA, WA, WI cities</div>
                      </button>
                    </div>

                    {/* Population Filter (Placeholder) */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Minimum Population
                      </label>
                      <select
                        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-gray-900 py-2.5"
                        defaultValue="any"
                      >
                        <option value="any">Any Size</option>
                        <option value="10000">10,000+</option>
                        <option value="50000">50,000+</option>
                        <option value="100000">100,000+</option>
                        <option value="500000">500,000+</option>
                        <option value="1000000">1,000,000+</option>
                      </select>
                    </div>
                  </div>

                  {/* Footer Actions */}
                  <div className="mt-8 pt-6 border-t border-gray-200 space-y-3">
                    <button
                      onClick={() => {
                        setSelectedState('')
                        setSelectedCity('')
                        setCityDraft('')
                        setSelectedCounty('')
                        setSelectedLevels([])
                        setHasWebsite(false)
                        setHasYouTube(false)
                        setHasMeetingPlatform(false)
                        setCurrentPage(1)
                        setTimeout(() => handleSearch(), 0)
                      }}
                      className="w-full px-4 py-2.5 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors font-medium"
                    >
                      Clear All Filters
                    </button>
                    <button
                      onClick={() => {
                        setSelectedCity(cityDraft.trim())
                        setCurrentPage(1)
                        setShowFilters(false)
                        setTimeout(() => handleSearch(), 0)
                      }}
                      className="w-full px-4 py-2.5 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors font-medium"
                    >
                      Apply Filters
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Clustered pin map of every indexed place (state/county/city/school
            district levels, each independently filterable). Always shown — it's
            a global explore tool independent of the list filters below, so a
            filtered deep-link (e.g. ?state=AL&city=Tuscaloosa) keeps the map.
            The active state/city/level filters scope and zoom the map live. */}
        <PlaceClusterMap filterState={selectedState} filterCity={selectedCity} filterLevels={selectedLevels} />

        {/* Places browse — state-grouped chips of real indexed places. Shown
            only in browse mode (no active query/filters). Every city is a real
            row from the jurisdictions search API, linked to its place home. */}
        {isBrowseMode && (
          <div ref={browseRef} className="bg-white rounded-lg shadow-sm p-6 mb-6">
            {/* "Find a state" filter */}
            <div className="relative mb-6 max-w-md">
              <MapPinIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                value={stateFilter}
                onChange={(e) => setStateFilter(e.target.value)}
                placeholder="Type to find a state…"
                className="w-full pl-10 pr-10 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 focus:outline-none"
              />
              {stateFilter && (
                <button
                  onClick={() => setStateFilter('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  aria-label="Clear state filter"
                >
                  <XMarkIcon className="h-5 w-5" />
                </button>
              )}
            </div>

            {isBrowseLoading && (
              <div className="text-center py-12">
                <div className="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-primary-500"></div>
                <p className="mt-4 text-gray-600">Loading places…</p>
              </div>
            )}

            {!isBrowseLoading && visibleGroups.length === 0 && (
              <p className="text-center py-12 text-gray-500">
                {placeGroups.length === 0
                  ? 'No places indexed yet.'
                  : `No states match "${stateFilter}".`}
              </p>
            )}

            {!isBrowseLoading && visibleGroups.length > 0 && (
              <div className="space-y-6">
                {visibleGroups.map((group) => (
                  <div key={group.stateCode}>
                    <h2 className="text-lg font-bold text-gray-900 mb-3">{group.stateName}</h2>
                    <div className="flex flex-wrap gap-2">
                      {group.places.map((place) => (
                        <Link
                          key={place.metadata!.geoid as string}
                          to={`/jurisdiction/${encodeURIComponent(place.metadata!.geoid as string)}/meetings`}
                          className="inline-flex items-center px-3 py-1.5 rounded-full bg-primary-50 text-primary-700 text-sm font-medium border border-primary-100 hover:bg-primary-100 hover:border-primary-500 transition-colors"
                        >
                          {place.title}
                        </Link>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Search Results */}
        {(activeQuery || selectedState || selectedLevels.length > 0 || searchResults) && (
          <div>
            {isSearching && (
              <div className="text-center py-12">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
                <p className="mt-4 text-gray-600">Searching...</p>
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
                <p className="text-red-600">Error loading search results. Please try again.</p>
              </div>
            )}

            {searchResults && searchResults.total_results !== undefined && searchResults.pagination && (
              <>
                {/* Results Summary */}
                <div className="mb-6">
                  <h2 className="text-xl font-semibold text-gray-900">
                    {searchResults.query ? (
                      <>
                        {searchResults.total_results.toLocaleString()} jurisdictions for "{searchResults.query}"
                        {searchResults.total_results > 0 && (
                          <span className="text-base font-normal text-gray-600 ml-2">
                            (showing {searchResults.pagination.offset + 1}-
                            {Math.min(searchResults.pagination.offset + searchResults.pagination.limit, searchResults.total_results)})
                          </span>
                        )}
                      </>
                    ) : (
                      <>
                        {searchResults.total_results.toLocaleString()} jurisdictions
                        {searchResults.total_results > 0 && (
                          <span className="text-base font-normal text-gray-600 ml-2">
                            (showing {searchResults.pagination.offset + 1}-
                            {Math.min(searchResults.pagination.offset + searchResults.pagination.limit, searchResults.total_results)})
                          </span>
                        )}
                      </>
                    )}
                  </h2>
                  {selectedState && (
                    <p className="text-sm text-gray-600 mt-1">
                      Filtered by state: {selectedState}
                    </p>
                  )}
                </div>

                {/* Results */}
                <div className="space-y-4">
                  {searchResults.results.jurisdictions.map((result, index) => (
                    <JurisdictionDiscovery
                      key={index}
                      jurisdiction={{
                        jurisdiction_id: result.metadata.geoid,
                        name: result.title,
                        state: result.metadata.state || '',
                        website: result.metadata.website,
                        youtube_channels: result.metadata.youtube_channels,
                        facebook: result.metadata.facebook,
                        twitter: result.metadata.twitter,
                        agenda_portal: result.metadata.agenda_portal,
                        meeting_platform: result.metadata.meeting_platform,
                        completeness: result.metadata.completeness || 0
                      }}
                    />
                  ))}
                </div>

                {/* No Results */}
                {searchResults.total_results === 0 && (
                  <div className="bg-gray-50 border border-gray-200 rounded-lg p-12 text-center">
                    <MapPinIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-xl font-semibold text-gray-900 mb-2">No jurisdictions found</h3>
                    <p className="text-gray-600">
                      Try adjusting your search terms or filters
                    </p>
                  </div>
                )}

                {/* Pagination */}
                {searchResults.total_results > 0 && searchResults.pagination.total_pages > 1 && (
                  <div className="mt-8 flex items-center justify-center gap-2">
                    <button
                      onClick={() => handlePageChange(currentPage - 1)}
                      disabled={!searchResults.pagination.has_prev}
                      className={`px-4 py-2 rounded-lg ${
                        searchResults.pagination.has_prev
                          ? 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                          : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      }`}
                    >
                      Previous
                    </button>
                    
                    <div className="flex items-center gap-2">
                      {Array.from({ length: Math.min(5, searchResults.pagination.total_pages) }, (_, i) => {
                        const pageNum = i + 1
                        return (
                          <button
                            key={pageNum}
                            onClick={() => handlePageChange(pageNum)}
                            className={`px-4 py-2 rounded-lg ${
                              currentPage === pageNum
                                ? 'bg-primary-600 text-white'
                                : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                            }`}
                          >
                            {pageNum}
                          </button>
                        )
                      })}
                    </div>
                    
                    <button
                      onClick={() => handlePageChange(currentPage + 1)}
                      disabled={!searchResults.pagination.has_next}
                      className={`px-4 py-2 rounded-lg ${
                        searchResults.pagination.has_next
                          ? 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                          : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      }`}
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
