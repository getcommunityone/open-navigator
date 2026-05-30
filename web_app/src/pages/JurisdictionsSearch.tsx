import { useState, useRef, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { 
  MagnifyingGlassIcon, 
  XMarkIcon,
  AdjustmentsHorizontalIcon,
  CheckIcon,
  MapPinIcon
} from '@heroicons/react/24/outline'
import JurisdictionDiscovery from '../components/JurisdictionDiscovery'

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
  const [selectedCity, setSelectedCity] = useState(() => searchParams.get('city') || '')
  const [selectedCounty, setSelectedCounty] = useState(() => searchParams.get('county') || '')
  const [currentPage, setCurrentPage] = useState(() => parseInt(searchParams.get('page') || '1'))
  const [showFilters, setShowFilters] = useState(false)
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false)
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
    
    // Update URL
    const params: any = {}
    if (activeQuery) params.q = activeQuery
    if (selectedState) params.state = selectedState
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
    
    // Update URL with all current filters
    const params: any = {}
    if (activeQuery) params.q = activeQuery
    if (selectedState) params.state = selectedState
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

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-6 pb-6">
        {/* Search Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <MapPinIcon className="h-8 w-8 text-primary-600" />
            <h1 className="text-3xl font-bold text-gray-900">Jurisdiction Search</h1>
          </div>
          <p className="text-gray-600 mb-4">
            Search across 90,000+ cities, counties, states, and school districts
          </p>
          
          {/* Search Bar */}
          <form onSubmit={handleSearch} className="relative">
            <div className="relative">
              <input
                ref={searchInputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search for cities, counties, states, school districts..."
                className="w-full px-12 py-3 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-lg text-gray-900"
              />
              <MagnifyingGlassIcon className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" />
              
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
          </form>

          {/* Filter Bar */}
          <div className="mt-4 flex items-center gap-3 flex-wrap">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg border-2 transition-colors ${
                showFilters 
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-300 text-gray-700 hover:border-gray-400 hover:bg-gray-50'
              }`}
            >
              <AdjustmentsHorizontalIcon className="h-5 w-5" />
              Basic Filters
            </button>

            <button
              onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg border-2 transition-colors ${
                showAdvancedFilters
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-300 text-gray-700 hover:border-gray-400 hover:bg-gray-50'
              }`}
            >
              <AdjustmentsHorizontalIcon className="h-5 w-5" />
              Advanced Filters
              {(hasWebsite || hasYouTube || hasMeetingPlatform) && (
                <span className="ml-1 px-2 py-0.5 bg-primary-600 text-white text-xs rounded-full">
                  {[hasWebsite, hasYouTube, hasMeetingPlatform].filter(Boolean).length}
                </span>
              )}
            </button>

            {/* Jurisdiction Level Pills */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm text-gray-600 font-medium">Levels:</span>
              {JURISDICTION_LEVELS.map((level) => (
                <button
                  key={level.id}
                  onClick={() => toggleLevel(level.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-full border-2 transition-all ${
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

          {/* Advanced Filters Panel */}
          {showFilters && (
            <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* State Filter */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    State
                  </label>
                  <select
                    value={selectedState}
                    onChange={(e) => {
                      setSelectedState(e.target.value)
                      setCurrentPage(1)
                      setTimeout(() => handleSearch(), 0)
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-gray-900 bg-white"
                  >
                    <option value="" className="text-gray-900">All States</option>
                    <option value="AL" className="text-gray-900">Alabama</option>
                    <option value="AK" className="text-gray-900">Alaska</option>
                    <option value="AZ" className="text-gray-900">Arizona</option>
                    <option value="AR" className="text-gray-900">Arkansas</option>
                    <option value="CA" className="text-gray-900">California</option>
                    <option value="CO" className="text-gray-900">Colorado</option>
                    <option value="CT" className="text-gray-900">Connecticut</option>
                    <option value="DE" className="text-gray-900">Delaware</option>
                    <option value="FL" className="text-gray-900">Florida</option>
                    <option value="GA" className="text-gray-900">Georgia</option>
                    <option value="HI" className="text-gray-900">Hawaii</option>
                    <option value="ID" className="text-gray-900">Idaho</option>
                    <option value="IL" className="text-gray-900">Illinois</option>
                    <option value="IN" className="text-gray-900">Indiana</option>
                    <option value="IA" className="text-gray-900">Iowa</option>
                    <option value="KS" className="text-gray-900">Kansas</option>
                    <option value="KY" className="text-gray-900">Kentucky</option>
                    <option value="LA" className="text-gray-900">Louisiana</option>
                    <option value="ME" className="text-gray-900">Maine</option>
                    <option value="MD" className="text-gray-900">Maryland</option>
                    <option value="MA" className="text-gray-900">Massachusetts</option>
                    <option value="MI" className="text-gray-900">Michigan</option>
                    <option value="MN" className="text-gray-900">Minnesota</option>
                    <option value="MS" className="text-gray-900">Mississippi</option>
                    <option value="MO" className="text-gray-900">Missouri</option>
                    <option value="MT" className="text-gray-900">Montana</option>
                    <option value="NE" className="text-gray-900">Nebraska</option>
                    <option value="NV" className="text-gray-900">Nevada</option>
                    <option value="NH" className="text-gray-900">New Hampshire</option>
                    <option value="NJ" className="text-gray-900">New Jersey</option>
                    <option value="NM" className="text-gray-900">New Mexico</option>
                    <option value="NY" className="text-gray-900">New York</option>
                    <option value="NC" className="text-gray-900">North Carolina</option>
                    <option value="ND" className="text-gray-900">North Dakota</option>
                    <option value="OH" className="text-gray-900">Ohio</option>
                    <option value="OK" className="text-gray-900">Oklahoma</option>
                    <option value="OR" className="text-gray-900">Oregon</option>
                    <option value="PA" className="text-gray-900">Pennsylvania</option>
                    <option value="RI" className="text-gray-900">Rhode Island</option>
                    <option value="SC" className="text-gray-900">South Carolina</option>
                    <option value="SD" className="text-gray-900">South Dakota</option>
                    <option value="TN" className="text-gray-900">Tennessee</option>
                    <option value="TX" className="text-gray-900">Texas</option>
                    <option value="UT" className="text-gray-900">Utah</option>
                    <option value="VT" className="text-gray-900">Vermont</option>
                    <option value="VA" className="text-gray-900">Virginia</option>
                    <option value="WA" className="text-gray-900">Washington</option>
                    <option value="WV" className="text-gray-900">West Virginia</option>
                    <option value="WI" className="text-gray-900">Wisconsin</option>
                    <option value="WY" className="text-gray-900">Wyoming</option>
                  </select>
                </div>
              </div>

              {/* Clear All Button */}
              <div className="mt-4">
                <button
                  onClick={() => {
                    setSelectedState('')
                    setSelectedLevels([])
                    setTimeout(() => handleSearch(), 0)
                  }}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
                >
                  Clear All Filters
                </button>
              </div>
            </div>
          )}
          
          {/* Advanced Filters Sidebar */}
          {showAdvancedFilters && (
            <>
              {/* Backdrop */}
              <div 
                className="fixed inset-0 bg-black bg-opacity-50 z-40"
                onClick={() => setShowAdvancedFilters(false)}
              />
              
              {/* Sidebar */}
              <div className="fixed right-0 top-0 h-full w-full md:w-96 bg-white shadow-2xl z-50 overflow-y-auto">
                <div className="p-6">
                  {/* Header */}
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-xl font-bold text-gray-900">Advanced Jurisdiction Filters</h3>
                    <button
                      onClick={() => setShowAdvancedFilters(false)}
                      className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
                    >
                      <XMarkIcon className="h-6 w-6" />
                    </button>
                  </div>

                  {/* Filters */}
                  <div className="space-y-6">
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
                        setHasWebsite(false)
                        setHasYouTube(false)
                        setHasMeetingPlatform(false)
                        setCurrentPage(1)
                      }}
                      className="w-full px-4 py-2.5 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors font-medium"
                    >
                      Clear Advanced Filters
                    </button>
                    <button
                      onClick={() => {
                        setShowAdvancedFilters(false)
                        handleSearch()
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
