import { useState, useRef, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { withSpan } from '../instrumentation'
import { 
  MagnifyingGlassIcon, 
  UserIcon, 
  CalendarIcon,
  BuildingOfficeIcon,
  HeartIcon,
  XMarkIcon,
  AdjustmentsHorizontalIcon,
  CheckIcon,
  MapPinIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  GlobeAltIcon,
  VideoCameraIcon,
  DocumentTextIcon,
  ChatBubbleBottomCenterTextIcon,
  ScaleIcon,
  BanknotesIcon,
  MegaphoneIcon
} from '@heroicons/react/24/outline'
import { formatCurrency } from '../utils/formatters'

type SearchResultType =
  | 'leader'
  | 'person'
  | 'meeting'
  | 'organization'
  | 'cause'
  | 'bill'
  | 'topic'
  | 'decision'
  | 'grant'
  | 'grant_opportunity'

interface SearchResult {
  type: SearchResultType
  result_type?: SearchResultType
  title: string
  subtitle: string
  description: string
  // Optional: a result with no stable detail key (e.g. an MDM person with a
  // null person_uid) comes back with no url and renders as non-clickable.
  url?: string | null
  score: number
  metadata: Record<string, any>
}

interface SearchResponse {
  query: string
  total_results: number
  type_totals?: {
    leaders?: number
    persons?: number
    meetings: number
    organizations: number
    causes: number
    bills: number
    topics: number
    decisions: number
    jurisdictions: number
    grants?: number
    grant_opportunities?: number
  }
  results: {
    leaders?: SearchResult[]
    persons?: SearchResult[]
    meetings: SearchResult[]
    organizations: SearchResult[]
    causes: SearchResult[]
    bills: SearchResult[]
    topics: SearchResult[]
    decisions: SearchResult[]
    jurisdictions?: SearchResult[]
    grants?: SearchResult[]
    grant_opportunities?: SearchResult[]
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
    ntee_code?: string
    types: string[]
  }
}

// Map legacy request type names to the current /api/search vocabulary so old
// links (?types=contacts / ?types=people / ?types=person) still resolve.
function normalizeTypeAlias(t: string): string {
  if (t === 'contacts' || t === 'leader') return 'leaders'
  if (t === 'people' || t === 'person') return 'persons'
  return t
}

// The result-type vocabulary, shared by the URL whitelist and the Advanced
// Filters "Result types" checkbox group. Previously the pills were a separate
// inline array in the filter bar; that confusing pill row was removed in favor
// of a single source of truth surfaced inside the flyout.
const RESULT_TYPES = [
  { type: 'leaders', label: 'Leaders' },
  { type: 'persons', label: 'People' },
  { type: 'organizations', label: 'Organizations' },
  { type: 'causes', label: 'Causes' },
  { type: 'meetings', label: 'Meetings' },
  { type: 'bills', label: 'Bills' },
  { type: 'topics', label: 'Topics' },
  { type: 'decisions', label: 'Decisions' },
  { type: 'grants', label: 'Grants' },
  { type: 'grant_opportunities', label: 'Grant Opportunities' },
] as const

// Default selection when no ?types= is present (a subset of RESULT_TYPES).
const DEFAULT_RESULT_TYPES = ['leaders', 'persons', 'organizations', 'causes', 'bills', 'topics']

const ALL_RESULT_TYPE_KEYS = RESULT_TYPES.map((t) => t.type) as readonly string[]

// Stable dot color for a cause/NTEE string (small palette, hashed by key).
const CAUSE_DOT_PALETTE = [
  '#2F5D62', // teal
  '#3B82F6', // blue
  '#8B5CF6', // violet
  '#EC4899', // pink
  '#F59E0B', // amber
  '#10B981', // emerald
  '#EF4444', // red
  '#6366F1', // indigo
]

function causeDotColor(key: string): string {
  let hash = 0
  for (let i = 0; i < key.length; i++) {
    hash = (hash * 31 + key.charCodeAt(i)) | 0
  }
  return CAUSE_DOT_PALETTE[Math.abs(hash) % CAUSE_DOT_PALETTE.length]
}

// Format a 9-digit IRS EIN as "XX-XXXXXXX"; leave anything else untouched.
function formatEin(ein: string): string {
  const digits = ein.replace(/\D/g, '')
  return digits.length === 9 ? `${digits.slice(0, 2)}-${digits.slice(2)}` : ein
}

export default function UnifiedSearch() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  // Navigate to a result's detail page, but only when it has a url. Results
  // without a stable detail key (url == null) are rendered non-clickable, so
  // this is a no-op for them instead of routing to a 404.
  //
  // Some result types (e.g. opportunities) carry an EXTERNAL url
  // (https://www.grants.gov/...) that has no matching App.tsx route. Those must
  // open in a new tab instead of being handed to react-router (which would 404).
  const isExternalUrl = (url?: string | null): boolean =>
    !!url && /^https?:\/\//i.test(url)

  const openResult = (url?: string | null) => {
    if (!url) return
    if (isExternalUrl(url)) {
      window.open(url, '_blank', 'noopener,noreferrer')
    } else {
      navigate(url)
    }
  }

  // Initialize state directly from URL params (lazy initializer for performance)
  const [query, setQuery] = useState(() => searchParams.get('q') || '')
  const [activeQuery, setActiveQuery] = useState(() => searchParams.get('q') || '')
  const [selectedEin, setSelectedEin] = useState(() => searchParams.get('ein') || '')
  const [selectedTypes, setSelectedTypes] = useState<string[]>(() => {
    const typesParam = searchParams.get('types')
    if (typesParam) {
      const types = typesParam.split(',').map(t => t.trim()).map(normalizeTypeAlias).filter(t =>
        ALL_RESULT_TYPE_KEYS.includes(t)
      )
      return types.length > 0 ? types : [...DEFAULT_RESULT_TYPES]
    }
    return [...DEFAULT_RESULT_TYPES]
  })
  const [selectedState, setSelectedState] = useState(() => searchParams.get('state') || '')
  const [currentPage, setCurrentPage] = useState(() => parseInt(searchParams.get('page') || '1'))
  const [showFilters, setShowFilters] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [sortBy, setSortBy] = useState(() => searchParams.get('sort') || 'relevance')
  const [nteeCategory, setNteeCategory] = useState(() => searchParams.get('ntee') || '')
  const [includeFullText, setIncludeFullText] = useState(() => searchParams.get('full_text') === 'true')
  const [jurisdictionDetails, setJurisdictionDetails] = useState<any[]>(() => {
    const detailsParam = searchParams.get('jurisdiction_details')
    if (detailsParam) {
      try {
        return JSON.parse(decodeURIComponent(detailsParam))
      } catch (e) {
        return []
      }
    }
    return []
  })
  
  // Derived state: Always have state code available from URL OR jurisdiction details
  const [effectiveState, setEffectiveState] = useState(() => {
    const urlState = searchParams.get('state')
    if (urlState) return urlState
    
    // Extract from jurisdiction details if available
    const detailsParam = searchParams.get('jurisdiction_details')
    if (detailsParam) {
      try {
        const details = JSON.parse(decodeURIComponent(detailsParam))
        // Find state in jurisdiction hierarchy
        for (const j of details) {
          if (j.state) return j.state
          if (j.type === 'State' || j.type === 'state') {
            const stateMap: Record<string, string> = {
              'Massachusetts': 'MA', 'Alabama': 'AL', 'Georgia': 'GA',
              'Washington': 'WA', 'Wisconsin': 'WI', 'California': 'CA',
              'Texas': 'TX', 'New York': 'NY', 'Florida': 'FL'
            }
            return stateMap[j.name] || j.name
          }
        }
      } catch (e) {
        // Ignore parse errors
      }
    }
    return ''
  })
  const [expandedJurisdictions, setExpandedJurisdictions] = useState<Set<number>>(new Set())
  const [expandedOrganizations, setExpandedOrganizations] = useState<Set<string>>(new Set())
  
  // Extract city from jurisdiction details, falling back to a plain ?city=
  // URL param so a Home-built scoped link (e.g. ?city=Tuscaloosa&state=AL)
  // filters results without needing a jurisdiction_details blob.
  const selectedCity = jurisdictionDetails.find(j =>
    j.type === 'City' || j.type === 'city' || j.type === 'Place' || j.type === 'place'
  )?.name || searchParams.get('city') || ''

  // Result types count as "active" once the user narrows away from the full set.
  const typesNarrowed = selectedTypes.length !== RESULT_TYPES.length
  // Badge count on the Filters button — how many advanced filters are engaged.
  const activeFilterCount = [
    selectedState,
    sortBy !== 'relevance' ? 'sorted' : null,
    nteeCategory,
    includeFullText ? 'full text' : null,
    typesNarrowed ? 'types' : null,
  ].filter(Boolean).length
  
  // Debounced query for autocomplete
  const [debouncedQuery, setDebouncedQuery] = useState(query)
  
  const searchInputRef = useRef<HTMLInputElement>(null)
  const searchContainerRef = useRef<HTMLFormElement>(null)

  // Debounce the query for autocomplete (300ms delay)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query)
    }, 300)
    
    return () => clearTimeout(timer)
  }, [query])

  // Close suggestions dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };

    if (showSuggestions) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [showSuggestions]);

  // Initialize from URL parameters on mount
  useEffect(() => {
    const queryParam = searchParams.get('q')
    const stateParam = searchParams.get('state')
    const typesParam = searchParams.get('types')
    const einParam = searchParams.get('ein')
    searchParams.get('page') // Read but don't store
    searchParams.get('sort') // Read but don't store
    searchParams.get('ntee') // Read but don't store
    const jurisdictionDetailsParam = searchParams.get('jurisdiction_details')
    
    if (queryParam) {
      setQuery(queryParam)
      setActiveQuery(queryParam)
    }
    if (einParam) {
      setSelectedEin(einParam)
    }
    if (stateParam) {
      setSelectedState(stateParam)
      setEffectiveState(stateParam)
    } else if (jurisdictionDetailsParam) {
      // Extract state from jurisdiction details
      try {
        const details = JSON.parse(decodeURIComponent(jurisdictionDetailsParam))
        setJurisdictionDetails(details)
        
        // Find and set effective state
        for (const j of details) {
          if (j.state) {
            setEffectiveState(j.state)
            setSelectedState(j.state)
            break
          }
          if (j.type === 'State' || j.type === 'state') {
            const stateMap: Record<string, string> = {
              'Massachusetts': 'MA', 'Alabama': 'AL', 'Georgia': 'GA',
              'Washington': 'WA', 'Wisconsin': 'WI', 'California': 'CA',
              'Texas': 'TX', 'New York': 'NY', 'Florida': 'FL'
            }
            const stateCode = stateMap[j.name] || j.name
            setEffectiveState(stateCode)
            setSelectedState(stateCode)
            break
          }
        }
      } catch (e) {
        setJurisdictionDetails([])
      }
    }
    if (typesParam) {
      const types = typesParam.split(',').map(t => t.trim()).map(normalizeTypeAlias).filter(t =>
        ['leaders', 'persons', 'meetings', 'organizations', 'causes', 'bills', 'topics', 'decisions'].includes(t)
      )
      if (types.length > 0) {
        setSelectedTypes(types)
      }
    } else if (jurisdictionDetailsParam) {
      // Default to showing organizations when landing on a jurisdiction page
      setSelectedTypes(['organizations'])
    }
  }, [searchParams, effectiveState])

  // Preview/autocomplete query for search suggestions (uses debounced query)
  const { data: previewResults, isFetching: isFetchingPreview } = useQuery<SearchResponse>({
    queryKey: ['search-preview', debouncedQuery, effectiveState],
    queryFn: async () => {
      if (!debouncedQuery || debouncedQuery.length < 2) return null
      
      const params: any = {
        q: debouncedQuery,
        types: 'meetings,decisions,causes,leaders,persons,organizations,bills,topics',
        limit: 3
      }
      
      // Use effectiveState - already computed from URL or jurisdiction details
      if (effectiveState) {
        params.state = effectiveState
      }
      
      // Include full text if enabled
      if (includeFullText) {
        params.full_text = 'true'
      }
      
      const response = await api.get('/search/', { params })
      return response.data
    },
    enabled: debouncedQuery.length >= 2 && showSuggestions,
    staleTime: 5000 // Cache for 5 seconds to avoid excessive requests
  })

  // Main search results
  const { data: searchResults, isLoading: isSearching, error } = useQuery<SearchResponse>({
    queryKey: ['unified-search', activeQuery, selectedTypes, selectedState, selectedCity, currentPage, sortBy, nteeCategory, selectedEin, includeFullText],
    queryFn: async () => {
      // Allow searching with query OR with filters (browse mode) OR with EIN
      if (!activeQuery && !selectedState && !selectedTypes.length && !selectedEin) {
        return null
      }
      
      const params: any = {
        types: selectedTypes.join(','),
        limit: 20,
        page: currentPage
      }
      
      // Query is optional - can browse by state/type
      if (activeQuery) {
        params.q = activeQuery
      }
      
      // If EIN is specified, search for it specifically
      if (selectedEin) {
        params.ein = selectedEin
      }
      
      if (selectedState) {
        params.state = selectedState
      }
      
      // Add city filter from jurisdiction details
      if (selectedCity) {
        params.city = selectedCity
      }
      
      // Add sort and filter parameters
      if (sortBy && sortBy !== 'relevance') {
        params.sort = sortBy
      }
      
      if (nteeCategory) {
        params.ntee_code = nteeCategory
      }
      
      // Include full text if enabled
      if (includeFullText) {
        params.full_text = 'true'
      }
      
      // Trace the search data-load. Low-cardinality attributes only — query
      // length/presence and enum-ish facets, never the raw query string.
      return withSpan(
        'search.fetch',
        async () => {
          const response = await api.get('/search/', { params })
          return response.data
        },
        {
          'search.q.length': activeQuery ? activeQuery.length : 0,
          'search.has_query': !!activeQuery,
          'search.has_state': !!selectedState,
          'search.has_ein': !!selectedEin,
          'search.type_count': selectedTypes.length,
          'search.page': currentPage,
        },
      )
    },
    // Enable if we have query OR filters (browse mode) OR EIN
    enabled: (activeQuery && activeQuery.length >= 2) || selectedState !== '' || selectedTypes.length > 0 || selectedEin !== ''
  })

  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault()
    // Allow search with query OR just filters (browse mode)
    if (query.trim().length >= 2 || selectedState || selectedTypes.length > 0) {
      setActiveQuery(query)
      setShowSuggestions(false)
      setCurrentPage(1) // Reset to first page on new search
      
      // Update URL
      const params: any = {}
      if (query.trim()) params.q = query
      if (selectedState) params.state = selectedState
      if (selectedCity) params.city = selectedCity
      if (selectedTypes.length > 0 && selectedTypes.length < 5) {
        params.types = selectedTypes.join(',')
      }
      if (sortBy && sortBy !== 'relevance') params.sort = sortBy
      if (nteeCategory) params.ntee = nteeCategory
      if (includeFullText) params.full_text = 'true'
      setSearchParams(params)
    }
  }

  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage)
    
    // Update URL
    const params: any = {}
    if (activeQuery) params.q = activeQuery
    if (selectedState) params.state = selectedState
    if (selectedCity) params.city = selectedCity
    if (selectedTypes.length > 0 && selectedTypes.length < 5) {
      params.types = selectedTypes.join(',')
    }
    if (sortBy && sortBy !== 'relevance') params.sort = sortBy
    if (nteeCategory) params.ntee = nteeCategory
    if (includeFullText) params.full_text = 'true'
    if (newPage > 1) params.page = newPage.toString()
    setSearchParams(params)
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleViewAllCategory = (category: string) => {
    setActiveQuery(query)
    setShowSuggestions(false)
    setSelectedTypes([category])
    
    // Update URL with all current filters
    const params: any = { q: query }
    if (selectedState) params.state = selectedState
    if (selectedCity) params.city = selectedCity
    params.types = category
    if (sortBy && sortBy !== 'relevance') params.sort = sortBy
    if (nteeCategory) params.ntee = nteeCategory
    if (includeFullText) params.full_text = 'true'
    setSearchParams(params)
  }

  const toggleType = (type: string) => {
    const newTypes = selectedTypes.includes(type)
      ? selectedTypes.filter(t => t !== type)
      : [...selectedTypes, type]
    
    setSelectedTypes(newTypes)
    setCurrentPage(1)
    
    // Update URL with all current filters
    const params: any = {}
    if (activeQuery) params.q = activeQuery
    if (selectedState) params.state = selectedState
    if (selectedCity) params.city = selectedCity
    if (newTypes.length > 0 && newTypes.length < 5) {
      params.types = newTypes.join(',')
    }
    if (sortBy && sortBy !== 'relevance') params.sort = sortBy
    if (nteeCategory) params.ntee = nteeCategory
    setSearchParams(params)
  }

  const toggleJurisdictionExpansion = (index: number) => {
    setExpandedJurisdictions(prev => {
      const newSet = new Set(prev)
      if (newSet.has(index)) {
        newSet.delete(index)
      } else {
        newSet.add(index)
      }
      return newSet
    })
  }

  const toggleOrganizationExpansion = (ein: string) => {
    setExpandedOrganizations(prev => {
      const newSet = new Set(prev)
      if (newSet.has(ein)) {
        newSet.delete(ein)
      } else {
        newSet.add(ein)
      }
      return newSet
    })
  }

  // Auto-expand organization when EIN is specified in URL
  useEffect(() => {
    if (selectedEin && searchResults?.results?.organizations) {
      // Check if the organization with this EIN is in the results
      const hasOrg = searchResults.results.organizations.some(
        (org: any) => org.metadata?.ein === selectedEin
      )
      if (hasOrg) {
        setExpandedOrganizations(new Set([selectedEin]))
      }
    }
  }, [selectedEin, searchResults])

  const getTypeIcon = (type: string) => {
    // Handle both singular and plural forms
    const normalizedType = type.replace(/s$/, '')
    
    switch (normalizedType) {
      case 'person':
      case 'leader':
        return <UserIcon className="h-5 w-5" />
      case 'meeting':
        return <CalendarIcon className="h-5 w-5" />
      case 'organization':
        return <BuildingOfficeIcon className="h-5 w-5" />
      case 'cause':
        return <HeartIcon className="h-5 w-5" />
      case 'bill':
        return <DocumentTextIcon className="h-5 w-5" />
      case 'topic':
        return <ChatBubbleBottomCenterTextIcon className="h-5 w-5" />
      case 'decision':
        return <ScaleIcon className="h-5 w-5" />
      case 'grant':
        return <BanknotesIcon className="h-5 w-5" />
      // 'grant_opportunities' normalizes to 'grant_opportunitie' (trailing 's' stripped);
      // match both the singular result type and the de-pluralized facet name.
      case 'grant_opportunity':
      case 'grant_opportunitie':
        return <MegaphoneIcon className="h-5 w-5" />
      case 'jurisdiction':
        return <MapPinIcon className="h-5 w-5" />
      default:
        return null
    }
  }

  const getTypeColor = (type: string) => {
    // Handle both singular and plural forms
    const normalizedType = type.replace(/s$/, '')
    
    switch (normalizedType) {
      case 'leader':
        return 'bg-blue-100 text-blue-700 border-blue-200'
      case 'person':
        return 'bg-sky-100 text-sky-700 border-sky-200'
      case 'meeting':
        return 'bg-green-100 text-green-700 border-green-200'
      case 'organization':
        return 'bg-purple-100 text-purple-700 border-purple-200'
      case 'cause':
        return 'bg-pink-100 text-pink-700 border-pink-200'
      case 'bill':
        return 'bg-indigo-100 text-indigo-700 border-indigo-200'
      case 'topic':
        return 'bg-teal-100 text-teal-700 border-teal-200'
      case 'decision':
        return 'bg-amber-100 text-amber-700 border-amber-200'
      case 'grant':
        return 'bg-emerald-100 text-emerald-700 border-emerald-200'
      case 'grant_opportunity':
      case 'grant_opportunitie':
        return 'bg-rose-100 text-rose-700 border-rose-200'
      case 'jurisdiction':
        return 'bg-orange-100 text-orange-700 border-orange-200'
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200'
    }
  }

  const ResultCard = ({ result }: { result: SearchResult }) => {
    const resultType = result.result_type ?? result.type
    return (
    <div
      className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow"
    >
      <div className="flex items-start gap-3">
        {/* Leaders / officials show their photo (or a letter avatar) in the
            left slot where the generic type icon would otherwise sit. */}
        {resultType === 'leader' ? (
          <div className="relative w-12 h-12 flex-shrink-0">
            {result.metadata?.photo_url ? (
              <img
                src={result.metadata.photo_url}
                alt={result.title}
                className="w-12 h-12 rounded-full object-cover bg-gray-100 border border-gray-200"
                onError={(e) => {
                  e.currentTarget.style.display = 'none'
                  const fallback = e.currentTarget.nextElementSibling as HTMLElement | null
                  if (fallback) fallback.style.display = 'flex'
                }}
              />
            ) : null}
            <div
              className="w-12 h-12 rounded-full items-center justify-center text-white text-lg font-bold"
              style={{
                backgroundColor: '#2F5D62',
                display: result.metadata?.photo_url ? 'none' : 'flex',
              }}
            >
              {result.title.charAt(0)}
            </div>
          </div>
        ) : (
          <div className={`p-2 rounded-lg border ${getTypeColor(resultType)}`}>
            {getTypeIcon(resultType)}
          </div>
        )}

        <div className="flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              {/* External-url results (e.g. opportunities → grants.gov) render
                  the title as a real anchor that opens in a new tab, since the
                  url is not an internal App.tsx route. Internal results keep the
                  click-to-route behavior via openResult(). */}
              {isExternalUrl(result.url) ? (
                <a
                  href={result.url as string}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="font-semibold text-gray-900 mb-1 inline-flex items-center gap-1 cursor-pointer hover:text-blue-600"
                >
                  {result.title}
                  <span aria-hidden="true" className="text-xs text-gray-400">↗</span>
                </a>
              ) : (
                <h3
                  onClick={() => openResult(result.url)}
                  className={`font-semibold text-gray-900 mb-1 ${
                    result.url ? 'cursor-pointer hover:text-blue-600' : ''
                  }`}
                >
                  {result.title}
                </h3>
              )}
              <p className="text-sm text-gray-600 mb-2">{result.subtitle}</p>
            </div>
            
            {/* Logo for organizations */}
            {result.type === 'organization' && (
              result.metadata?.logo_url ? (
                <img 
                  src={result.metadata.logo_url} 
                  alt={result.title}
                  className="w-12 h-12 rounded object-contain flex-shrink-0 bg-gray-100 border border-gray-200"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                    const fallback = e.currentTarget.nextElementSibling as HTMLElement | null
                    if (fallback) fallback.style.display = 'flex'
                  }}
                />
              ) : null
            )}
            {result.type === 'organization' && (
              <div
                className="w-12 h-12 rounded flex items-center justify-center text-white text-lg font-bold flex-shrink-0"
                style={{
                  backgroundColor: '#52796F',
                  display: result.metadata?.logo_url ? 'none' : 'flex'
                }}
              >
                {result.title.charAt(0)}
              </div>
            )}

          </div>
          
          <p className="text-sm text-gray-500 line-clamp-2 mb-2">{result.description}</p>
          
          {/* Mission statement for organizations */}
          {result.type === 'organization' && result.metadata?.mission && (
            <div className="mt-2 mb-2 p-3 bg-blue-50 border-l-4 border-blue-400 rounded">
              <p className="text-sm text-gray-700 italic">
                <span className="font-semibold text-blue-900">Mission: </span>
                {result.metadata.mission}
              </p>
            </div>
          )}
          
          {/* Website link for organizations */}
          {result.type === 'organization' && result.metadata?.website && (
            <a
              href={result.metadata.website}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-sm text-blue-600 hover:text-blue-800 hover:underline inline-flex items-center gap-1 mb-2"
            >
              🔗 {result.metadata.website}
            </a>
          )}
          
          {/* Additional metadata for organizations */}
          {result.type === 'organization' && result.metadata && (
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              {result.metadata.ein && (
                <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded">
                  EIN: {result.metadata.ein}
                </span>
              )}
              {result.metadata.revenue && result.metadata.revenue > 0 && (
                <span className="px-2 py-1 bg-green-100 text-green-700 rounded">
                  💰 Revenue: {formatCurrency(result.metadata.revenue)}
                  {result.metadata.tax_year && ` (${result.metadata.tax_year})`}
                </span>
              )}
              {result.metadata.assets && result.metadata.assets > 0 && (
                <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded">
                  📊 Assets: {formatCurrency(result.metadata.assets)}
                  {result.metadata.tax_year && ` (${result.metadata.tax_year})`}
                </span>
              )}
              {result.metadata.causes && result.metadata.causes.length > 0 && (
                <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded">
                  🏷️ {result.metadata.causes.slice(0, 3).join(', ')}
                </span>
              )}
            </div>
          )}
          
          {/* Expandable details for organizations */}
          {result.type === 'organization' && result.metadata?.ein && (
            <div className="mt-3">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  toggleOrganizationExpansion(result.metadata.ein)
                }}
                className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 font-medium"
              >
                {expandedOrganizations.has(result.metadata.ein) ? (
                  <ChevronUpIcon className="h-4 w-4" />
                ) : (
                  <ChevronDownIcon className="h-4 w-4" />
                )}
                {expandedOrganizations.has(result.metadata.ein) ? 'Hide' : 'Show'} Details
              </button>
              
              {expandedOrganizations.has(result.metadata.ein) && (
                <div className="mt-3 space-y-3 border-t pt-3">
                  {/* Financials Section */}
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1">
                      💰 Financial Information
                      {result.metadata.tax_year && (
                        <span className="text-xs text-gray-500 font-normal">(Tax Year {result.metadata.tax_year})</span>
                      )}
                    </h4>
                    
                    {/* Check if ANY financial data exists */}
                    {!result.metadata.revenue && !result.metadata.assets && !result.metadata.income ? (
                      <div className="bg-amber-50 p-4 rounded border border-amber-200 text-sm">
                        <p className="text-amber-800 mb-2">
                          <span className="font-semibold">📊 Form 990 data not yet available</span>
                        </p>
                        <p className="text-amber-700 text-xs">
                          Financial information from IRS Form 990 filings is being enriched. 
                          Check back later or visit{' '}
                          <a 
                            href={`https://projects.propublica.org/nonprofits/organizations/${result.metadata.ein}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="underline hover:text-amber-900"
                          >
                            ProPublica Nonprofit Explorer
                          </a>
                          {' '}for current data.
                        </p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                        <div className="bg-green-50 p-3 rounded border border-green-200">
                          <div className="text-xs text-green-700 font-medium mb-1">Total Revenue</div>
                          <div className="text-lg font-bold text-green-900">
                            {result.metadata.revenue !== null && result.metadata.revenue !== undefined 
                              ? formatCurrency(result.metadata.revenue) 
                              : <span className="text-sm text-gray-500">Pending</span>}
                          </div>
                        </div>
                        <div className="bg-blue-50 p-3 rounded border border-blue-200">
                          <div className="text-xs text-blue-700 font-medium mb-1">Total Assets</div>
                          <div className="text-lg font-bold text-blue-900">
                            {result.metadata.assets !== null && result.metadata.assets !== undefined 
                              ? formatCurrency(result.metadata.assets) 
                              : <span className="text-sm text-gray-500">Pending</span>}
                          </div>
                        </div>
                        <div className="bg-purple-50 p-3 rounded border border-purple-200">
                          <div className="text-xs text-purple-700 font-medium mb-1">Net Income</div>
                          <div className="text-lg font-bold text-purple-900">
                            {result.metadata.income !== null && result.metadata.income !== undefined 
                              ? formatCurrency(result.metadata.income) 
                              : <span className="text-sm text-gray-500">Pending</span>}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* Board Members Section - Placeholder */}
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1">
                      👥 Board Members
                    </h4>
                    <div className="bg-gray-50 p-3 rounded border border-gray-200 text-sm text-gray-600">
                      Board member information coming soon
                    </div>
                  </div>
                  
                  {/* Grants Section - Placeholder */}
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1">
                      📜 Recent Grants
                    </h4>
                    <div className="bg-gray-50 p-3 rounded border border-gray-200 text-sm text-gray-600">
                      Grant information coming soon
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Grant-specific metadata badges (amount, grantor location, tax year) */}
          {resultType === 'grant' && result.metadata && (
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              {result.metadata.amount !== null && result.metadata.amount !== undefined && (
                <span className="px-2 py-1 bg-emerald-100 text-emerald-700 rounded">
                  💰 {formatCurrency(result.metadata.amount)}
                </span>
              )}
              {(result.metadata.city || result.metadata.state_code) && (
                <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded">
                  📍 {[result.metadata.city, result.metadata.state_code].filter(Boolean).join(', ')}
                </span>
              )}
              {result.metadata.tax_year && (
                <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded">
                  📅 Tax Year {result.metadata.tax_year}
                </span>
              )}
              {result.metadata.source_url && (
                <a
                  href={result.metadata.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="px-2 py-1 bg-gray-100 text-blue-600 hover:text-blue-800 hover:underline rounded inline-flex items-center gap-1"
                >
                  🔗 Source
                </a>
              )}
            </div>
          )}

          {/* Opportunity-specific metadata badges (federal grant opportunities
              from Grants.gov — distinct from historical 990 grantmaking above). */}
          {resultType === 'grant_opportunity' && result.metadata && (
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              {result.metadata.opp_status && (
                <span
                  className={`px-2 py-1 rounded ${
                    result.metadata.is_open
                      ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-700'
                  }`}
                >
                  {result.metadata.is_open ? '🟢' : '⚪'} {String(result.metadata.opp_status).charAt(0).toUpperCase() + String(result.metadata.opp_status).slice(1)}
                </span>
              )}
              {result.metadata.agency_name && (
                <span className="px-2 py-1 bg-rose-100 text-rose-700 rounded">
                  🏛️ {result.metadata.agency_name}
                </span>
              )}
              {result.metadata.opportunity_number && (
                <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded">
                  #{result.metadata.opportunity_number}
                </span>
              )}
              {result.metadata.close_date && (
                <span className="px-2 py-1 bg-amber-100 text-amber-700 rounded">
                  📅 Closes {result.metadata.close_date}
                </span>
              )}
              {result.metadata.aln && (
                <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded">
                  ALN {result.metadata.aln}
                </span>
              )}
              {result.metadata.external_url && (
                <a
                  href={result.metadata.external_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="px-2 py-1 bg-gray-100 text-blue-600 hover:text-blue-800 hover:underline rounded inline-flex items-center gap-1"
                >
                  🔗 View on Grants.gov
                </a>
              )}
            </div>
          )}

          {/* Type badge */}
          <div className="mt-2">
            <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getTypeColor(resultType)}`}>
              {getTypeIcon(resultType)}
              {resultType.charAt(0).toUpperCase() + resultType.slice(1)}
            </span>
          </div>
        </div>
      </div>
    </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-6 pb-6">
        {/* Search Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-4">Search</h1>
          
          {/* Search Bar */}
          <form onSubmit={handleSearch} className="relative" ref={searchContainerRef}>
            <div className="relative">
              <input
                ref={searchInputRef}
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setShowSuggestions(true)
                }}
                onFocus={() => setShowSuggestions(true)}
                placeholder="Search people, meetings, organizations, bills, topics, decisions, causes..."
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
            
            {/* Rich Preview Dropdown with Grouped Results */}
            {showSuggestions && query.length >= 2 && (
              <div className="absolute z-10 w-full mt-2 bg-white border border-gray-200 rounded-lg shadow-xl max-h-96 overflow-y-auto">
                
                {/* Loading State */}
                {(isFetchingPreview || query !== debouncedQuery) && (
                  <div className="px-4 py-8 text-center">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mb-2"></div>
                    <p className="text-sm text-gray-600">Searching...</p>
                  </div>
                )}
                
                {/* Results */}
                {!isFetchingPreview && query === debouncedQuery && previewResults && previewResults.total_results > 0 && (
                  <>
                {/* Meetings Section */}
                {previewResults.results.meetings && previewResults.results.meetings.length > 0 && (
                  <div className="border-b border-gray-200">
                    <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CalendarIcon className="h-4 w-4 text-gray-500" />
                        <span className="text-xs font-semibold text-gray-700 uppercase">Meetings</span>
                      </div>
                      <button
                        onClick={() => handleViewAllCategory('meetings')}
                        className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                      >
                        View All
                      </button>
                    </div>
                    {previewResults.results.meetings.slice(0, 3).map((result, idx) => (
                      <button
                        key={idx}
                        onClick={() => openResult(result.url)}
                        className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                      >
                        <CalendarIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-gray-900 truncate">{result.title}</div>
                          <div className="text-sm text-gray-600 truncate">{result.subtitle}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* Decisions Section */}
                {previewResults.results.decisions && previewResults.results.decisions.length > 0 && (
                  <div className="border-b border-gray-200">
                    <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ScaleIcon className="h-4 w-4 text-gray-500" />
                        <span className="text-xs font-semibold text-gray-700 uppercase">Decisions</span>
                      </div>
                      <button
                        onClick={() => handleViewAllCategory('decisions')}
                        className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                      >
                        View All
                      </button>
                    </div>
                    {previewResults.results.decisions.slice(0, 3).map((result, idx) => (
                      <button
                        key={idx}
                        onClick={() => openResult(result.url)}
                        className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                      >
                        <ScaleIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-gray-900 truncate">{result.title}</div>
                          <div className="text-sm text-gray-600 truncate">{result.subtitle}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* Causes Section */}
                {previewResults.results.causes.length > 0 && (
                  <div className="border-b border-gray-200">
                    <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <HeartIcon className="h-4 w-4 text-gray-500" />
                        <span className="text-xs font-semibold text-gray-700 uppercase">Causes</span>
                      </div>
                      {previewResults.results.causes.length > 0 && (
                        <button
                          onClick={() => handleViewAllCategory('causes')}
                          className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                        >
                          View All
                        </button>
                      )}
                    </div>
                    {previewResults.results.causes.slice(0, 3).map((result, idx) => (
                      <button
                        key={idx}
                        onClick={() => openResult(result.url)}
                        className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                      >
                        <HeartIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-gray-900 truncate">{result.title}</div>
                          <div className="text-sm text-gray-600 truncate">{result.subtitle}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* Leaders Section (government officials) */}
                {(previewResults.results.leaders ?? []).length > 0 && (
                  <div className="border-b border-gray-200">
                    <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <UserIcon className="h-4 w-4 text-gray-500" />
                        <span className="text-xs font-semibold text-gray-700 uppercase">Leaders</span>
                      </div>
                      <button
                        onClick={() => handleViewAllCategory('leaders')}
                        className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                      >
                        View All
                      </button>
                    </div>
                    {(previewResults.results.leaders ?? []).slice(0, 3).map((result, idx) => (
                      <button
                        key={idx}
                        onClick={() => openResult(result.url)}
                        className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                      >
                        <UserIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-gray-900 truncate">{result.title}</div>
                          <div className="text-sm text-gray-600 truncate">
                            {[result.metadata?.title, result.metadata?.jurisdiction]
                              .filter(Boolean)
                              .join(' – ') || result.subtitle}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* People Section (real people incl. residents/homeowners) */}
                {(previewResults.results.persons ?? []).length > 0 && (
                  <div className="border-b border-gray-200">
                    <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <UserIcon className="h-4 w-4 text-gray-500" />
                        <span className="text-xs font-semibold text-gray-700 uppercase">People</span>
                      </div>
                      <button
                        onClick={() => handleViewAllCategory('persons')}
                        className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                      >
                        View All
                      </button>
                    </div>
                    {(previewResults.results.persons ?? []).slice(0, 3).map((result, idx) => (
                      <button
                        key={idx}
                        onClick={() => openResult(result.url)}
                        className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                      >
                        <UserIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-gray-900 truncate">{result.title}</div>
                          <div className="text-sm text-gray-600 truncate">{result.subtitle}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* Organizations Section */}
                {previewResults.results.organizations.length > 0 && (
                  <div>
                    <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <BuildingOfficeIcon className="h-4 w-4 text-gray-500" />
                        <span className="text-xs font-semibold text-gray-700 uppercase">Organizations</span>
                      </div>
                      {previewResults.results.organizations.length > 0 && (
                        <button
                          onClick={() => handleViewAllCategory('organizations')}
                          className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                        >
                          View All
                        </button>
                      )}
                    </div>
                    {previewResults.results.organizations.slice(0, 3).map((result, idx) => (
                      <button
                        key={idx}
                        onClick={() => openResult(result.url)}
                        className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors last:rounded-b-lg"
                      >
                        {/* Logo with fallback */}
                        {result.metadata?.logo_url ? (
                          <img 
                            src={result.metadata.logo_url} 
                            alt={result.title}
                            className="h-10 w-10 rounded object-contain flex-shrink-0 bg-gray-100 border border-gray-200"
                            onError={(e) => {
                              e.currentTarget.style.display = 'none'
                              const fallback = e.currentTarget.nextElementSibling as HTMLElement | null
                              if (fallback) fallback.style.display = 'flex'
                            }}
                          />
                        ) : null}
                        <div 
                          className="h-10 w-10 rounded flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
                          style={{ 
                            backgroundColor: '#52796F',
                            display: result.metadata?.logo_url ? 'none' : 'flex'
                          }}
                        >
                          {result.title.charAt(0)}
                        </div>
                        
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-gray-900 truncate">{result.title}</div>
                          <div className="text-sm text-gray-600 truncate">{result.subtitle}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* Bills Section */}
                {previewResults.results.bills && previewResults.results.bills.length > 0 && (
                  <div className="border-b border-gray-200">
                    <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <DocumentTextIcon className="h-4 w-4 text-gray-500" />
                        <span className="text-xs font-semibold text-gray-700 uppercase">Bills</span>
                      </div>
                      {previewResults.results.bills.length > 0 && (
                        <button
                          onClick={() => handleViewAllCategory('bills')}
                          className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                        >
                          View All
                        </button>
                      )}
                    </div>
                    {previewResults.results.bills.slice(0, 3).map((result, idx) => (
                      <button
                        key={idx}
                        onClick={() => openResult(result.url)}
                        className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                      >
                        <DocumentTextIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-gray-900 truncate">{result.title}</div>
                          <div className="text-sm text-gray-600 truncate">{result.subtitle}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* Topics Section */}
                {previewResults.results.topics && previewResults.results.topics.length > 0 && (
                  <div className="border-b border-gray-200">
                    <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ChatBubbleBottomCenterTextIcon className="h-4 w-4 text-gray-500" />
                        <span className="text-xs font-semibold text-gray-700 uppercase">Topics</span>
                      </div>
                      {previewResults.results.topics.length > 0 && (
                        <button
                          onClick={() => handleViewAllCategory('topics')}
                          className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                        >
                          View All
                        </button>
                      )}
                    </div>
                    {previewResults.results.topics.slice(0, 3).map((result, idx) => (
                      <button
                        key={idx}
                        onClick={() => openResult(result.url)}
                        className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                      >
                        <ChatBubbleBottomCenterTextIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-gray-900 truncate">{result.title}</div>
                          <div className="text-sm text-gray-600 truncate">{result.subtitle}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* Footer with total results */}
                <div className="px-4 py-2 bg-gray-50 text-center border-t border-gray-200">
                  <button
                    onClick={() => handleSearch()}
                    className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                  >
                    See all {previewResults.total_results} results →
                  </button>
                </div>
                  </>
                )}
                
                {/* No Results State */}
                {!isFetchingPreview && query === debouncedQuery && previewResults && previewResults.total_results === 0 && (
                  <div className="px-4 py-8 text-center">
                    <p className="text-gray-600">No results found for "{query}"</p>
                    <p className="text-sm text-gray-500 mt-1">Try a different search term</p>
                  </div>
                )}
              </div>
            )}
          </form>

          {/* Filter Bar — a single entry point into Advanced Filters. The old
              type-selection pill row lived here; it was confusing, so result-type
              selection now lives inside the flyout alongside the other filters. */}
          <div className="mt-4 flex items-center gap-2 sm:gap-3 flex-wrap">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-lg border-2 transition-colors text-sm ${
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
          {(selectedState || selectedCity || sortBy !== 'relevance' || nteeCategory || jurisdictionDetails.length > 0 || includeFullText) && (
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
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                  City: {selectedCity}
                  <button
                    onClick={() => {
                      const params = new URLSearchParams(window.location.search)
                      params.delete('city')
                      setSearchParams(params)
                    }}
                    className="hover:bg-blue-200 rounded-full p-0.5"
                  >
                    <XMarkIcon className="h-3 w-3" />
                  </button>
                </span>
              )}
              {jurisdictionDetails.length > 0 && (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-teal-100 text-teal-800 rounded-full text-sm">
                  <MapPinIcon className="h-3 w-3" />
                  {jurisdictionDetails.length} Jurisdictions
                  <button
                    onClick={() => {
                      setJurisdictionDetails([])
                      const params = new URLSearchParams(window.location.search)
                      params.delete('jurisdiction_details')
                      setSearchParams(params)
                    }}
                    className="hover:bg-teal-200 rounded-full p-0.5"
                  >
                    <XMarkIcon className="h-3 w-3" />
                  </button>
                </span>
              )}
              {sortBy !== 'relevance' && (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm">
                  Sort: {
                    sortBy === 'name-asc' ? 'Name A-Z' :
                    sortBy === 'name-desc' ? 'Name Z-A' :
                    sortBy === 'revenue-desc' ? 'Revenue ↓' :
                    sortBy === 'revenue-asc' ? 'Revenue ↑' :
                    sortBy === 'assets-desc' ? 'Assets ↓' :
                    sortBy === 'assets-asc' ? 'Assets ↑' : sortBy
                  }
                  <button
                    onClick={() => {
                      setSortBy('relevance')
                      setTimeout(() => handleSearch(), 0)
                    }}
                    className="hover:bg-purple-200 rounded-full p-0.5"
                  >
                    <XMarkIcon className="h-3 w-3" />
                  </button>
                </span>
              )}
              {nteeCategory && (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">
                  Category: {nteeCategory}
                  <button
                    onClick={() => {
                      setNteeCategory('')
                      setTimeout(() => handleSearch(), 0)
                    }}
                    className="hover:bg-green-200 rounded-full p-0.5"
                  >
                    <XMarkIcon className="h-3 w-3" />
                  </button>
                </span>
              )}
              {includeFullText && (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm">
                  <DocumentTextIcon className="h-3 w-3" />
                  Full text
                  <button
                    onClick={() => {
                      setIncludeFullText(false)
                      setTimeout(() => handleSearch(), 0)
                    }}
                    className="hover:bg-amber-200 rounded-full p-0.5"
                  >
                    <XMarkIcon className="h-3 w-3" />
                  </button>
                </span>
              )}
            </div>
          )}

          {/* Advanced Filters Flyout */}
          {showFilters && (
            <>
              {/* Backdrop */}
              <div 
                className="fixed inset-0 bg-black bg-opacity-50 z-40"
                onClick={() => setShowFilters(false)}
              />
              
              {/* Flyout Sidebar */}
              <div className="fixed right-0 top-0 h-full w-full md:w-96 bg-white shadow-2xl z-50 overflow-y-auto">
                <div className="p-6">
                  {/* Header */}
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-xl font-bold text-gray-900">Advanced Filters</h3>
                    <button
                      onClick={() => setShowFilters(false)}
                      className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
                    >
                      <XMarkIcon className="h-6 w-6" />
                    </button>
                  </div>

                  {/* Filters */}
                  <div className="space-y-6">
                {/* Result Types — replaces the old pill row. Pick which kinds of
                    results to include. */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">
                      Result types
                    </label>
                    <div className="flex items-center gap-3 text-xs">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedTypes([...ALL_RESULT_TYPE_KEYS])
                          setCurrentPage(1)
                          setTimeout(() => handleSearch(), 0)
                        }}
                        className="text-primary-600 hover:text-primary-700 font-medium"
                      >
                        Select all
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedTypes([...DEFAULT_RESULT_TYPES])
                          setCurrentPage(1)
                          setTimeout(() => handleSearch(), 0)
                        }}
                        className="text-gray-500 hover:text-gray-700 font-medium"
                      >
                        Reset
                      </button>
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    {RESULT_TYPES.map(({ type, label }) => (
                      <label
                        key={type}
                        className="flex items-center gap-2 cursor-pointer group py-1"
                      >
                        <input
                          type="checkbox"
                          checked={selectedTypes.includes(type)}
                          onChange={() => toggleType(type)}
                          className="h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-2 focus:ring-primary-500 cursor-pointer"
                        />
                        <span className="text-gray-500 group-hover:text-gray-700">
                          {getTypeIcon(type)}
                        </span>
                        <span className="text-sm text-gray-700 group-hover:text-gray-900">
                          {label}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

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
                    <option value="GA" className="text-gray-900">Georgia</option>
                    <option value="MA" className="text-gray-900">Massachusetts</option>
                    <option value="WA" className="text-gray-900">Washington</option>
                    <option value="WI" className="text-gray-900">Wisconsin</option>
                  </select>
                </div>

                {/* Sort By */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Sort By
                  </label>
                  <select
                    value={sortBy}
                    onChange={(e) => {
                      setSortBy(e.target.value)
                      setCurrentPage(1)
                      setTimeout(() => handleSearch(), 0)
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-gray-900 bg-white"
                  >
                    <option value="relevance" className="text-gray-900">Relevance</option>
                    <optgroup label="Date (decisions)">
                      <option value="date_desc" className="text-gray-900">Date (Newest first)</option>
                      <option value="date_asc" className="text-gray-900">Date (Oldest first)</option>
                      <option value="theme" className="text-gray-900">Theme (A-Z)</option>
                      <option value="outcome" className="text-gray-900">Outcome (A-Z)</option>
                    </optgroup>
                    <optgroup label="Organizations">
                      <option value="name-asc" className="text-gray-900">Name (A-Z)</option>
                      <option value="name-desc" className="text-gray-900">Name (Z-A)</option>
                      <option value="revenue-desc" className="text-gray-900">Revenue (High to Low)</option>
                      <option value="revenue-asc" className="text-gray-900">Revenue (Low to High)</option>
                      <option value="assets-desc" className="text-gray-900">Assets (High to Low)</option>
                      <option value="assets-asc" className="text-gray-900">Assets (Low to High)</option>
                    </optgroup>
                  </select>
                </div>

                {/* NTEE Category (for organizations) */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Category (NTEE)
                  </label>
                  <select
                    value={nteeCategory}
                    onChange={(e) => {
                      setNteeCategory(e.target.value)
                      setCurrentPage(1)
                      setTimeout(() => handleSearch(), 0)
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-gray-900 bg-white"
                    disabled={!selectedTypes.includes('organizations')}
                  >
                    <option value="" className="text-gray-900">All Categories</option>
                    <option value="A" className="text-gray-900">Arts & Culture</option>
                    <option value="B" className="text-gray-900">Education</option>
                    <option value="C" className="text-gray-900">Environment</option>
                    <option value="D" className="text-gray-900">Animal-Related</option>
                    <option value="E" className="text-gray-900">Health</option>
                    <option value="F" className="text-gray-900">Mental Health</option>
                    <option value="G" className="text-gray-900">Diseases</option>
                    <option value="H" className="text-gray-900">Medical Research</option>
                    <option value="I" className="text-gray-900">Crime & Legal</option>
                    <option value="J" className="text-gray-900">Employment</option>
                    <option value="K" className="text-gray-900">Food & Agriculture</option>
                    <option value="L" className="text-gray-900">Housing</option>
                    <option value="M" className="text-gray-900">Public Safety</option>
                    <option value="N" className="text-gray-900">Recreation & Sports</option>
                    <option value="O" className="text-gray-900">Youth Development</option>
                    <option value="P" className="text-gray-900">Human Services</option>
                    <option value="Q" className="text-gray-900">International</option>
                    <option value="R" className="text-gray-900">Civil Rights</option>
                    <option value="S" className="text-gray-900">Community</option>
                    <option value="T" className="text-gray-900">Philanthropy</option>
                    <option value="U" className="text-gray-900">Science</option>
                    <option value="V" className="text-gray-900">Social Science</option>
                    <option value="W" className="text-gray-900">Public Affairs</option>
                    <option value="X" className="text-gray-900">Religion</option>
                    <option value="Y" className="text-gray-900">Mutual Benefit</option>
                  </select>
                </div>
              </div>

                  {/* Full Text Search Checkbox */}
                  <div className="pt-4 border-t border-gray-200">
                    <label className="flex items-center gap-2 cursor-pointer group">
                      <input
                        type="checkbox"
                        checked={includeFullText}
                        onChange={(e) => {
                          setIncludeFullText(e.target.checked)
                          setCurrentPage(1)
                          setTimeout(() => handleSearch(), 0)
                        }}
                        className="h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-2 focus:ring-primary-500 cursor-pointer"
                      />
                      <div className="flex-1">
                        <span className="text-sm font-medium text-gray-700 group-hover:text-gray-900 block">
                          Include full text
                        </span>
                        <span className="text-xs text-gray-500 block">
                          (bills, meeting transcripts & summaries)
                        </span>
                      </div>
                    </label>
                  </div>
                </div>

                {/* Footer Actions */}
                <div className="mt-8 pt-6 border-t border-gray-200 space-y-3">
                  <button
                    onClick={() => {
                      setSelectedState('')
                      setSortBy('relevance')
                      setNteeCategory('')
                      setIncludeFullText(false)
                      setSelectedTypes([...DEFAULT_RESULT_TYPES])
                      setTimeout(() => handleSearch(), 0)
                    }}
                    className="w-full px-4 py-2.5 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors font-medium"
                  >
                    Clear All Filters
                  </button>
                  <button
                    onClick={() => setShowFilters(false)}
                    className="w-full px-4 py-2.5 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors font-medium"
                  >
                    Apply Filters
                  </button>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Search Results */}
        {(activeQuery || selectedState || searchResults) && (
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
                        {searchResults.total_results.toLocaleString()} results for "{searchResults.query}"
                        {searchResults.total_results > 0 && (
                          <span className="text-base font-normal text-gray-600 ml-2">
                            (showing {searchResults.pagination.offset + 1}-
                            {Math.min(searchResults.pagination.offset + searchResults.pagination.limit, searchResults.total_results)})
                          </span>
                        )}
                      </>
                    ) : (
                      <>
                        {searchResults.total_results.toLocaleString()} results
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

                {/* Jurisdiction Details Breakdown */}
                {jurisdictionDetails.length > 0 && (
                  <div className="mb-6 p-6 bg-gradient-to-br from-teal-50 to-blue-50 rounded-xl border border-teal-200">
                    <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
                      <MapPinIcon className="h-6 w-6 text-teal-600" />
                      Your Jurisdictions
                    </h3>
                    <p className="text-sm text-gray-600 mb-4">
                      When you select a city, you're connected to {jurisdictionDetails.length} levels of government:
                    </p>
                    <div className="space-y-3">
                      {jurisdictionDetails.map((item: any, index: number) => {
                        const isExpanded = expandedJurisdictions.has(index)
                        return (
                          <div
                            key={index}
                            className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden transition-all duration-200 hover:shadow-md"
                          >
                            {/* Collapsed Header - Always Visible */}
                            <button
                              onClick={() => toggleJurisdictionExpansion(index)}
                              className="w-full flex items-center justify-between p-4 text-left hover:bg-gray-50 transition-colors"
                            >
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-semibold text-gray-900">{item.type}</span>
                                  <span className="text-gray-400">•</span>
                                  <span className="text-gray-700">{item.name}</span>
                                </div>
                                {!isExpanded && (
                                  <div className="text-sm text-gray-500 mt-1">
                                    Click to view details and discover data sources
                                  </div>
                                )}
                              </div>
                              <div className="flex items-center gap-3">
                                <CheckIcon className="h-5 w-5 text-green-600 flex-shrink-0" />
                                {isExpanded ? (
                                  <ChevronUpIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
                                ) : (
                                  <ChevronDownIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
                                )}
                              </div>
                            </button>

                            {/* Expanded Details */}
                            {isExpanded && (
                              <div className="px-4 pb-4 border-t border-gray-100 bg-gray-50">
                                <div className="mt-4 space-y-3">
                                  {/* Jurisdiction Info */}
                                  <div className="grid grid-cols-2 gap-4">
                                    <div>
                                      <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Type</div>
                                      <div className="text-sm text-gray-900">{item.type}</div>
                                    </div>
                                    <div>
                                      <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Name</div>
                                      <div className="text-sm text-gray-900">{item.name}</div>
                                    </div>
                                    {item.count !== undefined && (
                                      <div>
                                        <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Count</div>
                                        <div className="text-sm text-gray-900">{item.count.toLocaleString()}</div>
                                      </div>
                                    )}
                                  </div>

                                  {/* Discover Data Sources Button */}
                                  <div className="pt-3 border-t border-gray-200">
                                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                                      <div className="flex items-start gap-3">
                                        <div className="flex-shrink-0">
                                          <GlobeAltIcon className="h-5 w-5 text-blue-600" />
                                        </div>
                                        <div className="flex-1">
                                          <h4 className="text-sm font-semibold text-blue-900 mb-1">
                                            Automated Data Discovery
                                          </h4>
                                          <p className="text-xs text-blue-700 mb-3">
                                            Automatically find official websites, meeting agendas, YouTube channels, and social media for this jurisdiction.
                                          </p>
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation()
                                              // Navigate to discovery page
                                              const searchQuery = `${item.name} ${item.type}`
                                              navigate(`/discovery?q=${encodeURIComponent(searchQuery)}&jurisdiction=${encodeURIComponent(item.name)}`)
                                            }}
                                            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
                                          >
                                            <MagnifyingGlassIcon className="h-4 w-4" />
                                            Discover Data Sources
                                          </button>
                                        </div>
                                      </div>
                                    </div>
                                  </div>

                                  {/* What We'll Find */}
                                  <div className="pt-3 border-t border-gray-200">
                                    <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                                      What We'll Discover
                                    </div>
                                    <div className="grid grid-cols-2 gap-2 text-sm">
                                      <div className="flex items-center gap-2 text-gray-700">
                                        <GlobeAltIcon className="h-4 w-4 text-gray-400" />
                                        Official Website
                                      </div>
                                      <div className="flex items-center gap-2 text-gray-700">
                                        <CalendarIcon className="h-4 w-4 text-gray-400" />
                                        Meeting Agendas
                                      </div>
                                      <div className="flex items-center gap-2 text-gray-700">
                                        <VideoCameraIcon className="h-4 w-4 text-gray-400" />
                                        YouTube Channels
                                      </div>
                                      <div className="flex items-center gap-2 text-gray-700">
                                        <BuildingOfficeIcon className="h-4 w-4 text-gray-400" />
                                        Social Media
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                    <div className="mt-4 p-4 bg-blue-100 rounded-lg">
                      <p className="text-sm text-blue-900">
                        <strong>💡 Why this matters:</strong> Each jurisdiction has its own meetings, budgets, and leaders that affect your daily life. Track all of them in one place.
                      </p>
                    </div>
                  </div>
                )}

                {/* Results by Type */}
                {selectedTypes.includes('leaders') &&
                  searchResults.results?.leaders &&
                  searchResults.results.leaders.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <UserIcon className="h-6 w-6 text-blue-600" />
                      Leaders ({searchResults.type_totals?.leaders?.toLocaleString() || searchResults.results.leaders.length})
                    </h3>
                    <div className="grid grid-cols-1 gap-4">
                      {searchResults.results.leaders.map((result, idx) => (
                        <ResultCard key={idx} result={result} />
                      ))}
                    </div>
                  </div>
                )}

                {selectedTypes.includes('persons') &&
                  searchResults.results?.persons &&
                  searchResults.results.persons.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <UserIcon className="h-6 w-6 text-sky-600" />
                      Nonprofit Leaders ({searchResults.type_totals?.persons?.toLocaleString() || searchResults.results.persons.length})
                    </h3>
                    {(() => {
                      const persons = searchResults.results.persons
                      // Max revenue across the currently-rendered list, for bar widths.
                      const maxRevenue = persons.reduce((max, r) => {
                        const v = Number(r.metadata?.total_revenue)
                        return Number.isFinite(v) && v > max ? v : max
                      }, 0)
                      return (
                        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
                          <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                              <tr>
                                <th className="px-4 py-3 w-12" />
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Leader</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Organization</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Cause</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Total Revenue</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Assets</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Jurisdiction</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">File</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200">
                              {persons.map((result, idx) => {
                                const m = result.metadata ?? {}
                                const revenue = Number(m.total_revenue)
                                const hasRevenue = Number.isFinite(revenue) && m.total_revenue != null
                                const assets = Number(m.total_assets)
                                const hasAssets = Number.isFinite(assets) && m.total_assets != null
                                const barWidth = hasRevenue && maxRevenue > 0
                                  ? Math.max(2, Math.round((revenue / maxRevenue) * 100))
                                  : 0
                                const cause = m.cause ?? null
                                const dotColor = cause
                                  ? causeDotColor(String(m.ntee_code ?? m.cause))
                                  : null
                                return (
                                  <tr key={idx} className="hover:bg-gray-50 transition-colors">
                                    {/* Avatar */}
                                    <td className="px-4 py-3">
                                      <div
                                        className="w-10 h-10 rounded-full flex items-center justify-center text-white text-base font-bold"
                                        style={{ backgroundColor: '#2F5D62' }}
                                      >
                                        {result.title?.charAt(0) ?? '?'}
                                      </div>
                                    </td>
                                    {/* Leader */}
                                    <td className="px-4 py-3 align-top">
                                      <div
                                        onClick={() => openResult(result.url)}
                                        className={`font-semibold text-gray-900 ${
                                          result.url ? 'cursor-pointer hover:text-blue-600' : ''
                                        }`}
                                      >
                                        {result.title}
                                      </div>
                                      <div className="text-xs text-gray-500 mt-0.5">
                                        {m.title ?? 'Leader'}
                                      </div>
                                    </td>
                                    {/* Organization */}
                                    <td className="px-4 py-3 align-top">
                                      <div className="text-sm text-gray-900">{m.organization ?? '—'}</div>
                                      {m.ein && (
                                        <div className="text-xs text-gray-500 mt-0.5">EIN {formatEin(String(m.ein))}</div>
                                      )}
                                    </td>
                                    {/* Cause */}
                                    <td className="px-4 py-3 align-top">
                                      {cause ? (
                                        <div className="flex items-center gap-2">
                                          <span
                                            className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                                            style={{ backgroundColor: dotColor ?? '#9CA3AF' }}
                                          />
                                          <span className="text-sm text-gray-700">{cause}</span>
                                        </div>
                                      ) : null}
                                    </td>
                                    {/* Total Revenue */}
                                    <td className="px-4 py-3 align-top">
                                      {hasRevenue ? (
                                        <div className="flex items-center gap-2 min-w-[120px]">
                                          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                            <div
                                              className="h-full bg-sky-500 rounded-full"
                                              style={{ width: `${barWidth}%` }}
                                            />
                                          </div>
                                          <span className="text-xs text-gray-700 whitespace-nowrap">
                                            {formatCurrency(revenue)}
                                          </span>
                                        </div>
                                      ) : null}
                                    </td>
                                    {/* Assets */}
                                    <td className="px-4 py-3 align-top text-sm text-gray-700 whitespace-nowrap">
                                      {hasAssets ? formatCurrency(assets) : null}
                                    </td>
                                    {/* Jurisdiction */}
                                    <td className="px-4 py-3 align-top">
                                      {m.city && <div className="text-sm text-gray-900">{m.city}</div>}
                                      {m.state && <div className="text-xs text-gray-500 mt-0.5">{m.state}</div>}
                                    </td>
                                    {/* File */}
                                    <td className="px-4 py-3 align-top">
                                      {m.filing_url ? (
                                        <a
                                          href={m.filing_url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="text-gray-400 hover:text-blue-600"
                                          title="View 990 filing"
                                        >
                                          <DocumentTextIcon className="h-5 w-5" />
                                        </a>
                                      ) : null}
                                    </td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                      )
                    })()}
                  </div>
                )}

                {selectedTypes.includes('meetings') && searchResults.results?.meetings && searchResults.results.meetings.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <CalendarIcon className="h-6 w-6 text-green-600" />
                      Meetings ({searchResults.type_totals?.meetings?.toLocaleString() || searchResults.results.meetings.length})
                    </h3>
                    <div className="grid grid-cols-1 gap-4">
                      {searchResults.results.meetings.map((result, idx) => (
                        <ResultCard key={idx} result={result} />
                      ))}
                    </div>
                  </div>
                )}

                {selectedTypes.includes('organizations') && searchResults.results?.organizations && searchResults.results.organizations.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <BuildingOfficeIcon className="h-6 w-6 text-purple-600" />
                      Organizations ({searchResults.type_totals?.organizations?.toLocaleString() || searchResults.results.organizations.length})
                    </h3>
                    <div className="grid grid-cols-1 gap-4">
                      {searchResults.results.organizations.map((result, idx) => (
                        <ResultCard key={idx} result={result} />
                      ))}
                    </div>
                  </div>
                )}

                {selectedTypes.includes('causes') && searchResults.results?.causes && searchResults.results.causes.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <HeartIcon className="h-6 w-6 text-pink-600" />
                      Causes ({searchResults.type_totals?.causes?.toLocaleString() || searchResults.results.causes.length})
                    </h3>
                    <div className="grid grid-cols-1 gap-4">
                      {searchResults.results.causes.map((result, idx) => (
                        <ResultCard key={idx} result={result} />
                      ))}
                    </div>
                  </div>
                )}

                {selectedTypes.includes('bills') && searchResults.results?.bills && searchResults.results.bills.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <DocumentTextIcon className="h-6 w-6 text-indigo-600" />
                      Bills ({searchResults.type_totals?.bills?.toLocaleString() || searchResults.results.bills.length})
                    </h3>
                    <div className="grid grid-cols-1 gap-4">
                      {searchResults.results.bills.map((result, idx) => (
                        <ResultCard key={idx} result={result} />
                      ))}
                    </div>
                  </div>
                )}

                {selectedTypes.includes('topics') && searchResults.results?.topics && searchResults.results.topics.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <ChatBubbleBottomCenterTextIcon className="h-6 w-6 text-teal-600" />
                      Topics ({searchResults.type_totals?.topics?.toLocaleString() || searchResults.results.topics.length})
                    </h3>
                    <div className="grid grid-cols-1 gap-4">
                      {searchResults.results.topics.map((result, idx) => (
                        <ResultCard key={idx} result={result} />
                      ))}
                    </div>
                  </div>
                )}

                {selectedTypes.includes('decisions') && searchResults.results?.decisions && searchResults.results.decisions.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <ScaleIcon className="h-6 w-6 text-amber-600" />
                      Decisions ({searchResults.type_totals?.decisions?.toLocaleString() || searchResults.results.decisions.length})
                    </h3>
                    <div className="grid grid-cols-1 gap-4">
                      {searchResults.results.decisions.map((result, idx) => (
                        <ResultCard key={idx} result={result} />
                      ))}
                    </div>
                  </div>
                )}

                {selectedTypes.includes('jurisdictions') && searchResults.results?.jurisdictions && searchResults.results.jurisdictions.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <MapPinIcon className="h-6 w-6 text-orange-600" />
                      Jurisdictions ({searchResults.type_totals?.jurisdictions?.toLocaleString() || searchResults.results.jurisdictions.length})
                    </h3>
                    <div className="grid grid-cols-1 gap-4">
                      {searchResults.results.jurisdictions.map((result, idx) => (
                        <ResultCard key={idx} result={result} />
                      ))}
                    </div>
                  </div>
                )}

                {selectedTypes.includes('grants') && searchResults.results?.grants && searchResults.results.grants.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <BanknotesIcon className="h-6 w-6 text-emerald-600" />
                      Grants ({searchResults.type_totals?.grants?.toLocaleString() || searchResults.results.grants.length})
                    </h3>
                    <div className="grid grid-cols-1 gap-4">
                      {searchResults.results.grants.map((result, idx) => (
                        <ResultCard key={idx} result={result} />
                      ))}
                    </div>
                  </div>
                )}

                {/* Grant Opportunities — open federal funding (Grants.gov).
                    Distinct from historical 990 grantmaking ("Grants") above. */}
                {selectedTypes.includes('grant_opportunities') && searchResults.results?.grant_opportunities && searchResults.results.grant_opportunities.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <MegaphoneIcon className="h-6 w-6 text-rose-600" />
                      Grant Opportunities ({searchResults.type_totals?.grant_opportunities?.toLocaleString() || searchResults.results.grant_opportunities.length})
                    </h3>
                    <div className="grid grid-cols-1 gap-4">
                      {searchResults.results.grant_opportunities.map((result, idx) => (
                        <ResultCard key={idx} result={result} />
                      ))}
                    </div>
                  </div>
                )}

                {/* No Results */}
                {searchResults.total_results === 0 && (
                  <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
                    <MagnifyingGlassIcon className="h-16 w-16 text-gray-300 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">No results found</h3>
                    <p className="text-gray-600">
                      Try different keywords or adjust your filters
                    </p>
                  </div>
                )}

                {/* Pagination Controls */}
                {searchResults.total_results > 0 && searchResults.pagination.total_pages > 1 && (
                  <div className="mt-8 flex items-center justify-between bg-white rounded-lg border border-gray-200 p-4">
                    <div className="text-sm text-gray-600">
                      Page {searchResults.pagination.page} of {searchResults.pagination.total_pages}
                      <span className="ml-2">•</span>
                      <span className="ml-2">{searchResults.total_results} total results</span>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handlePageChange(searchResults.pagination.page - 1)}
                        disabled={!searchResults.pagination.has_prev}
                        className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                          searchResults.pagination.has_prev
                            ? 'bg-primary-600 text-white hover:bg-primary-700'
                            : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        }`}
                      >
                        ← Previous
                      </button>
                      
                      {/* Page numbers */}
                      <div className="flex items-center gap-1">
                        {Array.from({ length: Math.min(5, searchResults.pagination.total_pages) }, (_, i) => {
                          const pageNum = Math.max(
                            1,
                            Math.min(
                              searchResults.pagination.page - 2 + i,
                              searchResults.pagination.total_pages - 4
                            )
                          ) + Math.min(i, 4)
                          
                          if (pageNum > searchResults.pagination.total_pages) return null
                          
                          return (
                            <button
                              key={pageNum}
                              onClick={() => handlePageChange(pageNum)}
                              className={`px-3 py-1 rounded ${
                                pageNum === searchResults.pagination.page
                                  ? 'bg-primary-600 text-white font-semibold'
                                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                              }`}
                            >
                              {pageNum}
                            </button>
                          )
                        })}
                      </div>
                      
                      <button
                        onClick={() => handlePageChange(searchResults.pagination.page + 1)}
                        disabled={!searchResults.pagination.has_next}
                        className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                          searchResults.pagination.has_next
                            ? 'bg-primary-600 text-white hover:bg-primary-700'
                            : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        }`}
                      >
                        Next →
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Initial State - Search Examples */}
        {!activeQuery && (
          <div className="bg-white rounded-lg shadow-sm p-8">
            {(selectedState || selectedTypes.length < 5) && (
              <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-blue-800 font-medium">
                  {selectedState && `State filter: ${selectedState}`}
                  {selectedState && selectedTypes.length < 5 && ' • '}
                  {selectedTypes.length < 5 && `Type filter: ${selectedTypes.join(', ')}`}
                </p>
                <p className="text-blue-700 text-sm mt-1">
                  Enter a search query above to see results with these filters applied.
                </p>
              </div>
            )}
            <h2 className="text-xl font-semibold text-gray-900 mb-6">Try searching for:</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[
                { query: 'dental health', icon: HeartIcon, description: 'Find organizations and meetings about dental health' },
                { query: 'affordable housing', icon: BuildingOfficeIcon, description: 'Discover housing-related initiatives' },
                { query: 'school board', icon: CalendarIcon, description: 'View school board meetings and decisions' },
                { query: 'mental health', icon: HeartIcon, description: 'Explore mental health programs and services' },
              ].map((example, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setQuery(example.query)
                    setActiveQuery(example.query)
                  }}
                  className="text-left p-4 border-2 border-gray-200 rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors"
                >
                  <div className="flex items-center gap-3 mb-2">
                    <example.icon className="h-6 w-6 text-primary-600" />
                    <span className="font-semibold text-gray-900">{example.query}</span>
                  </div>
                  <p className="text-sm text-gray-600">{example.description}</p>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
