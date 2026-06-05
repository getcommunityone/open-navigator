import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import React, { useState, Fragment, useEffect, useRef } from 'react'
import { Menu, Transition } from '@headlessui/react'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { tracer } from '../instrumentation'
import { homeLog } from '../utils/devLog'
import { 
  MagnifyingGlassIcon, 
  DocumentTextIcon, 
  ChartBarIcon,
  BuildingLibraryIcon,
  ArrowRightIcon,
  BookOpenIcon,
  HeartIcon,
  ScaleIcon,
  UserGroupIcon,
  ChatBubbleBottomCenterTextIcon,
  CheckCircleIcon,
  MapIcon,
  MapPinIcon,
  PlusIcon,
  BellIcon,
  ArrowTrendingUpIcon,
  Bars3Icon,
  XMarkIcon,
  UserCircleIcon,
  ChevronDownIcon,
  CheckIcon,
  EnvelopeIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon,
  ClipboardDocumentListIcon,
  CodeBracketIcon,
  BanknotesIcon,
} from '@heroicons/react/24/outline'
import {
  EXPLORE_BUILD_ID,
  EXPLORE_CAUSES_ID,
  EXPLORE_FIND_HELP_ID,
  EXPLORE_PLAN_ID,
  EXPLORE_TRACK_DECISIONS_ID,
} from '../data/exploreActionPhases'
import { useAuth } from '../contexts/AuthContext'
import AddressLookup from '../components/AddressLookup'
import HeroStateSilhouetteBadge from '../components/HeroStateSilhouetteBadge'
import { useLocation as useLocationContext, type LocationData } from '../contexts/LocationContext'
import { formatCommunityPlaceLine } from '../utils/communityLocationLabel'

// Trending topic/cause interface
interface TrendingCause {
  name: string
  icon: string
  category: string
  description?: string
  image_url?: string
  popularity_rank?: number
}

// Featured stories for tabbed hero banner
const FEATURED_STORIES = [
  {
    type: 'hero',
    title: 'CommunityOne',
    subtitle: 'Track Local Decisions. Take Action.',
    description: 'Follow leaders, charities, and causes in your community.',
    stats: '925 jurisdictions • 43.7K nonprofits • 8.8K legislators • 650+ causes • 100% free',
    category: 'Home',
    link: '/'
  },
  {
    type: 'story',
    title: 'World Press Freedom Day: 43,726 Nonprofits Fighting for Transparency',
    subtitle: 'How local journalism and civic organizations are tracking government decisions across 925 jurisdictions',
    image: 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1200&h=600&fit=crop',
    category: 'Civic Engagement',
    link: '/search?q=press+freedom'
  },
  {
    type: 'story',
    title: 'AI Policy Tracking: 15,000+ Government Decisions Analyzed',
    subtitle: 'Machine learning models identify patterns in legislative discussions and regulatory frameworks',
    image: 'https://images.unsplash.com/photo-1677442136019-21780ecad995?w=1200&h=600&fit=crop',
    category: 'Artificial Intelligence',
    link: '/search?q=artificial+intelligence'
  },
  {
    type: 'story',
    title: 'Healthcare Access: Dental Clinics in Focus',
    subtitle: 'Tracking 8,500+ dental health providers and community health initiatives nationwide',
    image: 'https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?w=1200&h=600&fit=crop',
    category: 'Health & Medicine',
    link: '/search?q=dental+health'
  },
  {
    type: 'story',
    title: 'Local Sports Funding: $2.5B in Community Programs',
    subtitle: 'Analysis of recreation budget allocation across 12,000+ jurisdictions',
    image: 'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=1200&h=600&fit=crop',
    category: 'Sports & Recreation',
    link: '/search?q=sports+funding'
  },
  {
    type: 'story',
    title: 'Social Media Policies: Cities Set New Guidelines',
    subtitle: 'How local governments are establishing digital communication standards',
    image: 'https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=1200&h=600&fit=crop',
    category: 'Technology',
    link: '/search?q=social+media+policy'
  },
  {
    type: 'story',
    title: 'Business Development: 8,000+ Economic Initiatives',
    subtitle: 'Economic development zones, tax incentives, and small business support programs',
    image: 'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1200&h=600&fit=crop',
    category: 'Business & Markets',
    link: '/search?q=business+development'
  },
  {
    type: 'story',
    title: 'Government Transparency: 12,000+ Hours of Meeting Video',
    subtitle: 'Comprehensive archive of city council, county board, and planning commission meetings',
    image: 'https://images.unsplash.com/photo-1555421689-d68471e189f2?w=1200&h=600&fit=crop',
    category: 'Government',
    link: '/documents'
  },
]

type HeroSearchCategoryTab =
  | 'all'
  | 'leaders'
  | 'persons'
  | 'nonprofits'
  | 'decisions'
  | 'causes'
  | 'bills'
  | 'grants'
  | 'donors'

const HERO_SEARCH_TAB_DEFS: {
  id: HeroSearchCategoryTab
  label: string
  types: string
  count?: string
  /* `activity` surfaces an orange "new this week" dot in the category dropdown. */
  activity?: boolean
  /* Shown in the input when this category is active (the box narrows a browsable list). */
  filterPlaceholder?: string
}[] = [
  { id: 'all', label: 'All', types: 'causes,leaders,organizations,bills,topics,decisions' },
  { id: 'leaders', label: 'Leaders', types: 'leaders', count: '75K', filterPlaceholder: 'Filter leaders by name or office…' },
  { id: 'persons', label: 'Persons', types: 'persons', filterPlaceholder: 'Filter people by name…' },
  { id: 'nonprofits', label: 'Nonprofits', types: 'organizations', count: '1.8M', filterPlaceholder: 'Filter nonprofits by name or cause…' },
  { id: 'decisions', label: 'Decisions', types: 'decisions', count: '169', activity: true, filterPlaceholder: 'Filter decisions by topic or body…' },
  { id: 'causes', label: 'Causes', types: 'causes', count: '650+', filterPlaceholder: 'Filter causes by name…' },
  { id: 'bills', label: 'Bills', types: 'bills', filterPlaceholder: 'Filter bills by number or topic…' },
  { id: 'grants', label: 'Grants', types: 'grants', filterPlaceholder: 'Filter grants by organization or purpose…' },
  {
    id: 'donors',
    label: 'Donors',
    /* No dedicated donor index yet — combined people + orgs until search adds a donors type. */
    types: 'persons,organizations',
    filterPlaceholder: 'Filter donors by name…',
  },
]

// Shown under the hero bar in the idle state when the live trending query
// returns nothing (e.g. an empty local warehouse) so the row still reads as
// designed. Real trending causes from /trending take precedence when present.
const FALLBACK_TRENDING: { name: string }[] = [
  { name: 'school board budget' },
  { name: 'rezoning' },
  { name: 'police oversight board' },
  { name: 'water utility rates' },
  { name: 'short-term rentals' },
  { name: 'transit funding' },
]

function formatCompactCount(n: number | undefined): string | undefined {
  if (n == null || Number.isNaN(n) || n < 0) return undefined
  if (n >= 1_000_000) {
    const x = n / 1_000_000
    return x >= 10 ? `${Math.round(x)}M` : `${x.toFixed(1).replace(/\.0$/, '')}M`
  }
  if (n >= 1_000) {
    const x = n / 1_000
    return x >= 100 ? `${Math.round(x)}K` : `${x.toFixed(1).replace(/\.0$/, '')}K`
  }
  return String(n)
}

export default function Home() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [keyword, setKeyword] = useState('')
  const [debouncedKeyword, setDebouncedKeyword] = useState('')
  const [searchScope, setSearchScope] = useState('city') // city, county, state, national, community (school)
  const [selectedTab, setSelectedTab] = useState(0)
  const [selectedStoryTab, setSelectedStoryTab] = useState(0)
  const [heroSearchTab, setHeroSearchTab] = useState<HeroSearchCategoryTab>('all')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [focused, setFocused] = useState(false)
  const [scopeOpen, setScopeOpen] = useState(false)
  const [catOpen, setCatOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [showLoginMenu, setShowLoginMenu] = useState(false)
  const { location, setLocation } = useLocationContext()
  const { user, isAuthenticated, login, logout, isLoading } = useAuth()
  const searchContainerRef = useRef<HTMLDivElement>(null)
  const scopeRef = useRef<HTMLDivElement>(null)
  const catRef = useRef<HTMLDivElement>(null)

  const DOCS_URL = import.meta.env.PROD ? 'https://www.communityone.com/docs/intro' : 'http://localhost:3000/docs/intro'
  
  // Debounce keyword input (300ms delay)
  useEffect(() => {
    const timer = setTimeout(() => {
      homeLog('⏱️ [Home] Debounced keyword update:', keyword);
      setDebouncedKeyword(keyword);
    }, 300);

    return () => {
      clearTimeout(timer);
    };
  }, [keyword]);

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

  // Close location scope dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (scopeRef.current && !scopeRef.current.contains(event.target as Node)) {
        setScopeOpen(false);
      }
    };

    if (scopeOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [scopeOpen]);

  // Close category dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (catRef.current && !catRef.current.contains(event.target as Node)) {
        setCatOpen(false);
      }
    };

    if (catOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [catOpen]);

  // Fetch stats based on location AND search scope
  const { data: locationStats } = useQuery({
    queryKey: ['location-stats', location?.state, location?.city, location?.county, location?.granularity, searchScope],
    queryFn: async () => {
      if (!location) return null;
      
      const params: any = {};
      
      // Only include parameters based on selected scope
      if (searchScope === 'city' && location.city) {
        params.state = location.state;
        params.county = location.county;
        params.city = location.city;
      } else if (searchScope === 'county' && location.county) {
        params.state = location.state;
        params.county = location.county;
      } else if (searchScope === 'state' && location.state) {
        params.state = location.state;
      } else if (searchScope === 'community' && location.city) {
        // School boards - city level
        params.state = location.state;
        params.city = location.city;
      } else {
        // Fallback to state level if scope doesn't match available data
        params.state = location.state;
      }
      
      homeLog('📊 [Home] Fetching stats for scope:', searchScope, 'params:', params);
      const response = await api.get('/stats', { params });
      homeLog('📊 [Home] Location stats:', response.data);
      return response.data;
    },
    enabled: !!location,
    staleTime: 5 * 60 * 1000 // Cache for 5 minutes
  });

  // Hero category badge counts, scoped to the selected geography. The /stats
  // endpoint serves these from the cached jurisdiction_state_aggregate rollup
  // (national/state/county/city rows). When a location is selected we show the
  // real count; otherwise we fall back to the static marketing string so the
  // idle hero still reads as designed.
  const HERO_COUNT_STAT_FIELD: Partial<Record<HeroSearchCategoryTab, string>> = {
    leaders: 'leaders',
    persons: 'persons',
    nonprofits: 'nonprofits',
    decisions: 'decisions',
    bills: 'bills',
  }
  const heroCategoryCount = (cat: { id: HeroSearchCategoryTab; count?: string }): string | undefined => {
    const statKey = HERO_COUNT_STAT_FIELD[cat.id]
    if (statKey) {
      const real = formatCompactCount(locationStats?.[statKey] as number | undefined)
      if (real != null) return real
    }
    return cat.count
  }

  // Fetch trending causes from database (replaces hardcoded TRENDING_TOPICS)
  const { data: trendingData } = useQuery({
    queryKey: ['trending-causes'],
    queryFn: async () => {
      const response = await api.get('/trending', {
        params: {
          source: 'mixed',  // Mix of everyorg and ntee causes
          limit: 12
        }
      })
      return response.data
    },
    staleTime: 5 * 60 * 1000,  // Cache for 5 minutes
  })

  // Helper function to map cause names to icons
  const getCauseIcon = (causeName: string): string => {
    const iconMap: Record<string, string> = {
      'Education': '📚',
      'Education and Workforce': '📚',
      'Health': '🏥',
      'Healthcare': '🏥',
      'Environment': '🌍',
      'Environmental Protection': '🌍',
      'Environmental and Natural Resources': '🌍',
      'Climate': '🌍',
      'Housing': '🏠',
      'Housing and Community Amenities': '🏠',
      'Public Safety': '🚨',
      'Public Safety and Emergency Services': '🚨',
      'Public Order and Safety': '🚨',
      'Economic Affairs': '💼',
      'Economic Development and Business': '💼',
      'Social Protection': '🤝',
      'Recreation': '🎨',
      'Recreation, Culture, and Religion': '🎨',
      'General Public Services': '🏛️',
      'Governance and Administrative Policy': '🏛️',
      'Infrastructure and Capital Projects': '🏗️',
      'Fiscal and Budget Management': '💰',
      'Public Engagement and Communications': '📣',
      'Zoning and Land Use': '🏘️',
      'Defense': '🛡️',
      'Transportation': '🚗'
    }
    return iconMap[causeName] || '📋'
  }

  // Use location-specific trending causes if available, fallback to global trending
  const trendingTopics = React.useMemo(() => {
    // If we have location stats with trending causes, use those
    if (locationStats?.trending_causes && Array.isArray(locationStats.trending_causes)) {
      homeLog('📊 [Home] Using location-specific trending causes:', locationStats.trending_causes)
      
      // Transform the database trending_causes to match TrendingCause interface
      // Filter out causes with no decisions
      return locationStats.trending_causes
        .filter((cause: any) => (cause.decision_count || 0) > 0)
        .slice(0, 12)
        .map((cause: any) => ({
          name: cause.cause || cause.name,
          icon: getCauseIcon(cause.cause || cause.name),
          category: 'primary',
          description: `${cause.decision_count || 0} recent decisions`,
          popularity_rank: cause.rank
        }))
    }
    
    // Otherwise use global trending causes from API
    // Also filter these to only show causes with decision counts
    homeLog('📊 [Home] Using global trending causes from API')
    const globalCauses = trendingData?.causes || []
    return globalCauses.filter((cause: any) => (cause.decision_count || 0) > 0)
  }, [locationStats, trendingData])

  const activeHeroTab = React.useMemo(
    () => HERO_SEARCH_TAB_DEFS.find((t) => t.id === heroSearchTab) ?? HERO_SEARCH_TAB_DEFS[0],
    [heroSearchTab],
  )

  const heroSearchTypes = activeHeroTab.types

  // Placeholder adapts to the active scope: the broad "All" prompt, or a
  // category-specific "Filter … by …" prompt that signals the box now narrows
  // a browsable list.
  const heroSearchPlaceholder =
    heroSearchTab === 'all'
      ? 'Search topics, people, organizations, or causes…'
      : activeHeroTab.filterPlaceholder ?? 'Search topics, people, organizations, or causes…'

  // Human-readable label for the currently selected search scope (reused by the
  // location selector button and the live "Searching … in …" hint line).
  const scopeLabel = React.useMemo(() => {
    if (!location) return 'your area'
    switch (searchScope) {
      case 'city':
        return `My City (${location.city || '—'})`
      case 'county':
        return `My County (${location.county || '—'})`
      case 'community':
        return `School Board (${location.city || '—'})`
      case 'state':
        return `My State (${location.state})`
      case 'national':
        return 'National'
      default:
        return 'your area'
    }
  }, [location, searchScope])

  const scopeNoun = React.useMemo(() => {
    if (heroSearchTab === 'all') return 'everything'
    const row = HERO_SEARCH_TAB_DEFS.find((t) => t.id === heroSearchTab)
    return (row?.label ?? 'everything').toLowerCase()
  }, [heroSearchTab])

  // The next-broader geography for the "expand search area" affordance shown
  // when a scoped search returns no results. Walks city → county → state →
  // national, skipping levels the current location can't support. `null` once
  // already nationwide (nothing left to broaden to).
  const broaderScope = React.useMemo<{ value: string; label: string } | null>(() => {
    if (!location) return null
    const order = ['city', 'community', 'county', 'state', 'national']
    const currentRank = order.indexOf(searchScope)
    const candidates: { value: string; available: boolean; label: string }[] = [
      { value: 'county', available: !!location.county, label: location.county ? `${location.county} County` : 'your county' },
      { value: 'state', available: !!location.state, label: location.state || 'your state' },
      { value: 'national', available: true, label: 'nationwide' },
    ]
    for (const c of candidates) {
      if (order.indexOf(c.value) > currentRank && c.available) return { value: c.value, label: c.label }
    }
    return null
  }, [location, searchScope])

  // Generate dynamic subtitle based on location and search scope
  const getSubtitle = () => {
    // If national scope, show national message regardless of location
    if (searchScope === 'national') {
      return 'Track Decisions Nationwide';
    }
    
    if (!location) {
      return 'Track Local Decisions. Take Action.';
    }
    
    if (searchScope === 'city' && location.city && location.state) {
      return `Track Decisions in ${location.city}, ${location.state}`;
    }
    if (searchScope === 'county' && location.county && location.state) {
      return `Track Decisions in ${location.county}, ${location.state}`;
    }
    if (searchScope === 'state' && location.state) {
      return `Track Decisions in ${location.state}`;
    }
    if (searchScope === 'community' && location.city && location.state) {
      return `Track School Board Decisions in ${location.city}, ${location.state}`;
    }
    
    // Fallback based on location only
    if (location.city && location.state) {
      return `Track Decisions in ${location.city}, ${location.state}`;
    }
    if (location.state) {
      return `Track Decisions in ${location.state}`;
    }
    return 'Track Local Decisions. Take Action.';
  };

  // Highlight matching text in dropdown results
  const highlightMatch = (text: string, keyword: string) => {
    if (!keyword || !text) return text;
    
    const parts = text.split(new RegExp(`(${keyword})`, 'gi'));
    return (
      <>
        {parts.map((part, i) => 
          part.toLowerCase() === keyword.toLowerCase() ? (
            <span key={i} className="bg-yellow-200 font-semibold">{part}</span>
          ) : (
            part
          )
        )}
      </>
    );
  };

  // Filter results to only include items containing the keyword
  const filterResults = (results: any[], keyword: string, resultType?: string) => {
    if (!keyword || keyword.length < 2) return results;
    const lowerKeyword = keyword.toLowerCase();
    return results.filter((result: any) => {
      // For topics, only check the title (topic field) - be strict
      if (resultType === 'topics') {
        return result.title?.toLowerCase().includes(lowerKeyword);
      }
      // For other types, check all searchable fields
      const searchableText = [
        result.title,
        result.subtitle,
        result.description,
        result.name,
        result.jurisdiction_name
      ].filter(Boolean).join(' ').toLowerCase();
      return searchableText.includes(lowerKeyword);
    });
  };

  // Live search preview (type-ahead with actual results from API)
  const { data: previewResults, isLoading: previewLoading, error: previewError } = useQuery({
    queryKey: ['search-preview-home', debouncedKeyword, location?.state, searchScope, heroSearchTypes],
    queryFn: async () => {
      homeLog('🔍 [Home] Fetching preview for:', debouncedKeyword, 'in state:', location?.state);
      if (!debouncedKeyword || debouncedKeyword.length < 2) {
        homeLog('⚠️ [Home] Query too short, skipping');
        return null;
      }
      
      try {
        const url = '/search/';
        const params: any = {
          q: debouncedKeyword,
          types: heroSearchTypes,
          limit: 12  // Higher limit to show results from multiple types
        };
        
        // Add state filter based on search scope (don't filter if scope is 'national')
        if (location && location.state && searchScope !== 'national') {
          params.state = location.state;
          homeLog('📍 [Home] Filtering by state:', location.state);
        } else if (searchScope === 'national') {
          homeLog('🌎 [Home] National search - no state filter');
        }
        
        homeLog('📤 [Home] API Request:', url, params);
        const response = await api.get(url, { params });
        homeLog('📥 [Home] API Response:', response.data);
        homeLog('📊 [Home] Total results:', response.data.total_results);
        return response.data;
      } catch (error: any) {
        console.error('❌ [Home] Search preview error:', error);
        console.error('❌ [Home] Error details:', {
          message: error.message,
          response: error.response,
          status: error.response?.status,
          data: error.response?.data
        });
        throw error;
      }
    },
    enabled: debouncedKeyword.length >= 2 && showSuggestions,
    staleTime: 1000,
    retry: false // Don't retry to see errors immediately
  });

  // Log when preview state changes
  useEffect(() => {
    homeLog('🔄 [Home] Preview state:', {
      keyword,
      keywordLength: keyword.length,
      showSuggestions,
      isLoading: previewLoading,
      hasError: !!previewError,
      hasResults: !!previewResults,
      totalResults: previewResults?.total_results
    });
  }, [previewResults, showSuggestions, keyword, previewLoading, previewError]);

  // Handle tab parameter from URL
  useEffect(() => {
    const tabParam = searchParams.get('tab')
    if (tabParam === 'community') {
      setSelectedTab(1) // Open location modal
    }
  }, [searchParams])

  // When location is set, default to city search if currently on 'community' (placeholder)
  useEffect(() => {
    if (location && searchScope === 'community') {
      setSearchScope('city')
    }
  }, [location, searchScope])

  const handleKeywordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setKeyword(value)
    setShowSuggestions(value.length >= 2)
  }

  // Apply the active location scope to a /search URL the same way the
  // `location-stats` query (above) does, so navigation stays consistent with
  // the badge counts. UnifiedSearch + /api/search currently accept only
  // `state` and `city` (no `county` param), so we forward city+state and
  // intentionally omit county even when the scope is county-level.
  const applyLocationScope = (params: URLSearchParams) => {
    if (!location) return
    if (searchScope === 'city' && location.city) {
      if (location.state) params.set('state', location.state)
      params.set('city', location.city)
    } else if (searchScope === 'community' && location.city) {
      // School boards — city level
      if (location.state) params.set('state', location.state)
      params.set('city', location.city)
    } else if (location.state) {
      // county / state / national / fallback: state-level only (no county param downstream)
      params.set('state', location.state)
    }
  }

  const handleSelectSuggestion = (suggestion: string) => {
    setKeyword(suggestion)
    setShowSuggestions(false)

    // Navigate to search results with the selected suggestion
    const params = new URLSearchParams()
    params.set('q', suggestion)
    if (heroSearchTab !== 'all') {
      params.set('types', heroSearchTypes)
    }
    applyLocationScope(params)
    navigate(`/search?${params.toString()}`)
  }

  const handleViewAllCategory = (category: string) => {
    if (keyword.trim().length >= 2) {
      const params = new URLSearchParams()
      params.set('q', keyword)
      params.set('types', category)
      applyLocationScope(params)
      navigate(`/search?${params.toString()}`)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    homeLog('🔍 [Home] Search submitted:', { keyword, location: location?.state, searchScope });

    const q = keyword.trim()
    // Unified search supports browse-by-type with no query; hero still requires a query on "All".
    if (!q && heroSearchTab === 'all') {
      console.warn('⚠️ [Home] Search submitted with empty keyword');
      return
    }

    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (heroSearchTab !== 'all') {
      params.set('types', heroSearchTypes)
    }

    applyLocationScope(params)
    homeLog('📍 [Home] Applied location scope:', { scope: searchScope, state: params.get('state'), city: params.get('city') })

    // Trace the search submission. Attributes are low-cardinality only — we
    // record the query *length* and presence, never the raw query string
    // (privacy + cardinality), mirroring the API's search spans.
    const searchSpan = tracer.startSpan('search.submit', {
      attributes: {
        'search.q.length': q.length,
        'search.has_query': q.length > 0,
        'search.scope': searchScope,
        'search.tab': heroSearchTab,
      },
    })
    searchSpan.end()

    const searchUrl = `/search?${params.toString()}`
    homeLog('🚀 [Home] Navigating to:', searchUrl)
    navigate(searchUrl)
  }

  const handleAddressFound = (locationData: LocationData) => {
    homeLog('📍 [Home] Address found, updating location:', locationData)
    setLocation({
      address: locationData.address,
      state: locationData.state,
      county: locationData.county,
      city: locationData.city,
      granularity: locationData.granularity,
      latitude: locationData.latitude,
      longitude: locationData.longitude,
    })
    if (locationData.granularity === 'state') {
      setSearchScope('state')
    } else if (locationData.granularity === 'county') {
      setSearchScope('county')
    } else {
      setSearchScope('city')
    }

    // Close the modal and return to search tab
    setSelectedTab(0)
  }

  // Debug: Log when location changes
  useEffect(() => {
    homeLog('📍 [Home] Location state changed:', location);
    homeLog('📍 [Home] Current subtitle:', getSubtitle());
  }, [location]);

  // Smooth scroll to section with offset for sticky header
  const scrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId)
    if (element) {
      const offset = 80 // Account for sticky header (h-20 = 80px)
      const elementPosition = element.getBoundingClientRect().top
      const offsetPosition = elementPosition + window.pageYOffset - offset

      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
      })
    }
  }

  /** Top nav "Search": return to hero and focus the main search field (no route change). */
  const scrollToTopHeroSearch = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
    window.setTimeout(() => {
      document.getElementById('hero-search-input')?.focus({ preventScroll: true })
    }, 350)
  }

  return (
    <div className="min-h-screen bg-slate-300">
      {/* Navigation Header */}
      <nav className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-20">
            {/* Logo */}
            <a 
              href="#" 
              onClick={(e) => {
                e.preventDefault()
                window.scrollTo({ top: 0, behavior: 'smooth' })
              }}
              className="flex items-center gap-2 md:gap-3 cursor-pointer group"
            >
              <img 
                src="/communityone_logo.svg" 
                alt="CommunityOne Logo" 
                className="h-8 md:h-12"
              />
              <div className="flex flex-col">
                <span className="text-base md:text-xl font-bold" style={{ color: '#354F52' }}>
                  Open Navigator
                </span>
                <span className="hidden sm:block text-xs text-gray-500 -mt-1 group-hover:text-[#354F52] transition-colors">
                  The open path to everything local
                </span>
              </div>
            </a>

            {/* Desktop Navigation Links - Centered with underline */}
            <div className="hidden md:flex items-center gap-8">
              <button
                type="button"
                onClick={scrollToTopHeroSearch}
                className="text-sm font-medium text-gray-600 hover:text-[#354F52] transition-colors pb-1 border-b-2 border-transparent hover:border-[#354F52] cursor-pointer"
              >
                Search
              </button>
              <button 
                onClick={() => scrollToSection('how-it-works')} 
                className="text-sm font-medium text-gray-600 hover:text-[#354F52] transition-colors pb-1 border-b-2 border-transparent hover:border-[#354F52] cursor-pointer"
              >
                How It Works
              </button>
              <button 
                onClick={() => scrollToSection('impact')} 
                className="text-sm font-medium text-gray-600 hover:text-[#354F52] transition-colors pb-1 border-b-2 border-transparent hover:border-[#354F52] cursor-pointer"
              >
                Impact
              </button>
              <button 
                onClick={() => scrollToSection('contact')} 
                className="text-sm font-medium text-gray-600 hover:text-[#354F52] transition-colors pb-1 border-b-2 border-transparent hover:border-[#354F52] cursor-pointer"
              >
                Contact
              </button>
            </div>

            {/* Desktop CTA Button */}
            <div className="hidden md:flex items-center gap-3">
              {isLoading ? (
                <div className="px-3 py-2">
                  <div className="animate-spin h-8 w-8 border-3 border-gray-300 border-t-primary-600 rounded-full"></div>
                </div>
              ) : isAuthenticated && user ? (
                <Menu as="div" className="relative">
                  <Menu.Button className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors">
                    {user.avatar_url ? (
                      <img 
                        src={user.avatar_url} 
                        alt={user.full_name || user.email}
                        className="h-9 w-9 flex-shrink-0 rounded-full border-2 border-primary-500 shadow-sm object-cover"
                        referrerPolicy="no-referrer"
                        onError={(e) => {
                          console.error('❌ Avatar failed to load:', user.avatar_url);
                          e.currentTarget.style.display = 'none';
                          const fallback = e.currentTarget.nextElementSibling as HTMLElement | null;
                          if (fallback) fallback.style.display = 'flex';
                        }}
                        onLoad={() => {
                          homeLog('✅ Avatar loaded successfully:', user.avatar_url?.substring(0, 50));
                        }}
                      />
                    ) : null}
                    <div 
                      className="h-9 w-9 rounded-full bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center text-white font-bold text-sm shadow-sm"
                      style={{ display: user.avatar_url ? 'none' : 'flex' }}
                    >
                      {(user.full_name || user.username || user.email).charAt(0).toUpperCase()}
                    </div>
                    <span className="hidden md:inline text-sm font-medium text-gray-700">
                      {user.full_name || user.username || user.email.split('@')[0]}
                    </span>
                    <ChevronDownIcon className="hidden md:block h-4 w-4 text-gray-600" />
                  </Menu.Button>
                  
                  <Transition
                    as={Fragment}
                    enter="transition ease-out duration-100"
                    enterFrom="transform opacity-0 scale-95"
                    enterTo="transform opacity-100 scale-100"
                    leave="transition ease-in duration-75"
                    leaveFrom="transform opacity-100 scale-100"
                    leaveTo="transform opacity-0 scale-95"
                  >
                    <Menu.Items className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-gray-200 focus:outline-none z-50">
                      <div className="px-4 py-3 border-b border-gray-200">
                        <div className="flex items-center gap-3 mb-2">
                          {user.avatar_url ? (
                            <img 
                              src={user.avatar_url} 
                              alt={user.full_name || user.email}
                              className="h-12 w-12 rounded-full border-2 border-primary-500"
                              referrerPolicy="no-referrer"
                              onError={(e) => {
                                console.error('❌ Avatar (dropdown) failed to load:', user.avatar_url);
                                e.currentTarget.style.display = 'none';
                                const fallback = e.currentTarget.nextElementSibling as HTMLElement | null;
                                if (fallback) fallback.style.display = 'flex';
                              }}
                            />
                          ) : null}
                          <div 
                            className="h-12 w-12 rounded-full bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center text-white font-bold text-lg"
                            style={{ display: user.avatar_url ? 'none' : 'flex' }}
                          >
                            {(user.full_name || user.username || user.email).charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-gray-900">
                              {user.full_name || user.username || user.email.split('@')[0]}
                            </p>
                            <p className="text-xs text-gray-500 truncate">
                              {user.email}
                            </p>
                          </div>
                        </div>
                        {user.oauth_provider && (
                          <div className="flex items-center gap-1 text-xs text-gray-400">
                            <span>Signed in via</span>
                            <span className="font-medium capitalize">{user.oauth_provider}</span>
                          </div>
                        )}
                      </div>
                      <div className="py-1">
                        <Menu.Item>
                          {({ active }) => (
                            <button
                              onClick={() => navigate('/profile')}
                              className={`${
                                active ? 'bg-gray-50' : ''
                              } flex items-center gap-3 w-full px-4 py-2.5 text-sm text-gray-700 hover:text-gray-900`}
                            >
                              <UserCircleIcon className="h-5 w-5" />
                              <span>My Profile</span>
                            </button>
                          )}
                        </Menu.Item>
                        <Menu.Item>
                          {({ active }) => (
                            <button
                              onClick={() => navigate('/settings')}
                              className={`${
                                active ? 'bg-gray-50' : ''
                              } flex items-center gap-3 w-full px-4 py-2.5 text-sm text-gray-700 hover:text-gray-900`}
                            >
                              <Cog6ToothIcon className="h-5 w-5" />
                              <span>Settings</span>
                            </button>
                          )}
                        </Menu.Item>
                        <Menu.Item>
                          {({ active }) => (
                            <button
                              onClick={logout}
                              className={`${
                                active ? 'bg-red-50' : ''
                              } flex items-center gap-3 w-full px-4 py-2.5 text-sm text-red-600 hover:text-red-700 border-t border-gray-100 mt-1`}
                            >
                              <ArrowRightOnRectangleIcon className="h-5 w-5" />
                              <span className="font-medium">Sign out</span>
                            </button>
                          )}
                        </Menu.Item>
                      </div>
                    </Menu.Items>
                  </Transition>
                </Menu>
              ) : (
                <div className="relative">
                  <button
                    onClick={() => setShowLoginMenu(!showLoginMenu)}
                    className="h-[42px] px-6 text-white rounded-lg transition-colors text-sm font-semibold flex items-center gap-2"
                    style={{ backgroundColor: '#354F52' }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#2e4346'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#354F52'}
                  >
                    <UserCircleIcon className="h-5 w-5" />
                    <span>Register/Login</span>
                    <ChevronDownIcon className="h-4 w-4" />
                  </button>
                  
                  {showLoginMenu && (
                    <>
                      {/* Backdrop */}
                      <div 
                        className="fixed inset-0 z-40" 
                        onClick={() => setShowLoginMenu(false)}
                        aria-hidden="true"
                      />
                      
                      {/* Menu */}
                      <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50">
                        <div className="px-4 py-2 border-b border-gray-200">
                          <p className="text-sm font-medium text-gray-900">Sign in with:</p>
                        </div>
                        <button
                          onClick={() => { login('google'); setShowLoginMenu(false); }}
                          className="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-100 transition-colors"
                        >
                          <div className="w-6 h-6 flex items-center justify-center flex-shrink-0">
                            <svg viewBox="0 0 24 24" className="w-5 h-5" preserveAspectRatio="xMidYMid meet">
                              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                            </svg>
                          </div>
                          <span className="text-sm font-medium text-gray-700">Google</span>
                        </button>
                        <button
                          onClick={() => { login('facebook'); setShowLoginMenu(false); }}
                          className="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-100 transition-colors"
                        >
                          <div className="w-6 h-6 flex items-center justify-center">
                            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="#1877F2">
                              <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                            </svg>
                          </div>
                          <span className="text-sm font-medium text-gray-700">Facebook</span>
                        </button>
                        <button
                          onClick={() => { login('github'); setShowLoginMenu(false); }}
                          className="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-100 transition-colors"
                        >
                          <div className="w-6 h-6 flex items-center justify-center">
                            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="#181717">
                              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                            </svg>
                          </div>
                          <span className="text-sm font-medium text-gray-700">GitHub</span>
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}
              <div className="flex items-center gap-2">
                <Link
                  to="/data-explorer/map/us/2024/median_household_income"
                  className="h-[42px] px-6 rounded-lg text-white font-semibold hover:shadow-lg transition-all flex items-center"
                  style={{ backgroundColor: '#354F52' }}
                >
                  Explore Now
                </Link>
                <a
                  href={DOCS_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Documentation"
                  aria-label="Documentation"
                  className="h-[42px] w-[42px] shrink-0 rounded-lg border-2 font-semibold text-lg flex items-center justify-center transition-colors border-[#354F52] text-[#354F52] hover:bg-[#354F52]/10"
                >
                  ?
                </a>
              </div>
            </div>

            {/* Mobile Menu Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? (
                <XMarkIcon className="h-6 w-6" />
              ) : (
                <Bars3Icon className="h-6 w-6" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-gray-200 bg-white">
            <div className="px-4 py-3 space-y-1">
              <button
                type="button"
                className="block w-full text-left px-4 py-3 rounded-lg text-base font-medium text-gray-700 hover:bg-gray-100"
                onClick={() => {
                  scrollToTopHeroSearch()
                  setMobileMenuOpen(false)
                }}
              >
                Search
              </button>
              <button
                className="block w-full text-left px-4 py-3 rounded-lg text-base font-medium text-gray-700 hover:bg-gray-100"
                onClick={() => {
                  scrollToSection('how-it-works')
                  setMobileMenuOpen(false)
                }}
              >
                How It Works
              </button>
              <button
                className="block w-full text-left px-4 py-3 rounded-lg text-base font-medium text-gray-700 hover:bg-gray-100"
                onClick={() => {
                  scrollToSection('impact')
                  setMobileMenuOpen(false)
                }}
              >
                Impact
              </button>
              <a
                href={DOCS_URL}
                target="_blank"
                rel="noopener noreferrer"
                title="Documentation"
                aria-label="Documentation"
                className="flex items-center justify-center mx-4 py-3 rounded-lg text-lg font-semibold text-[#354F52] border border-[#354F52] hover:bg-gray-100"
                onClick={() => setMobileMenuOpen(false)}
              >
                ?
              </a>
              <button
                className="block w-full text-left px-4 py-3 rounded-lg text-base font-medium text-gray-700 hover:bg-gray-100"
                onClick={() => {
                  scrollToSection('contact')
                  setMobileMenuOpen(false)
                }}
              >
                Contact
              </button>
            </div>
          </div>
        )}
      </nav>

      {/* Trending Topics Bar - Compact and Professional - Only show if there are topics */}
      {trendingTopics && trendingTopics.length > 0 && (
        <div className="border-b border-slate-400/50 bg-slate-200/95">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2">
            <div className="flex items-center gap-2 md:gap-3">
              {/* Trending Icon */}
              <ArrowTrendingUpIcon className="h-4 w-4 md:h-5 md:w-5 text-green-600 flex-shrink-0" />
              
              {/* Scrollable topics row */}
              <div className="flex items-center gap-1.5 md:gap-2 overflow-x-auto scrollbar-hide flex-1">
                {trendingTopics.slice(0, 12).map((topic: TrendingCause) => (
                  <button
                    key={topic.name}
                    onClick={() => navigate(`/search?q=${encodeURIComponent(topic.name)}`)}
                    className="group inline-flex items-center gap-1 md:gap-1.5 px-2 md:px-2.5 py-0.5 md:py-1 bg-gray-50 border border-gray-200 rounded-md hover:border-[#354F52] hover:bg-[#354F52]/5 transition-all text-xs whitespace-nowrap flex-shrink-0"
                  >
                    <span className="font-medium text-gray-700 group-hover:text-[#354F52]">{topic.name}</span>
                    <PlusIcon className="h-3 w-3 text-gray-400 group-hover:text-[#354F52]" />
                  </button>
                ))}
                <button
                  onClick={() => navigate('/search')}
                  className="inline-flex items-center gap-1 md:gap-1.5 px-2 md:px-2.5 py-0.5 md:py-1 bg-[#354F52] text-white rounded-md hover:bg-[#2e4346] transition-all text-xs whitespace-nowrap flex-shrink-0"
                >
                  <BellIcon className="h-3 w-3" />
                  <span className="font-medium hidden sm:inline">View All</span>
                  <span className="font-medium sm:hidden">All</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Featured Story Hero */}
      <div className="pt-2 pb-4 md:pt-3 md:pb-7 bg-gradient-to-b from-stone-50 via-white to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="animate-[slideUp_0.6s_ease-out]">
                {/* Story Content - Conditional rendering based on type */}
                {FEATURED_STORIES[selectedStoryTab].type === 'hero' ? (
                  /* Hero Search Interface */
                  <div
                    className="relative flex flex-col items-center justify-center pt-1 pb-3 md:pt-2 md:pb-5 px-2 md:px-6"
                    style={{ overflow: 'visible' }}
                  >
                    <div className="text-center max-w-6xl w-full mx-auto space-y-1 md:space-y-1.5">
                      <div className="flex justify-center px-2">
                        <HeroStateSilhouetteBadge
                          location={location}
                          onChangeLocation={() => setSelectedTab(1)}
                          changeLocationLabel="Change your community location"
                        />
                      </div>
                      <h1
                        className="px-1 mb-0 font-semibold leading-[1.07] tracking-tight text-[clamp(2rem,5.5vw,4.125rem)]"
                        style={{ fontFamily: "'Fraunces', serif" }}
                      >
                        <span className="block text-[#0f2b2b]">Your community.</span>
                        <span className="block text-[#1a6b6b] italic mt-0.5 font-semibold">Your decisions.</span>
                      </h1>
                      <p className="mx-auto max-w-[460px] px-2 text-[15px] sm:text-[17px] font-normal leading-[1.65] text-[#6b8a8a]">
                        Follow leaders, track local decisions, and find support — all in one place. Free, forever.
                      </p>

                      <span id="hero-search-hint" className="sr-only">
                        Search examples include school board budget, mental health nonprofit, zoning, and transit.
                      </span>


                      {/* Search Box — single unified rounded pill bar */}
                      <div className="w-full max-w-4xl mx-auto px-1" ref={searchContainerRef}>
                        <div className="relative">
                          <form
                            onSubmit={handleSearch}
                            id="hero-search-primary"
                            className="flex flex-col items-stretch overflow-visible rounded-2xl border-2 bg-white transition-all lg:flex-row"
                            style={{
                              borderColor: focused ? '#1a6b6b' : '#d4e8e8',
                              boxShadow: focused
                                ? '0 0 0 4px rgba(26,107,107,0.2), 0 4px 20px rgba(26,107,107,0.10)'
                                : '0 4px 20px rgba(26,107,107,0.08)',
                            }}
                          >
                            {/* 0. Category scope — dropdown on the left, part of the search action */}
                            <div ref={catRef} className="relative flex items-stretch">
                              <button
                                type="button"
                                onClick={() => setCatOpen((o) => !o)}
                                aria-haspopup="listbox"
                                aria-expanded={catOpen}
                                aria-label="Search category"
                                className="flex items-center gap-2 rounded-t-2xl px-5 py-4 font-medium text-[#0f2b2b] transition-colors hover:bg-[#f7fafb] lg:rounded-l-2xl lg:rounded-tr-none lg:py-0"
                                style={{ fontFamily: "'DM Sans', sans-serif" }}
                              >
                                <span className="text-[15px]">{activeHeroTab.label}</span>
                                {HERO_SEARCH_TAB_DEFS.some((c) => c.activity && c.id !== heroSearchTab) && (
                                  <span
                                    className="h-1.5 w-1.5 rounded-full bg-[#e0723a]"
                                    title="New activity in some categories"
                                  />
                                )}
                                <ChevronDownIcon
                                  className={`h-4 w-4 shrink-0 text-[#6b8a8a] transition-transform ${catOpen ? 'rotate-180' : ''}`}
                                  aria-hidden
                                />
                              </button>

                              {catOpen && (
                                <div
                                  role="listbox"
                                  aria-label="Search category"
                                  className="absolute left-0 top-full z-50 mt-2 w-64 overflow-hidden rounded-xl border border-[#d4e8e8] bg-white py-1.5 text-left shadow-[0_8px_30px_rgba(26,107,107,0.18)]"
                                >
                                  <p className="px-3 pb-2 pt-1 text-[11px] font-semibold uppercase tracking-wide text-[#9bb8b8]">
                                    Search in
                                  </p>
                                  {HERO_SEARCH_TAB_DEFS.map((cat) => {
                                    const selected = heroSearchTab === cat.id
                                    const countBadge = heroCategoryCount(cat)
                                    return (
                                      <button
                                        key={cat.id}
                                        type="button"
                                        role="option"
                                        aria-selected={selected}
                                        onClick={() => {
                                          setHeroSearchTab(cat.id)
                                          setCatOpen(false)
                                        }}
                                        className="flex w-full items-center justify-between px-3 py-2 text-sm transition-colors hover:bg-[#f7fafb]"
                                        style={{
                                          color: selected ? '#1a6b6b' : '#334155',
                                          fontFamily: "'DM Sans', sans-serif",
                                        }}
                                      >
                                        <span className="flex items-center gap-2">
                                          {cat.label}
                                          {cat.activity && (
                                            <span
                                              className="h-1.5 w-1.5 rounded-full bg-[#e0723a]"
                                              title="New activity this week"
                                            />
                                          )}
                                        </span>
                                        <span className="flex items-center gap-2">
                                          {countBadge && (
                                            <span className="text-[11px] font-semibold tabular-nums text-[#9bb8b8]">
                                              {countBadge}
                                            </span>
                                          )}
                                          {selected && <CheckIcon className="h-4 w-4 text-[#1a6b6b]" aria-hidden />}
                                        </span>
                                      </button>
                                    )
                                  })}
                                </div>
                              )}
                            </div>

                            {/* vertical divider between category and query */}
                            <div className="mx-0 hidden w-px self-stretch bg-[#d4e8e8] lg:my-3 lg:block" />

                            {/* 1. Query region (dominant) */}
                            <div className="flex flex-1 items-center pl-4 lg:pl-5">
                              <MagnifyingGlassIcon
                                className="pointer-events-none h-7 w-7 shrink-0 text-[#6b8a8a]"
                                aria-hidden
                              />
                              <label htmlFor="hero-search-input" className="sr-only">
                                Search for topics, people, organizations, or causes
                              </label>
                              <input
                                id="hero-search-input"
                                type="search"
                                name="q"
                                autoComplete="off"
                                placeholder={heroSearchPlaceholder}
                                title='Examples: "school board budget", "mental health nonprofit", "zoning", "transit".'
                                aria-describedby="hero-search-hint"
                                value={keyword}
                                onChange={handleKeywordChange}
                                onFocus={() => {
                                  setFocused(true)
                                  if (keyword.length >= 2) {
                                    setShowSuggestions(true)
                                  }
                                }}
                                onBlur={() => setFocused(false)}
                                className="min-w-0 flex-1 border-0 bg-transparent px-3 py-5 text-lg leading-snug text-[#0f2b2b] placeholder:text-[#9bb8b8] focus:outline-none focus:ring-0 md:py-6 md:text-xl"
                                style={{ fontFamily: "'DM Sans', sans-serif" }}
                              />
                            </div>

                            {/* 2. Location selector region (secondary) */}
                            <div
                              ref={scopeRef}
                              className="relative flex items-stretch border-t border-[#d4e8e8] lg:border-l lg:border-t-0"
                            >
                              {location ? (
                                <button
                                  type="button"
                                  onClick={() => setScopeOpen((o) => !o)}
                                  aria-haspopup="listbox"
                                  aria-expanded={scopeOpen}
                                  aria-label="Search area"
                                  className="flex w-full items-center justify-center gap-2 px-5 py-4 text-[15px] font-medium text-[#0f2b2b] transition-colors hover:bg-[#f7fafb] lg:py-0"
                                  style={{ fontFamily: "'DM Sans', sans-serif" }}
                                >
                                  <MapPinIcon className="h-5 w-5 shrink-0 text-[#1a6b6b]" aria-hidden />
                                  <span className="truncate max-w-[12rem]">{scopeLabel}</span>
                                  <ChevronDownIcon
                                    className={`h-4 w-4 shrink-0 text-[#6b8a8a] transition-transform ${scopeOpen ? 'rotate-180' : ''}`}
                                    aria-hidden
                                  />
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => setSelectedTab(1)}
                                  className="flex w-full items-center justify-center gap-2 px-5 py-4 text-[15px] font-semibold text-[#1a6b6b] transition-colors hover:bg-[#f7fafb] lg:py-0"
                                  style={{ fontFamily: "'DM Sans', sans-serif" }}
                                >
                                  <MapPinIcon className="h-5 w-5 shrink-0" aria-hidden />
                                  <span>Set location</span>
                                </button>
                              )}

                              {/* Custom scope dropdown panel */}
                              {location && scopeOpen && (
                                <div
                                  role="listbox"
                                  aria-label="Search area"
                                  className="absolute right-0 top-full z-50 mt-2 w-72 overflow-hidden rounded-xl border border-[#d4e8e8] bg-white py-1 text-left shadow-[0_8px_30px_rgba(26,107,107,0.18)]"
                                >
                                  {([
                                    { value: 'city', label: `My City (${location.city || '—'})`, disabled: !location.city },
                                    { value: 'county', label: `My County (${location.county || '—'})`, disabled: !location.county },
                                    { value: 'community', label: `School Board (${location.city || '—'})`, disabled: !location.city },
                                    { value: 'state', label: `My State (${location.state})`, disabled: false },
                                    { value: 'national', label: 'National', disabled: false },
                                  ] as { value: string; label: string; disabled: boolean }[]).map((opt) => {
                                    const active = searchScope === opt.value
                                    return (
                                      <button
                                        key={opt.value}
                                        type="button"
                                        role="option"
                                        aria-selected={active}
                                        disabled={opt.disabled}
                                        onClick={() => {
                                          setSearchScope(opt.value)
                                          setScopeOpen(false)
                                        }}
                                        className={`flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm transition-colors ${
                                          opt.disabled
                                            ? 'cursor-not-allowed text-[#9bb8b8]'
                                            : active
                                              ? 'bg-[#e8f4f4] font-semibold text-[#0f2b2b]'
                                              : 'text-[#0f2b2b] hover:bg-[#f7fafb]'
                                        }`}
                                        style={{ fontFamily: "'DM Sans', sans-serif" }}
                                      >
                                        <CheckIcon
                                          className={`h-4 w-4 shrink-0 ${active ? 'text-[#1a6b6b]' : 'text-transparent'}`}
                                          aria-hidden
                                        />
                                        <span className="truncate">{opt.label}</span>
                                      </button>
                                    )
                                  })}
                                  <div className="my-1 border-t border-[#d4e8e8]" />
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setScopeOpen(false)
                                      setSelectedTab(1)
                                    }}
                                    className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm font-medium text-[#1a6b6b] transition-colors hover:bg-[#f7fafb]"
                                    style={{ fontFamily: "'DM Sans', sans-serif" }}
                                  >
                                    <MapIcon className="h-4 w-4 shrink-0" aria-hidden />
                                    Change Location
                                  </button>
                                </div>
                              )}
                            </div>

                            {/* 3. CTA submit */}
                            <button
                              type="submit"
                              aria-label="Search"
                              className="flex items-center justify-center border-t border-[#d4e8e8] bg-[#1a6b6b] px-6 py-4 text-white transition-colors hover:bg-[#2a8585] lg:rounded-r-2xl lg:border-l lg:border-t-0 lg:py-0"
                            >
                              <MagnifyingGlassIcon className="h-6 w-6" aria-hidden />
                            </button>
                          </form>

                                {/* Error Display - Below Input */}
                                {keyword.length >= 2 && previewError && (
                                  <div className="absolute top-full left-0 right-0 mt-2 z-50 bg-red-50 border border-red-200 rounded-lg shadow-lg p-3">
                                    <div className="flex items-start gap-2">
                                      <svg className="h-5 w-5 text-red-400 flex-shrink-0 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                                      </svg>
                                      <div>
                                        <p className="text-sm font-medium text-red-800">Search Error</p>
                                        <p className="text-xs text-red-600 mt-1">
                                          {(previewError as any)?.response?.status === 404 
                                            ? 'API endpoint not found. Server may still be starting.'
                                            : 'Unable to fetch results. Please try again.'}
                                        </p>
                                      </div>
                                    </div>
                                  </div>
                                )}
                                
                                {/* Loading Display - Below Input */}
                                {keyword.length >= 2 && previewLoading && (
                                  <div className="absolute top-full left-0 right-0 mt-2 z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-3">
                                    <div className="flex items-center gap-2">
                                      <svg className="animate-spin h-4 w-4 text-[#354F52]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                      </svg>
                                      <span className="text-sm text-gray-600">Searching...</span>
                                    </div>
                                  </div>
                                )}
                                
                                {/* Preview Results Dropdown */}
                                {keyword.length >= 2 && showSuggestions && !previewLoading && !previewError && previewResults && (
                                  <div className="absolute top-full left-0 right-0 mt-2 z-50 bg-white border border-gray-200 rounded-lg shadow-xl max-h-96 overflow-y-auto">
                                    {/* No Results Message */}
                                    {previewResults.total_results === 0 && (
                                      <div className="px-4 py-8 text-center">
                                        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                        </svg>
                                        <h3 className="mt-2 text-sm font-medium text-gray-900">
                                          No results in <span className="text-[#1a6b6b]">{scopeLabel}</span>
                                        </h3>
                                        {/* Geography is the most common reason a scoped search comes back
                                            empty — offer to widen it before suggesting other fixes. */}
                                        {broaderScope ? (
                                          <>
                                            <p className="mt-1 text-sm text-gray-500">
                                              Nothing here yet for “{keyword.trim()}”. Try a wider area.
                                            </p>
                                            <button
                                              type="button"
                                              onClick={() => setSearchScope(broaderScope.value)}
                                              className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-[#1a6b6b] bg-[#1a6b6b] px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-[#2a8585]"
                                              style={{ fontFamily: "'DM Sans', sans-serif" }}
                                            >
                                              <MapPinIcon className="h-4 w-4" aria-hidden />
                                              Expand to {broaderScope.label}
                                            </button>
                                          </>
                                        ) : (
                                          <p className="mt-1 text-sm text-gray-500">
                                            Try searching for different keywords or check back later.
                                          </p>
                                        )}
                                      </div>
                                    )}
                                    
                                    {/* Causes Section */}
                                    {previewResults.total_results > 0 && previewResults.results?.causes?.length > 0 && (() => {
                                      const filteredCauses = filterResults(previewResults.results.causes, keyword);
                                      return filteredCauses.length > 0 && (
                                        <div className="border-b border-gray-200">
                                          <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                              <HeartIcon className="h-4 w-4 text-gray-500" />
                                              <span className="text-xs font-semibold text-gray-700 uppercase">Causes</span>
                                            </div>
                                            <button
                                              type="button"
                                              onClick={() => handleViewAllCategory('causes')}
                                              className="text-xs text-[#354F52] hover:text-[#2e4346] font-medium"
                                            >
                                              View All
                                            </button>
                                          </div>
                                          {filteredCauses.slice(0, 3).map((result: any, idx: number) => (
                                            <button
                                              key={idx}
                                              type="button"
                                              onClick={() => handleSelectSuggestion(result.title)}
                                              className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                                            >
                                              <HeartIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                                              <div className="flex-1 min-w-0">
                                                <div className="font-medium text-gray-900 truncate">{highlightMatch(result.title, keyword)}</div>
                                                <div className="text-sm text-gray-600 truncate">
                                                  {result.breadcrumb || result.subtitle || result.description}
                                                </div>
                                              </div>
                                            </button>
                                          ))}
                                        </div>
                                      );
                                    })()}

                                    {/* Organizations Section */}
                                    {previewResults.total_results > 0 && previewResults.results?.organizations?.length > 0 && (() => {
                                      const filteredOrgs = filterResults(previewResults.results.organizations, keyword);
                                      return filteredOrgs.length > 0 && (
                                        <div className="border-b border-gray-200">
                                          <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                              <BuildingLibraryIcon className="h-4 w-4 text-gray-500" />
                                              <span className="text-xs font-semibold text-gray-700 uppercase">Organizations</span>
                                            </div>
                                            <button
                                              type="button"
                                              onClick={() => handleViewAllCategory('organizations')}
                                              className="text-xs text-[#354F52] hover:text-[#2e4346] font-medium"
                                            >
                                              View All
                                            </button>
                                          </div>
                                          {filteredOrgs.slice(0, 3).map((result: any, idx: number) => (
                                            <button
                                              key={idx}
                                              type="button"
                                              onClick={() => handleSelectSuggestion(result.title)}
                                              className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                                            >
                                              <BuildingLibraryIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                                              <div className="flex-1 min-w-0">
                                                <div className="font-medium text-gray-900 truncate">{highlightMatch(result.title, keyword)}</div>
                                                <div className="text-sm text-gray-600 truncate">{highlightMatch(result.subtitle || result.description, keyword)}</div>
                                              </div>
                                            </button>
                                          ))}
                                        </div>
                                      );
                                    })()}

                                    {/* Leaders Section (government officials — backend `leaders` search type) */}
                                    {previewResults.total_results > 0 && previewResults.results?.leaders?.length > 0 && (() => {
                                      const filteredLeaders = filterResults(previewResults.results.leaders, keyword);
                                      return filteredLeaders.length > 0 && (
                                        <div className="border-b border-gray-200">
                                          <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                              <UserGroupIcon className="h-4 w-4 text-gray-500" />
                                              <span className="text-xs font-semibold text-gray-700 uppercase">Leaders</span>
                                            </div>
                                            <button
                                              type="button"
                                              onClick={() => handleViewAllCategory('leaders')}
                                              className="text-xs text-[#354F52] hover:text-[#2e4346] font-medium"
                                            >
                                              View All
                                            </button>
                                          </div>
                                          {filteredLeaders.slice(0, 3).map((result: any, idx: number) => (
                                            <button
                                              key={idx}
                                              type="button"
                                              onClick={() => handleSelectSuggestion(result.title)}
                                              className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                                            >
                                              <UserGroupIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                                              <div className="flex-1 min-w-0">
                                                <div className="font-medium text-gray-900 truncate">{highlightMatch(result.title, keyword)}</div>
                                                <div className="text-sm text-gray-600 truncate">
                                                  {highlightMatch(
                                                    [result.metadata?.title, result.metadata?.jurisdiction]
                                                      .filter(Boolean)
                                                      .join(' – ') || result.subtitle || result.description,
                                                    keyword,
                                                  )}
                                                </div>
                                              </div>
                                            </button>
                                          ))}
                                        </div>
                                      );
                                    })()}

                                    {/* People Section (MDM person index — real people incl. residents/homeowners; backend `persons` search type) */}
                                    {previewResults.total_results > 0 && previewResults.results?.persons?.length > 0 && (() => {
                                      const filteredPersons = filterResults(previewResults.results.persons, keyword);
                                      return filteredPersons.length > 0 && (
                                        <div className="border-b border-gray-200">
                                          <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                              <UserCircleIcon className="h-4 w-4 text-gray-500" />
                                              <span className="text-xs font-semibold text-gray-700 uppercase">People</span>
                                            </div>
                                            <button
                                              type="button"
                                              onClick={() => handleViewAllCategory('persons')}
                                              className="text-xs text-[#354F52] hover:text-[#2e4346] font-medium"
                                            >
                                              View All
                                            </button>
                                          </div>
                                          {filteredPersons.slice(0, 3).map((result: any, idx: number) => (
                                            <button
                                              key={idx}
                                              type="button"
                                              onClick={() => handleSelectSuggestion(result.title)}
                                              className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                                            >
                                              <UserCircleIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                                              <div className="flex-1 min-w-0">
                                                <div className="font-medium text-gray-900 truncate">{highlightMatch(result.title, keyword)}</div>
                                                <div className="text-sm text-gray-600 truncate">{highlightMatch(result.subtitle || result.description, keyword)}</div>
                                              </div>
                                            </button>
                                          ))}
                                        </div>
                                      );
                                    })()}

                                    {/* Bills Section */}
                                    {previewResults.total_results > 0 && previewResults.results?.bills?.length > 0 && (() => {
                                      const filteredBills = filterResults(previewResults.results.bills, keyword);
                                      return filteredBills.length > 0 && (
                                        <div className="border-b border-gray-200">
                                          <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                              <DocumentTextIcon className="h-4 w-4 text-gray-500" />
                                              <span className="text-xs font-semibold text-gray-700 uppercase">Bills</span>
                                            </div>
                                            <button
                                              type="button"
                                              onClick={() => handleViewAllCategory('bills')}
                                              className="text-xs text-[#354F52] hover:text-[#2e4346] font-medium"
                                            >
                                              View All
                                            </button>
                                          </div>
                                          {filteredBills.slice(0, 3).map((result: any, idx: number) => (
                                            <button
                                              key={idx}
                                              type="button"
                                              onClick={() => handleSelectSuggestion(result.title)}
                                              className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                                            >
                                              <DocumentTextIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                                              <div className="flex-1 min-w-0">
                                                <div className="font-medium text-gray-900 truncate">{highlightMatch(result.title, keyword)}</div>
                                                <div className="text-sm text-gray-600 truncate">{highlightMatch(result.subtitle || result.description, keyword)}</div>
                                              </div>
                                            </button>
                                          ))}
                                        </div>
                                      );
                                    })()}

                                    {/* Grants Section (GivingTuesday 990 grants — backend `grants` search type) */}
                                    {previewResults.total_results > 0 && previewResults.results?.grants?.length > 0 && (() => {
                                      const filteredGrants = filterResults(previewResults.results.grants, keyword);
                                      return filteredGrants.length > 0 && (
                                        <div className="border-b border-gray-200">
                                          <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                              <BanknotesIcon className="h-4 w-4 text-gray-500" />
                                              <span className="text-xs font-semibold text-gray-700 uppercase">Grants</span>
                                            </div>
                                            <button
                                              type="button"
                                              onClick={() => handleViewAllCategory('grants')}
                                              className="text-xs text-[#354F52] hover:text-[#2e4346] font-medium"
                                            >
                                              View All
                                            </button>
                                          </div>
                                          {filteredGrants.slice(0, 3).map((result: any, idx: number) => (
                                            <button
                                              key={idx}
                                              type="button"
                                              onClick={() => handleSelectSuggestion(result.title)}
                                              className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                                            >
                                              <BanknotesIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                                              <div className="flex-1 min-w-0">
                                                <div className="font-medium text-gray-900 truncate">{highlightMatch(result.title, keyword)}</div>
                                                <div className="text-sm text-gray-600 truncate">{highlightMatch(result.subtitle || result.description, keyword)}</div>
                                              </div>
                                            </button>
                                          ))}
                                        </div>
                                      );
                                    })()}

                                    {/* Topics Section */}
                                    {previewResults.total_results > 0 && previewResults.results?.topics?.length > 0 && (() => {
                                      const filteredTopics = filterResults(previewResults.results.topics, keyword, 'topics');
                                      return filteredTopics.length > 0 && (
                                        <div className="border-b border-gray-200">
                                          <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                              <ChatBubbleBottomCenterTextIcon className="h-4 w-4 text-gray-500" />
                                              <span className="text-xs font-semibold text-gray-700 uppercase">Topics</span>
                                            </div>
                                            <button
                                              type="button"
                                              onClick={() => handleViewAllCategory('topics')}
                                              className="text-xs text-[#354F52] hover:text-[#2e4346] font-medium"
                                            >
                                              View All
                                            </button>
                                          </div>
                                          {filteredTopics.slice(0, 3).map((result: any, idx: number) => (
                                            <button
                                              key={idx}
                                              type="button"
                                              onClick={() => handleSelectSuggestion(result.title)}
                                              className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                                            >
                                              <ChatBubbleBottomCenterTextIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                                              <div className="flex-1 min-w-0">
                                                <div className="font-medium text-gray-900 truncate">{highlightMatch(result.title, keyword)}</div>
                                                <div className="text-sm text-gray-600 truncate">{highlightMatch(result.subtitle || result.description, keyword)}</div>
                                              </div>
                                            </button>
                                          ))}
                                        </div>
                                      );
                                    })()}

                                    {/* Decisions Section */}
                                    {previewResults.total_results > 0 && previewResults.results?.decisions?.length > 0 && (() => {
                                      const filteredDecisions = filterResults(previewResults.results.decisions, keyword);
                                      return filteredDecisions.length > 0 && (
                                        <div className="border-b border-gray-200">
                                          <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                              <ScaleIcon className="h-4 w-4 text-gray-500" />
                                              <span className="text-xs font-semibold text-gray-700 uppercase">Decisions</span>
                                            </div>
                                            <button
                                              type="button"
                                              onClick={() => handleViewAllCategory('decisions')}
                                              className="text-xs text-[#354F52] hover:text-[#2e4346] font-medium"
                                            >
                                              View All
                                            </button>
                                          </div>
                                          {filteredDecisions.slice(0, 3).map((result: any, idx: number) => (
                                            <button
                                              key={idx}
                                              type="button"
                                              onClick={() => handleSelectSuggestion(result.title)}
                                              className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                                            >
                                              <ScaleIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                                              <div className="flex-1 min-w-0">
                                                <div className="font-medium text-gray-900 truncate">{highlightMatch(result.title, keyword)}</div>
                                                <div className="text-sm text-gray-600 truncate">{highlightMatch(result.subtitle || result.description, keyword)}</div>
                                              </div>
                                            </button>
                                          ))}
                                        </div>
                                      );
                                    })()}

                                    {/* Footer with total results */}
                                    {previewResults.total_results > 0 && (
                                      <div className="px-4 py-3 bg-gray-50 text-center border-t border-gray-200">
                                        <button
                                          type="submit"
                                          className="text-sm text-[#354F52] hover:text-[#2e4346] font-medium"
                                        >
                                          See all {previewResults.total_results} results →
                                        </button>
                                      </div>
                                    )}
                                  </div>
                                )}
                        </div>

                        {/* State-aware footer: trending + browse when idle, scope
                            hint when a category or query narrows the search. */}
                        {(() => {
                          const trimmed = keyword.trim()
                          const intent =
                            trimmed.length > 0 ? 'query' : heroSearchTab === 'all' ? 'idle' : 'browse'

                          if (intent === 'idle') {
                            const heroTrending =
                              trendingTopics && trendingTopics.length > 0
                                ? trendingTopics
                                : FALLBACK_TRENDING
                            return (
                              <div className="mt-4 flex items-center gap-3 text-left">
                                <span className="hidden shrink-0 items-center gap-1.5 text-[#9bb8b8] sm:inline-flex">
                                  <ArrowTrendingUpIcon className="h-4 w-4" style={{ color: '#e0723a' }} aria-hidden />
                                  Trending
                                </span>
                                <div className="relative min-w-0 flex-1">
                                  <div className="scrollbar-hide flex items-center gap-2 overflow-x-auto py-0.5">
                                    {heroTrending.slice(0, 8).map((t: { name: string }) => (
                                      <button
                                        key={t.name}
                                        type="button"
                                        onClick={() => setKeyword(t.name)}
                                        className="inline-flex shrink-0 items-center whitespace-nowrap rounded-full border border-[#d4e8e8] bg-white px-3 py-1.5 text-sm font-medium text-[#4a6a6a] transition-colors hover:border-[#1a6b6b]/45 hover:text-[#0f2b2b]"
                                        style={{ fontFamily: "'DM Sans', sans-serif" }}
                                      >
                                        {t.name}
                                      </button>
                                    ))}
                                  </div>
                                  {/* edge fade masks */}
                                  <div className="pointer-events-none absolute inset-y-0 left-0 w-6 bg-gradient-to-r from-white to-transparent" />
                                  <div className="pointer-events-none absolute inset-y-0 right-0 w-6 bg-gradient-to-l from-white to-transparent" />
                                </div>
                                <button
                                  type="button"
                                  onClick={() => navigate('/search')}
                                  className="inline-flex shrink-0 items-center gap-1 text-sm font-medium text-[#1a6b6b] underline-offset-2 transition-colors hover:underline"
                                  style={{ fontFamily: "'DM Sans', sans-serif" }}
                                >
                                  Browse topics
                                  <ChevronDownIcon className="h-4 w-4 -rotate-90" aria-hidden />
                                </button>
                              </div>
                            )
                          }

                          if (intent === 'browse') {
                            const countBadge = heroCategoryCount(activeHeroTab)
                            return (
                              <p
                                className="mt-3 text-sm text-[#6b8a8a]"
                                style={{ fontFamily: "'DM Sans', sans-serif" }}
                              >
                                Browsing{' '}
                                <span className="font-semibold text-[#0f2b2b]">
                                  {countBadge ? `all ${countBadge} ` : 'all '}
                                  {activeHeroTab.label.toLowerCase()}
                                </span>{' '}
                                in <span className="font-semibold text-[#1a6b6b]">{scopeLabel}</span>
                                {' — start typing to filter'}
                              </p>
                            )
                          }

                          return (
                            <p
                              className="mt-3 text-sm text-[#6b8a8a]"
                              style={{ fontFamily: "'DM Sans', sans-serif" }}
                            >
                              Searching <span className="font-semibold text-[#0f2b2b]">{scopeNoun}</span> in{' '}
                              <span className="font-semibold text-[#1a6b6b]">{scopeLabel}</span>
                            </p>
                          )
                        })()}
                      </div>
                    </div>

                  </div>
                ) : (
                  /* Regular Story with Image */
                  <Link to={FEATURED_STORIES[selectedStoryTab].link} className="group block">
                    <div className="relative overflow-hidden rounded-2xl bg-gray-900 shadow-2xl h-[500px]">
                      <img
                        src={FEATURED_STORIES[selectedStoryTab].image}
                        alt={FEATURED_STORIES[selectedStoryTab].title}
                        className="absolute inset-0 w-full h-full object-cover opacity-60 group-hover:opacity-50 transition-opacity duration-300"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black via-black/50 to-transparent" />
                      <div className="absolute bottom-0 left-0 right-0 p-8 md:p-12">
                        <h2 className="text-3xl md:text-5xl font-bold text-white mb-4 leading-tight group-hover:text-primary-300 transition-colors">
                          {FEATURED_STORIES[selectedStoryTab].title}
                        </h2>
                        <p className="text-lg md:text-xl text-gray-200 max-w-3xl">
                          {FEATURED_STORIES[selectedStoryTab].subtitle}
                        </p>
                      </div>

                      {/* Story Navigation Arrows */}
                      <button
                        onClick={(e) => {
                          e.preventDefault()
                          setSelectedStoryTab((prev) => (prev === 0 ? FEATURED_STORIES.length - 1 : prev - 1))
                        }}
                        className="absolute left-4 top-1/2 -translate-y-1/2 w-12 h-12 bg-white/20 backdrop-blur-sm hover:bg-white/30 rounded-full flex items-center justify-center text-white transition-all"
                        aria-label="Previous story"
                      >
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                      </button>
                      <button
                        onClick={(e) => {
                          e.preventDefault()
                          setSelectedStoryTab((prev) => (prev === FEATURED_STORIES.length - 1 ? 0 : prev + 1))
                        }}
                        className="absolute right-4 top-1/2 -translate-y-1/2 w-12 h-12 bg-white/20 backdrop-blur-sm hover:bg-white/30 rounded-full flex items-center justify-center text-white transition-all"
                        aria-label="Next story"
                      >
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>

                    </div>
                  </Link>
                )}
              </div>
        </div>
      </div>

      {/* Find My Community Modal */}
      {selectedTab === 1 && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setSelectedTab(0)}>
          <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-2xl w-full" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold" style={{ color: '#354F52' }}>
                {location ? 'Change My Community' : 'Find My Community'}
              </h2>
              <button
                onClick={() => setSelectedTab(0)}
                className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                aria-label="Close"
              >
                <XMarkIcon className="h-6 w-6 text-gray-500" />
              </button>
            </div>
            <p className="text-gray-600 mb-6">
              {location
                ? `Currently set to ${formatCommunityPlaceLine(location)}. Enter a new address to change your community.`
                : 'Enter your address to find local organizations, city councils, county boards, school districts, and charities near you'}
            </p>
            <AddressLookup onLocationFound={handleAddressFound} />
            
            {/* Success message */}
            {location && (
              <div className="mt-8 p-6 bg-green-50 border-2 border-green-200 rounded-xl">
                <div className="flex items-start gap-3 mb-4">
                  <CheckCircleIcon className="h-6 w-6 text-green-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h3 className="text-lg font-bold text-green-900 mb-1">
                      Location Set Successfully!
                    </h3>
                    <p className="text-green-700">
                      You&apos;re all set for <strong>{formatCommunityPlaceLine(location)}</strong>. You can now
                      search for topics in your community.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedTab(0)}
                  className="w-full bg-green-600 hover:bg-green-700 text-white px-6 py-4 rounded-lg font-semibold text-lg flex items-center justify-center gap-2 transition-all shadow-lg hover:shadow-xl"
                >
                  <MagnifyingGlassIcon className="h-6 w-6" />
                  Start Searching
                  <ArrowRightIcon className="h-5 w-5" />
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* How It Works — aligned with /explore “From information to impact” flow */}
      <section id="how-it-works" className="py-16 px-4 bg-gradient-to-br from-gray-50 to-gray-100">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12 max-w-3xl mx-auto">
            <p className="text-xs font-semibold uppercase tracking-widest text-teal-800/90 mb-2">How it works</p>
            <h2 className="text-3xl md:text-4xl font-bold mb-3 text-gray-900">From information to impact</h2>
            <div className="w-24 h-1 bg-gradient-to-r from-[#52796F] to-[#84A98C] mx-auto rounded mb-4"></div>
            <p className="text-lg text-gray-600 leading-relaxed">
              Start by choosing a cause, make a plan (learn the record, decide who to work with, then show up), find help
              when someone needs direct support, track the decisions that matter, and build on open data.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 lg:gap-3">
            {(
              [
                {
                  href: `/explore#${EXPLORE_CAUSES_ID}`,
                  Icon: MapPinIcon,
                  title: 'Choose a cause',
                  blurb: 'Roads, schools, safety, family, health, or something else.',
                },
                {
                  href: `/explore#${EXPLORE_PLAN_ID}`,
                  Icon: ClipboardDocumentListIcon,
                  title: 'Make a plan',
                  blurb: 'Personal and community paths, allies, and outcomes.',
                },
                {
                  href: `/explore#${EXPLORE_FIND_HELP_ID}`,
                  Icon: HeartIcon,
                  title: 'Find help',
                  blurb: 'Nonprofits, programs, and family supports.',
                },
                {
                  href: `/explore#${EXPLORE_TRACK_DECISIONS_ID}`,
                  Icon: ChartBarIcon,
                  title: 'Track decisions',
                  blurb: 'Meetings, budgets, maps, and verification.',
                },
                {
                  href: `/explore#${EXPLORE_BUILD_ID}`,
                  Icon: CodeBracketIcon,
                  title: 'Build with data',
                  blurb: 'Open datasets, APIs, and civic tooling.',
                },
              ] as const
            ).map((step) => (
              <Link
                key={step.title}
                to={step.href}
                className="flex flex-col rounded-xl border border-gray-200 bg-white p-5 text-left shadow-sm transition-all hover:border-teal-700/40 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
              >
                <span className="mb-3 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#354F52] text-white">
                  <step.Icon className="h-5 w-5" aria-hidden />
                </span>
                <h3 className="text-base font-bold text-gray-900">{step.title}</h3>
                <p className="mt-2 text-sm leading-snug text-gray-600">{step.blurb}</p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Impact Section */}
      <section id="impact" className="py-16 px-4 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-2" style={{ color: '#354F52' }}>
              Our Impact
            </h2>
            <div className="w-24 h-1 bg-gradient-to-r from-[#52796F] to-[#84A98C] mx-auto rounded mb-4"></div>
            <p className="mb-10 text-lg text-gray-600">
              One platform connecting residents, leaders, and funders to what's really happening on the ground
            </p>
          </div>

          {/* Mission + PBC */}
          <div id="mission" className="max-w-3xl mx-auto text-center bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-2xl p-8">
            <h2 className="text-3xl md:text-4xl font-bold mb-2" style={{ color: '#354F52' }}>
              Our Mission
            </h2>
            <div className="w-24 h-1 bg-gradient-to-r from-[#52796F] to-[#84A98C] mx-auto rounded mb-4"></div>
            <p className="text-lg text-gray-600 mb-4">
              CommunityOne: One Map for Every Community
            </p>
            <p className="text-lg text-gray-700 leading-relaxed mb-3">
              Every person deserves to find the help they need and have a voice in the decisions that shape their lives. But public resources are scattered, gaps go unseen, and communities are left navigating alone.
            </p>
            <p className="text-lg text-gray-700 leading-relaxed mb-6">
              CommunityOne changes that. One platform connects residents, leaders, and funders to what's really happening on the ground — so no community has to fight just to be seen.
            </p>

            {/* Temporarily hidden until PBC approval — restore when ready.
            <div className="border-t border-gray-200 pt-6 mb-6">
              <p className="text-xs font-bold uppercase tracking-widest text-[#52796F] mb-2">Public Benefit Corporation</p>
              <p className="text-base text-gray-600 leading-relaxed">
                CommunityOne is a public benefit corporation with a fiscal-sponsored nonprofit 501(c)(3). We are solely funded by mission-aligned impact investors and philanthropic institutions.
              </p>
            </div>
            */}

            <Link
              to="/explore"
              className="inline-flex items-center gap-2 px-6 py-3 bg-[#354F52] text-white rounded-lg hover:bg-[#2e4346] transition-colors font-semibold"
            >
              Start Exploring <ArrowRightIcon className="h-5 w-5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <div className="py-16" style={{ backgroundColor: '#354F52' }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center mb-12 text-white">Explore the Platform</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            <Link to="/data-explorer/map/us/2024/median_household_income" className="group">
              <div className="bg-white border-2 border-gray-200 rounded-lg p-6 hover:border-primary-500 transition-colors">
                <ChartBarIcon className="h-10 w-10 text-primary-600 mb-4" />
                <h3 className="text-xl font-semibold mb-2" style={{ color: '#354F52' }}>Data & Trends</h3>
                <p className="text-gray-600 mb-4">
                  Statistics, charts, and insights. See what's happening across communities.
                </p>
                <span className="text-primary-600 font-medium inline-flex items-center">
                  View Data <ArrowRightIcon className="h-4 w-4 ml-2" />
                </span>
              </div>
            </Link>

            <Link to="/documents" className="group">
              <div className="bg-white border-2 border-gray-200 rounded-lg p-6 hover:border-primary-500 transition-colors">
                <DocumentTextIcon className="h-10 w-10 text-primary-600 mb-4" />
                <h3 className="text-xl font-semibold mb-2" style={{ color: '#354F52' }}>Meeting Minutes</h3>
                <p className="text-gray-600 mb-4">
                  See what local governments are discussing, deciding, and spending
                </p>
                <span className="text-primary-600 font-medium inline-flex items-center">
                  Browse Minutes <ArrowRightIcon className="h-4 w-4 ml-2" />
                </span>
              </div>
            </Link>

            <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className="group">
              <div className="bg-white border-2 border-gray-200 rounded-lg p-6 hover:border-primary-500 transition-colors">
                <BookOpenIcon className="h-10 w-10 text-primary-600 mb-4" />
                <h3 className="text-xl font-semibold mb-2" style={{ color: '#354F52' }}>Learn More</h3>
                <p className="text-gray-600 mb-4">
                  Discover how to track local decisions and find charities
                </p>
                <span className="text-primary-600 font-medium inline-flex items-center">
                  Getting Started <ArrowRightIcon className="h-4 w-4 ml-2" />
                </span>
              </div>
            </a>
          </div>
        </div>
      </div>

      {/* Contact Us CTA */}
      <section id="contact" className="py-20 px-4 bg-gradient-to-br from-gray-50 to-blue-50">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-2xl shadow-xl p-12 text-center">
            <EnvelopeIcon className="h-16 w-16 mx-auto mb-6" style={{ color: '#354F52' }} />
            <h2 className="text-4xl md:text-5xl font-bold mb-4" style={{ color: '#354F52' }}>
              Get in Touch
            </h2>
            <p className="text-xl text-gray-600 mb-8">
              Questions, feedback, or ideas? We'd love to hear from you.
              Report bugs, request features, or ask questions about jurisdiction coverage.
            </p>
            <div className="flex justify-center">
              <a
                href="mailto:hello@communityone.com"
                className="inline-flex items-center justify-center px-8 py-4 rounded-lg text-white font-semibold transition-all hover:shadow-lg"
                style={{ backgroundColor: '#354F52' }}
              >
                <EnvelopeIcon className="h-5 w-5 mr-2" />
                Email Us
              </a>
            </div>
            <p className="text-sm text-gray-500 mt-6">
              Your feedback helps us improve the platform for everyone.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-4 bg-gray-900 text-white">
        <div className="max-w-7xl mx-auto text-center">
          <div className="flex items-center justify-center gap-3 mb-6">
            <img 
              src="/communityone_logo.svg" 
              alt="CommunityOne Logo" 
              className="h-10 opacity-90"
            />
            <span className="text-xl font-bold">Open Navigator</span>
          </div>
          <p className="text-gray-400 mb-6">
            Making community impact accessible to everyone
          </p>
          
          {/* Social Media Links */}
          <div className="flex justify-center gap-6 mb-8">
            <a href="https://www.instagram.com/getcommunityone/" target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white transition-colors" aria-label="Instagram">
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
              </svg>
            </a>
            <a href="https://www.facebook.com/getcommunityone" target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white transition-colors" aria-label="Facebook">
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
              </svg>
            </a>
            <a href="https://x.com/getcommunityone/" target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white transition-colors" aria-label="X (Twitter)">
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
              </svg>
            </a>
            <a href="https://www.linkedin.com/company/getcommunityone" target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white transition-colors" aria-label="LinkedIn">
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
              </svg>
            </a>
            <a href="https://www.youtube.com/@getcommunityone" target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white transition-colors" aria-label="YouTube">
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
              </svg>
            </a>
            <a href="https://discord.gg/uH6Dytek" target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white transition-colors" aria-label="Discord">
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
              </svg>
            </a>
            <a href="https://communityone-hq.slack.com/" target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white transition-colors" aria-label="Slack">
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/>
              </svg>
            </a>
            <a href="https://github.com/getcommunityone" target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white transition-colors" aria-label="GitHub">
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
            </a>
          </div>
          
          <nav aria-label="Site sections" className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-gray-400 max-w-4xl mx-auto px-2">
            <Link to="/explore" className="hover:text-white transition-colors">
              Take action
            </Link>
            <Link to="/search" className="hover:text-white transition-colors">
              Search
            </Link>
            <Link to="/jurisdictions" className="hover:text-white transition-colors">
              Jurisdictions
            </Link>
            <Link to="/nonprofits" className="hover:text-white transition-colors">
              Nonprofits
            </Link>
            <Link to="/analytics" className="hover:text-white transition-colors">
              Analytics
            </Link>
            <Link to="/policy-map" className="hover:text-white transition-colors">
              Policy map
            </Link>
            <Link to="/documents" className="hover:text-white transition-colors">
              Documents
            </Link>
            <Link to="/dashboard" className="hover:text-white transition-colors">
              Dashboard
            </Link>
            <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">
              Documentation
            </a>
            <a
              href={import.meta.env.PROD ? 'https://www.communityone.com/api/docs' : 'http://localhost:8000/docs'}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-white transition-colors"
            >
              API
            </a>
          </nav>
          <p className="text-gray-500 text-sm mt-6">
            © 2026 CommunityOne. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  )
}
