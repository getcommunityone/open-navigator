import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import React, { useState, Fragment, useEffect, useRef } from 'react'
import { Tab, Menu, Transition } from '@headlessui/react'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { 
  MagnifyingGlassIcon, 
  DocumentTextIcon, 
  ChartBarIcon,
  BuildingLibraryIcon,
  ArrowRightIcon,
  BookOpenIcon,
  CurrencyDollarIcon,
  HomeIcon,
  TruckIcon,
  HeartIcon,
  AcademicCapIcon,
  BriefcaseIcon,
  ScaleIcon,
  UserGroupIcon,
  ChatBubbleBottomCenterTextIcon,
  CodeBracketIcon,
  BuildingOfficeIcon,
  UserIcon,
  CheckCircleIcon,
  MapPinIcon,
  PlusIcon,
  BellIcon,
  ArrowTrendingUpIcon,
  Bars3Icon,
  XMarkIcon,
  UserCircleIcon,
  ChevronDownIcon,
  MapIcon,
  BellAlertIcon,
  EnvelopeIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon
} from '@heroicons/react/24/outline'
import { useAuth } from '../contexts/AuthContext'
import AddressLookup from '../components/AddressLookup'
import { useLocation as useLocationContext } from '../contexts/LocationContext'

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

export default function Home() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [keyword, setKeyword] = useState('')
  const [debouncedKeyword, setDebouncedKeyword] = useState('')
  const [searchScope, setSearchScope] = useState('city') // city, county, state, national, community (school)
  const [selectedTab, setSelectedTab] = useState(0)
  const [selectedStoryTab, setSelectedStoryTab] = useState(0)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [showLoginMenu, setShowLoginMenu] = useState(false)
  const { location, setLocation } = useLocationContext()
  const { user, isAuthenticated, login, logout, isLoading } = useAuth()
  const searchContainerRef = useRef<HTMLDivElement>(null)

  const DOCS_URL = import.meta.env.PROD ? 'https://www.communityone.com/docs/intro' : 'http://localhost:3000/docs/intro'
  
  // Debounce keyword input (300ms delay)
  useEffect(() => {
    const timer = setTimeout(() => {
      console.log('⏱️ [Home] Debounced keyword update:', keyword);
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

  // Fetch stats based on location AND search scope
  const { data: locationStats } = useQuery({
    queryKey: ['location-stats', location?.state, location?.city, location?.county, searchScope],
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
      
      console.log('📊 [Home] Fetching stats for scope:', searchScope, 'params:', params);
      const response = await api.get('/stats', { params });
      console.log('📊 [Home] Location stats:', response.data);
      return response.data;
    },
    enabled: !!location,
    staleTime: 5 * 60 * 1000 // Cache for 5 minutes
  });

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
      console.log('📊 [Home] Using location-specific trending causes:', locationStats.trending_causes)
      
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
    console.log('📊 [Home] Using global trending causes from API')
    const globalCauses = trendingData?.causes || []
    return globalCauses.filter((cause: any) => (cause.decision_count || 0) > 0)
  }, [locationStats, trendingData])

  // Generate dynamic stats text based on location (memoized for performance)
  const statsText = React.useMemo(() => {
    console.log('📊 [Home] Recomputing stats text, locationStats:', locationStats, 'location:', location);
    
    // If national scope selected, always show national stats
    if (searchScope === 'national') {
      return '90,000+ jurisdictions • 1.8M nonprofits • 75K+ leaders • 169 decisions • 650+ causes • 100% free';
    }
    
    // If no location data or stats are loading, show national stats
    if (!locationStats) {
      return '90,000+ jurisdictions • 1.8M nonprofits • 75K+ leaders • 169 decisions • 650+ causes • 100% free';
    }

    // If database returns zeros, show location-specific message
    if (locationStats.jurisdictions === 0 && 
        locationStats.nonprofits === 0 && 
        locationStats.contacts === 0) {
      // Show which location we're looking at
      const locationName = locationStats.city || locationStats.county || locationStats.state || 'this area';
      return `Searching ${locationName} • Database loading • Check back soon • 100% free`;
    }

    const parts = [];
    
    // Format jurisdictions count
    if (locationStats.jurisdictions && locationStats.jurisdictions > 0) {
      const count = locationStats.jurisdictions >= 1000 
        ? `${(locationStats.jurisdictions / 1000).toFixed(1)}K` 
        : locationStats.jurisdictions.toLocaleString();
      parts.push(`${count} jurisdiction${locationStats.jurisdictions === 1 ? '' : 's'}`);
    }
    
    // Format nonprofits count
    if (locationStats.nonprofits && locationStats.nonprofits > 0) {
      const count = locationStats.nonprofits >= 1000 
        ? `${(locationStats.nonprofits / 1000).toFixed(1)}K` 
        : locationStats.nonprofits.toLocaleString();
      parts.push(`${count} nonprofit${locationStats.nonprofits === 1 ? '' : 's'}`);
    }
    
    // Format contacts count (leaders)
    if (locationStats.contacts && locationStats.contacts > 0) {
      const count = locationStats.contacts >= 1000 
        ? `${(locationStats.contacts / 1000).toFixed(1)}K` 
        : locationStats.contacts.toLocaleString();
      parts.push(`${count} leader${locationStats.contacts === 1 ? '' : 's'}`);
    }
    
    // Format decisions count
    if (locationStats.decisions && locationStats.decisions > 0) {
      const count = locationStats.decisions >= 1000 
        ? `${(locationStats.decisions / 1000).toFixed(1)}K` 
        : locationStats.decisions.toLocaleString();
      parts.push(`${count} decision${locationStats.decisions === 1 ? '' : 's'}`);
    }
    
    // Add causes count (estimate or fixed)
    parts.push('650+ causes');
    parts.push('100% free');
    
    return parts.join(' • ');
  }, [locationStats, location, searchScope]);

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

  // Generate dynamic description based on search scope
  const getDescription = () => {
    if (searchScope === 'national') {
      return 'Search leaders, charities, and causes across the United States';
    }
    if (searchScope === 'state' && location?.state) {
      return `Follow leaders, charities, and causes in ${location.state}.`;
    }
    if (searchScope === 'county' && location?.county) {
      return `Follow leaders, charities, and causes in ${location.county}.`;
    }
    if (searchScope === 'community' && location?.city) {
      return `Follow school boards, educators, and education causes in ${location.city}.`;
    }
    // Default for city or when location exists
    if (location?.city) {
      return `Follow leaders, charities, and causes in ${location.city}.`;
    }
    return 'Follow leaders, charities, and causes in your community.';
  };

  // Live search preview (type-ahead with actual results from API)
  const { data: previewResults, isLoading: previewLoading, error: previewError } = useQuery({
    queryKey: ['search-preview-home', debouncedKeyword, location?.state, searchScope],
    queryFn: async () => {
      console.log('🔍 [Home] Fetching preview for:', debouncedKeyword, 'in state:', location?.state);
      if (!debouncedKeyword || debouncedKeyword.length < 2) {
        console.log('⚠️ [Home] Query too short, skipping');
        return null;
      }
      
      try {
        const url = '/search/';
        const params: any = {
          q: debouncedKeyword,
          types: 'causes,contacts,organizations,bills,topics,decisions',
          limit: 12  // Higher limit to show results from multiple types
        };
        
        // Add state filter based on search scope (don't filter if scope is 'national')
        if (location && location.state && searchScope !== 'national') {
          params.state = location.state;
          console.log('📍 [Home] Filtering by state:', location.state);
        } else if (searchScope === 'national') {
          console.log('🌎 [Home] National search - no state filter');
        }
        
        console.log('📤 [Home] API Request:', url, params);
        const response = await api.get(url, { params });
        console.log('📥 [Home] API Response:', response.data);
        console.log('📊 [Home] Total results:', response.data.total_results);
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
    console.log('🔄 [Home] Preview state:', {
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
      setSelectedTab(1) // Switch to "Find/Change My Community" tab
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

  const handleSelectSuggestion = (suggestion: string) => {
    setKeyword(suggestion)
    setShowSuggestions(false)
    
    // Navigate to search results with the selected suggestion
    const params = new URLSearchParams()
    params.set('q', suggestion)
    if (location && location.state) {
      params.set('state', location.state)
    }
    navigate(`/search?${params.toString()}`)
  }

  const handleViewAllCategory = (category: string) => {
    if (keyword.trim().length >= 2) {
      const params = new URLSearchParams()
      params.set('q', keyword)
      params.set('types', category)
      if (location && location.state) {
        params.set('state', location.state)
      }
      navigate(`/search?${params.toString()}`)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    console.log('🔍 [Home] Search submitted:', { keyword, location: location?.state, searchScope });
    
    if (keyword.trim()) {
      const params = new URLSearchParams()
      params.set('q', keyword.trim())
      
      // Add location context if available
      if (location && location.state) {
        params.set('state', location.state)
        console.log('📍 [Home] Adding state filter:', location.state);
      }
      
      const searchUrl = `/search?${params.toString()}`;
      console.log('🚀 [Home] Navigating to:', searchUrl);
      navigate(searchUrl)
    } else {
      console.warn('⚠️ [Home] Search submitted with empty keyword');
    }
  }

  const handleAddressFound = (locationData: any) => {
    console.log('📍 [Home] Address found, updating location:', locationData);
    setLocation({
      address: locationData.address,
      state: locationData.state,
      county: locationData.county,
      city: locationData.city,
      latitude: locationData.latitude,
      longitude: locationData.longitude,
    })
    console.log('📍 [Home] Location updated, should trigger stats refetch');
    console.log('📍 [Home] New subtitle will be:', `Track Decisions in ${locationData.city}, ${locationData.state}`);
    
    // Close the modal and return to search tab
    setSelectedTab(0);
  }

  // Debug: Log when location changes
  useEffect(() => {
    console.log('📍 [Home] Location state changed:', location);
    console.log('📍 [Home] Current subtitle:', getSubtitle());
  }, [location]);

  const categories = [
    { name: 'People', icon: UserGroupIcon, query: '', route: '/people' },
    { name: 'Community', icon: CodeBracketIcon, query: 'community engagement' },
    { name: 'Budget', icon: CurrencyDollarIcon, query: 'budget funding' },
    { name: 'Housing', icon: HomeIcon, query: 'housing affordable' },
    { name: 'Transport', icon: TruckIcon, query: 'transportation transit' },
    { name: 'Health', icon: HeartIcon, query: 'health dental' },
    { name: 'Education', icon: AcademicCapIcon, query: 'education school' },
    { name: 'Jobs', icon: BriefcaseIcon, query: 'employment jobs' },
    { name: 'Legal', icon: ScaleIcon, query: 'legal services' },
    { name: 'Charities', icon: BuildingLibraryIcon, query: '', route: '/nonprofits' },
  ]

  const quickSearch = (category: { query: string, route?: string }) => {
    if (category.route) {
      if (category.route.startsWith('http')) {
        window.open(category.route, '_blank')
      } else {
        navigate(category.route)
      }
    } else if (category.query) {
      navigate(`/search?q=${encodeURIComponent(category.query)}`)
    }
  }

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

  return (
    <div className="min-h-screen bg-white">
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
                onClick={() => scrollToSection('features')} 
                className="text-sm font-medium text-gray-600 hover:text-[#354F52] transition-colors pb-1 border-b-2 border-transparent hover:border-[#354F52] cursor-pointer"
              >
                Features
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
              <a 
                href={DOCS_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-gray-600 hover:text-[#354F52] transition-colors pb-1 border-b-2 border-transparent hover:border-[#354F52]"
              >
                Documentation
              </a>
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
                          console.log('✅ Avatar loaded successfully:', user.avatar_url?.substring(0, 50));
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
              <Link
                to="/explore"
                className="h-[42px] px-6 rounded-lg text-white font-semibold hover:shadow-lg transition-all flex items-center"
                style={{ backgroundColor: '#354F52' }}
              >
                Explore Now
              </Link>
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
                className="block w-full text-left px-4 py-3 rounded-lg text-base font-medium text-gray-700 hover:bg-gray-100"
                onClick={() => {
                  scrollToSection('features')
                  setMobileMenuOpen(false)
                }}
              >
                Features
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
                className="block px-4 py-3 rounded-lg text-base font-medium text-gray-700 hover:bg-gray-100"
                onClick={() => setMobileMenuOpen(false)}
              >
                Documentation
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
        <div className="border-b border-gray-200 bg-white">
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

      {/* Featured Story Hero with gradient background */}
      <div className="py-8" style={{ background: 'linear-gradient(135deg, #F1F5F9 0%, #E8EEF2 100%)' }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex gap-6">
            {/* Left Sidebar Navigation */}
            <div className="hidden lg:block w-64 flex-shrink-0">
              <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-6 sticky top-24 h-[500px] flex flex-col">
                <h3 className="text-lg font-bold mb-4" style={{ color: '#354F52' }}>
                  Quick Navigation
                </h3>
                <nav className="space-y-2 flex-1">
                  <a
                    href="#mission"
                    onClick={(e) => { e.preventDefault(); scrollToSection('mission'); }}
                    className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-[#354F52] hover:text-white transition-all group"
                  >
                    <HeartIcon className="h-5 w-5 group-hover:scale-110 transition-transform" />
                    <span className="font-medium">Our Mission</span>
                  </a>
                  <Link
                    to="/explore"
                    className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-[#354F52] hover:text-white transition-all group"
                  >
                    <MapIcon className="h-5 w-5 group-hover:scale-110 transition-transform" />
                    <span className="font-medium">Explore</span>
                  </Link>
                  <Link
                    to="/policy-map"
                    className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-[#354F52] hover:text-white transition-all group"
                  >
                    <ChartBarIcon className="h-5 w-5 group-hover:scale-110 transition-transform" />
                    <span className="font-medium">Policy Map</span>
                  </Link>
                  <Link
                    to="/nonprofits"
                    className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-[#354F52] hover:text-white transition-all group"
                  >
                    <BuildingLibraryIcon className="h-5 w-5 group-hover:scale-110 transition-transform" />
                    <span className="font-medium">Charity Search</span>
                  </Link>
                </nav>
                
                {/* Additional Info */}
                <div className="mt-auto pt-6 border-t border-gray-200">
                  <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                    <BellAlertIcon className="h-4 w-4 text-primary-600" />
                    <span className="font-semibold">Stay Updated</span>
                  </div>
                  <p className="text-xs text-gray-500 mb-3">
                    Get alerts for new policies and opportunities in your area
                  </p>
                  <Link
                    to="/explore"
                    className="block w-full px-4 py-2 text-center bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors text-sm font-medium"
                  >
                    Get Started
                  </Link>
                </div>
              </div>
            </div>

            {/* Hero Carousel with Search as First Item */}
            <div className="flex-1">
              <div className="animate-[slideUp_0.6s_ease-out]">
                {/* Story Content - Conditional rendering based on type */}
                {FEATURED_STORIES[selectedStoryTab].type === 'hero' ? (
                  /* Hero Search Interface */
                  <div className="relative rounded-2xl shadow-2xl min-h-[400px] md:h-[500px] flex items-center justify-center p-4 md:p-8 lg:p-12 bg-gradient-to-br from-gray-50 to-white" style={{ overflow: 'visible' }}>
                    <div className="text-center max-w-4xl w-full">
                      <p className="text-base md:text-xl lg:text-2xl text-gray-600 mb-3 md:mb-4 px-2">
                        {FEATURED_STORIES[selectedStoryTab].title}
                      </p>
                      <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-7xl font-bold mb-4 md:mb-6 leading-tight px-2" style={{
                        background: 'linear-gradient(135deg, #354F52 0%, #52796F 50%, #84A98C 100%)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        backgroundClip: 'text'
                      }}>
                        {getSubtitle()}
                      </h1>
                      <p className="text-sm md:text-lg lg:text-xl text-gray-600 mb-4 md:mb-6 px-2">
                        {getDescription()}
                      </p>
                      <div className="text-xs md:text-sm lg:text-base text-gray-500 mb-6 md:mb-8 font-medium flex flex-wrap items-center justify-center gap-1 md:gap-2 px-2">
                        {/* Parse statsText and make each part clickable */}
                        {statsText.split('•').map((part, index, array) => {
                          const trimmed = part.trim();
                          let link = '';
                          
                          // Determine the appropriate link based on the content
                          if (trimmed.includes('jurisdiction')) {
                            link = '/jurisdictions';
                          } else if (trimmed.includes('nonprofit')) {
                            link = '/nonprofits';
                          } else if (trimmed.includes('leader')) {
                            link = '/people';
                          } else if (trimmed.includes('cause')) {
                            link = '/search';
                          }
                          
                          return (
                            <React.Fragment key={index}>
                              {link ? (
                                <Link
                                  to={link}
                                  className="hover:text-[#354F52] hover:underline transition-colors cursor-pointer"
                                >
                                  {trimmed}
                                </Link>
                              ) : (
                                <span>{trimmed}</span>
                              )}
                              {index < array.length - 1 && <span className="text-gray-400">•</span>}
                            </React.Fragment>
                          );
                        })}
                      </div>
                      
                      {/* Search Box */}
                      <div className="max-w-3xl mx-auto mb-6">
                        <div className="bg-white rounded-xl shadow-lg border-2 border-gray-200 p-4" ref={searchContainerRef}>
                          <form onSubmit={handleSearch}>
                            {/* Search Input and Scope Dropdown on Same Line */}
                            <div className="flex flex-col sm:flex-row gap-2 mb-3 relative">
                              <div className="flex-1 relative">
                                <input
                                  type="text"
                                  placeholder={window.innerWidth < 640 ? "Search organizations, bills, causes..." : "Search contacts, organizations, bills, topics, decisions, causes..."}
                                  value={keyword}
                                  onChange={handleKeywordChange}
                                  onFocus={() => {
                                    if (keyword.length >= 2) {
                                      setShowSuggestions(true)
                                    }
                                  }}
                                  className="w-full px-3 md:px-4 py-2 text-sm md:text-base border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#354F52] focus:border-transparent text-gray-900"
                                />
                                
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
                                        <h3 className="mt-2 text-sm font-medium text-gray-900">No results found</h3>
                                        <p className="mt-1 text-sm text-gray-500">
                                          Try searching for different keywords or check back later.
                                        </p>
                                        <p className="mt-2 text-xs text-gray-400">
                                          Database may be empty. Run data ingestion scripts to populate.
                                        </p>
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

                                    {/* Contacts Section */}
                                    {previewResults.total_results > 0 && previewResults.results?.contacts?.length > 0 && (() => {
                                      const filteredContacts = filterResults(previewResults.results.contacts, keyword);
                                      return filteredContacts.length > 0 && (
                                        <div className="border-b border-gray-200">
                                          <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                              <UserGroupIcon className="h-4 w-4 text-gray-500" />
                                              <span className="text-xs font-semibold text-gray-700 uppercase">People</span>
                                            </div>
                                            <button
                                              type="button"
                                              onClick={() => handleViewAllCategory('contacts')}
                                              className="text-xs text-[#354F52] hover:text-[#2e4346] font-medium"
                                            >
                                              View All
                                            </button>
                                          </div>
                                          {filteredContacts.slice(0, 3).map((result: any, idx: number) => (
                                            <button
                                              key={idx}
                                              type="button"
                                              onClick={() => handleSelectSuggestion(result.title)}
                                              className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                                            >
                                              <UserGroupIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
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
                              
                              {/* Search Scope Dropdown */}
                              {location ? (
                                <select
                                  value={searchScope}
                                  onChange={(e) => setSearchScope(e.target.value)}
                                  className="w-full sm:w-auto px-3 sm:px-4 py-2 text-sm border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#354F52] focus:border-transparent bg-white text-gray-900"
                                >
                                  <option value="city">City: {location.city}</option>
                                  <option value="county">County: {location.county || 'County'}</option>
                                  <option value="community">School: {location.city}</option>
                                  <option value="state">State: {location.state}</option>
                                  <option value="national">National</option>
                                </select>
                              ) : null}
                            </div>
                            
                            <div className="flex gap-2 items-center">
                              <button
                                onClick={() => setSelectedTab(1)}
                                type="button"
                                className="px-3 py-2 text-sm font-medium text-[#354F52] hover:text-[#52796F] transition-colors whitespace-nowrap"
                              >
                                📍 {location ? 'Change My Location' : 'Find My Community'}
                              </button>
                              
                              <button
                                type="submit"
                                className="flex-1 px-6 py-2 bg-[#354F52] text-white rounded-lg hover:bg-[#2e4346] transition-colors font-semibold shadow-lg text-sm"
                              >
                                Search
                              </button>
                            </div>
                          </form>
                        </div>
                      </div>
                    </div>

                    {/* Navigation Arrows */}
                    <button
                      onClick={(e) => {
                        e.preventDefault()
                        setSelectedStoryTab((prev) => (prev === 0 ? FEATURED_STORIES.length - 1 : prev - 1))
                      }}
                      className="absolute left-4 top-1/2 -translate-y-1/2 w-12 h-12 bg-white/20 backdrop-blur-sm hover:bg-white/30 rounded-full flex items-center justify-center text-gray-700 transition-all"
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
                      className="absolute right-4 top-1/2 -translate-y-1/2 w-12 h-12 bg-white/20 backdrop-blur-sm hover:bg-white/30 rounded-full flex items-center justify-center text-gray-700 transition-all"
                      aria-label="Next story"
                    >
                      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </button>

                    {/* Story Indicators */}
                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2">
                      {FEATURED_STORIES.map((_, idx) => (
                        <button
                          key={idx}
                          onClick={(e) => {
                            e.preventDefault()
                            setSelectedStoryTab(idx)
                          }}
                          className={`w-2 h-2 rounded-full transition-all ${
                            selectedStoryTab === idx
                              ? 'bg-gray-700 w-8'
                              : 'bg-gray-400 hover:bg-gray-600'
                          }`}
                          aria-label={`Go to story ${idx + 1}`}
                        />
                      ))}
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

                      {/* Story Indicators */}
                      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2">
                        {FEATURED_STORIES.map((_, idx) => (
                          <button
                            key={idx}
                            onClick={(e) => {
                              e.preventDefault()
                              setSelectedStoryTab(idx)
                            }}
                            className={`w-2 h-2 rounded-full transition-all ${
                              selectedStoryTab === idx
                                ? 'bg-white w-8'
                                : 'bg-white/50 hover:bg-white/75'
                            }`}
                            aria-label={`Go to story ${idx + 1}`}
                          />
                        ))}
                      </div>
                    </div>
                  </Link>
                )}
              </div>
            </div>
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
                ? `Currently set to ${location.city}, ${location.state}. Enter a new address to change your community.`
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
                      You're all set for <strong>{location.city}, {location.state}</strong>. You can now search for topics in your community.
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

      {/* Features Section */}
      <section id="features" className="py-16 px-4 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12 animate-[slideUp_0.8s_ease-out_0.8s_both]">
            <h2 className="text-3xl md:text-4xl font-bold mb-2" style={{ color: '#354F52' }}>
              Everything You Need
            </h2>
            <div className="w-24 h-1 bg-gradient-to-r from-[#52796F] to-[#84A98C] mx-auto rounded mb-4"></div>
            <p className="text-lg text-gray-600">
              Powerful tools to stay informed and engaged
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 animate-[slideUp_0.8s_ease-out_1s_both]">
            <Link
              to="/documents"
              className="group bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-2xl p-8 hover:border-[#354F52] hover:shadow-xl transition-all"
            >
              <div
                className="w-14 h-14 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform"
                style={{ backgroundColor: '#354F5215' }}
              >
                <DocumentTextIcon className="h-7 w-7" style={{ color: '#354F52' }} />
              </div>
              <h3 className="text-xl font-bold mb-3" style={{ color: '#354F52' }}>
                Policy Decisions
              </h3>
              <p className="text-gray-600 mb-4">
                Track 500K+ meeting pages with decision analysis, deferral patterns, and stakeholder positions
              </p>
              <span className="inline-flex items-center gap-2 text-sm font-medium" style={{ color: '#354F52' }}>
                Learn more <ArrowRightIcon className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
              </span>
            </Link>

            <Link
              to="/analytics"
              className="group bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-2xl p-8 hover:border-[#52796F] hover:shadow-xl transition-all"
            >
              <div
                className="w-14 h-14 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform"
                style={{ backgroundColor: '#52796F15' }}
              >
                <ChartBarIcon className="h-7 w-7" style={{ color: '#52796F' }} />
              </div>
              <h3 className="text-xl font-bold mb-3" style={{ color: '#354F52' }}>
                Budget Analysis
              </h3>
              <p className="text-gray-600 mb-4">
                Compare budget rhetoric to reality with $2T+ in tracked spending and delta analysis
              </p>
              <span className="inline-flex items-center gap-2 text-sm font-medium" style={{ color: '#52796F' }}>
                Learn more <ArrowRightIcon className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
              </span>
            </Link>

            <Link
              to="/people"
              className="group bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-2xl p-8 hover:border-[#84A98C] hover:shadow-xl transition-all"
            >
              <div
                className="w-14 h-14 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform"
                style={{ backgroundColor: '#84A98C15' }}
              >
                <UserGroupIcon className="h-7 w-7" style={{ color: '#84A98C' }} />
              </div>
              <h3 className="text-xl font-bold mb-3" style={{ color: '#354F52' }}>
                Elected Officials
              </h3>
              <p className="text-gray-600 mb-4">
                Follow 362 officials across 925 jurisdictions with voting records and decision patterns
              </p>
              <span className="inline-flex items-center gap-2 text-sm font-medium" style={{ color: '#84A98C' }}>
                Learn more <ArrowRightIcon className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
              </span>
            </Link>

            <Link
              to="/policy-map"
              className="group bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-2xl p-8 hover:border-[#4A90E2] hover:shadow-xl transition-all"
            >
              <div
                className="w-14 h-14 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform"
                style={{ backgroundColor: '#4A90E215' }}
              >
                <MapIcon className="h-7 w-7" style={{ color: '#4A90E2' }} />
              </div>
              <h3 className="text-xl font-bold mb-3" style={{ color: '#354F52' }}>
                Policy Map
              </h3>
              <p className="text-gray-600 mb-4">
                Track state legislation and bills across all sessions. Search 13,000+ bills by topic and status
              </p>
              <span className="inline-flex items-center gap-2 text-sm font-medium" style={{ color: '#4A90E2' }}>
                Learn more <ArrowRightIcon className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
              </span>
            </Link>

            <Link
              to="/nonprofits"
              className="group bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-2xl p-8 hover:border-[#9B59B6] hover:shadow-xl transition-all"
            >
              <div
                className="w-14 h-14 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform"
                style={{ backgroundColor: '#9B59B615' }}
              >
                <BuildingLibraryIcon className="h-7 w-7" style={{ color: '#9B59B6' }} />
              </div>
              <h3 className="text-xl font-bold mb-3" style={{ color: '#354F52' }}>
                Nonprofits & Churches
              </h3>
              <p className="text-gray-600 mb-4">
                43,726 nonprofits including 4,372 churches with financial data from 5 states
              </p>
              <span className="inline-flex items-center gap-2 text-sm font-medium" style={{ color: '#9B59B6' }}>
                Learn more <ArrowRightIcon className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
              </span>
            </Link>

            <Link
              to="/debate-grader"
              className="group bg-gradient-to-br from-gray-50 to-white border-2 border-gray-200 rounded-2xl p-8 hover:border-[#E74C3C] hover:shadow-xl transition-all"
            >
              <div
                className="w-14 h-14 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform"
                style={{ backgroundColor: '#E74C3C15' }}
              >
                <BellAlertIcon className="h-7 w-7" style={{ color: '#E74C3C' }} />
              </div>
              <h3 className="text-xl font-bold mb-3" style={{ color: '#354F52' }}>
                Fact-Checking
              </h3>
              <p className="text-gray-600 mb-4">
                Verify claims with integrated PolitiFact, FactCheck.org, and Google Fact Check data
              </p>
              <span className="inline-flex items-center gap-2 text-sm font-medium" style={{ color: '#E74C3C' }}>
                Learn more <ArrowRightIcon className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
              </span>
            </Link>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="py-16 px-4 bg-gradient-to-br from-gray-50 to-gray-100">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-2" style={{ color: '#354F52' }}>
              How It Works
            </h2>
            <div className="w-24 h-1 bg-gradient-to-r from-[#52796F] to-[#84A98C] mx-auto rounded mb-4"></div>
            <p className="text-lg text-gray-600">
              Three simple steps to stay engaged with your community
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {/* Step 1 */}
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-[#354F52] text-white text-2xl font-bold mb-4">
                1
              </div>
              <h3 className="text-xl font-bold mb-3" style={{ color: '#354F52' }}>
                Discover
              </h3>
              <p className="text-gray-600">
                Search across 925 jurisdictions and 43,726 nonprofits to find topics, people, and causes that matter to you
              </p>
            </div>

            {/* Step 2 */}
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-[#52796F] text-white text-2xl font-bold mb-4">
                2
              </div>
              <h3 className="text-xl font-bold mb-3" style={{ color: '#354F52' }}>
                Track
              </h3>
              <p className="text-gray-600">
                Monitor legislation, meetings, and policy decisions with AI-powered analysis and real-time updates
              </p>
            </div>

            {/* Step 3 */}
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-[#84A98C] text-white text-2xl font-bold mb-4">
                3
              </div>
              <h3 className="text-xl font-bold mb-3" style={{ color: '#354F52' }}>
                Engage
              </h3>
              <p className="text-gray-600">
                Take action by contacting officials, supporting causes, and participating in local democracy
              </p>
            </div>
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
            <p className="text-lg text-gray-600">
              One platform connecting residents, leaders, and funders to what's really happening on the ground
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-12">
            {/* Stat 1 */}
            <div className="text-center">
              <div className="text-4xl md:text-5xl font-bold mb-2" style={{ color: '#354F52' }}>
                925
              </div>
              <div className="text-gray-600 font-medium">
                Jurisdictions Tracked
              </div>
            </div>

            {/* Stat 2 */}
            <div className="text-center">
              <div className="text-4xl md:text-5xl font-bold mb-2" style={{ color: '#52796F' }}>
                43K+
              </div>
              <div className="text-gray-600 font-medium">
                Nonprofits Indexed
              </div>
            </div>

            {/* Stat 3 */}
            <div className="text-center">
              <div className="text-4xl md:text-5xl font-bold mb-2" style={{ color: '#84A98C' }}>
                500K+
              </div>
              <div className="text-gray-600 font-medium">
                Meeting Pages
              </div>
            </div>

            {/* Stat 4 */}
            <div className="text-center">
              <div className="text-4xl md:text-5xl font-bold mb-2" style={{ color: '#4A90E2' }}>
                13K+
              </div>
              <div className="text-gray-600 font-medium">
                Legislative Bills
              </div>
            </div>
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

            <div className="border-t border-gray-200 pt-6 mb-6">
              <p className="text-xs font-bold uppercase tracking-widest text-[#52796F] mb-2">Public Benefit Corporation</p>
              <p className="text-base text-gray-600 leading-relaxed">
                GroundVue is a public benefit corporation with a fiscal-sponsored nonprofit 501(c)(3). We are solely funded by mission-aligned impact investors and philanthropic institutions.
              </p>
            </div>

            <Link
              to="/explore"
              className="inline-flex items-center gap-2 px-6 py-3 bg-[#354F52] text-white rounded-lg hover:bg-[#2e4346] transition-colors font-semibold"
            >
              Start Exploring <ArrowRightIcon className="h-5 w-5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Search Section (Collapsible) */}
      <div className="bg-gray-50 py-12 border-t border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-8 animate-[slideUp_0.8s_ease-out_0.8s_both]">
            <h2 className="text-3xl md:text-4xl font-bold mb-2" style={{ color: '#354F52' }}>
              Search Your Community
            </h2>
            <div className="w-24 h-1 bg-gradient-to-r from-[#52796F] to-[#84A98C] mx-auto rounded mb-4"></div>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              Track local governments and charities. Find leaders by name. Discover causes.{' '}
              <Link to="/jurisdictions" className="font-semibold text-[#52796F] hover:text-[#354F52] hover:underline hover:decoration-2 transition-colors">925 jurisdictions</Link>.{' '}
              <Link to="/search?types=organizations" className="font-semibold hover:underline">43,726 nonprofits</Link>. All free.
            </p>
          </div>

          {/* Tabbed Interface */}
          <div className="max-w-5xl mx-auto mb-8">
            <Tab.Group selectedIndex={selectedTab} onChange={setSelectedTab}>
              <Tab.List className="flex space-x-2 rounded-xl bg-white p-2 shadow-lg mb-6">
                <Tab as={Fragment}>
                  {({ selected }) => (
                    <button
                      className={`w-full rounded-lg py-3 px-4 text-base font-medium leading-5 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 ${
                        selected ? 'text-white shadow' : 'text-gray-700 hover:bg-gray-100'
                      }`}
                      style={selected ? { backgroundColor: '#354F52' } : {}}
                    >
                      🔍 Search Topics
                    </button>
                  )}
                </Tab>
                <Tab as={Fragment}>
                  {({ selected }) => (
                    <button
                      className={`w-full rounded-lg py-3 px-4 text-base font-medium leading-5 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 ${
                        selected ? 'text-white shadow' : 'text-gray-700 hover:bg-gray-100'
                      }`}
                      style={selected ? { backgroundColor: '#354F52' } : {}}
                    >
                      📍 {location ? 'Change My Community' : 'Find My Local Community'}
                    </button>
                  )}
                </Tab>
              </Tab.List>

              <Tab.Panels>
                {/* Search Tab */}
                <Tab.Panel>
                  <div className="bg-white rounded-xl shadow-lg p-8" style={{ overflow: 'visible' }}>
                    <form onSubmit={handleSearch}>
                      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-end">
                        <div className="lg:col-span-7">
                          <label className="block text-left text-sm font-medium text-gray-700 mb-2">
                            Search for topics, people, organizations, or causes
                          </label>
                          <div className="relative">
                            <input
                              type="text"
                              placeholder="Try: mayor, dental clinic, food bank, affordable housing..."
                              value={keyword}
                              onChange={handleKeywordChange}
                              onFocus={() => {
                                if (keyword.length >= 2) {
                                  setShowSuggestions(true)
                                }
                              }}
                              className="w-full px-4 py-3 text-lg border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-gray-900"
                            />
                            
                            {/* Error Display */}
                            {showSuggestions && previewError && (
                              <div className="absolute z-50 w-full mt-2 bg-red-50 border border-red-200 rounded-lg shadow-xl p-4">
                                <div className="flex items-start gap-3">
                                  <div className="flex-shrink-0">
                                    <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                                    </svg>
                                  </div>
                                  <div className="flex-1">
                                    <h3 className="text-sm font-medium text-red-800">Search Error</h3>
                                    <p className="mt-1 text-sm text-red-700">
                                      {(previewError as any)?.response?.status === 404 
                                        ? 'Search endpoint not found. The API may still be starting up.'
                                        : 'Unable to fetch search results. Please try again.'}
                                    </p>
                                    <p className="mt-2 text-xs text-red-600">
                                      Error details: {(previewError as any)?.message || 'Unknown error'}
                                    </p>
                                  </div>
                                </div>
                              </div>
                            )}
                            
                            {/* Loading Display */}
                            {showSuggestions && previewLoading && (
                              <div className="absolute z-50 w-full mt-2 bg-white border border-gray-200 rounded-lg shadow-xl p-4">
                                <div className="flex items-center justify-center gap-3">
                                  <svg className="animate-spin h-5 w-5 text-primary-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                  </svg>
                                  <span className="text-sm text-gray-600">Searching...</span>
                                </div>
                              </div>
                            )}
                            
                            {/* Rich Preview Dropdown with Grouped Results */}
                            {showSuggestions && !previewLoading && !previewError && previewResults && previewResults.total_results > 0 && (
                              <div className="absolute z-50 w-full mt-2 bg-white border border-gray-200 rounded-lg shadow-xl max-h-96 overflow-y-auto">
                                
                                {/* Causes Section */}
                                {previewResults.results.causes.length > 0 && (
                                  <div className="border-b border-gray-200">
                                    <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                                      <div className="flex items-center gap-2">
                                        <HeartIcon className="h-4 w-4 text-gray-500" />
                                        <span className="text-xs font-semibold text-gray-700 uppercase">Causes</span>
                                      </div>
                                      <button
                                        type="button"
                                        onClick={() => handleViewAllCategory('causes')}
                                        className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                                      >
                                        View All
                                      </button>
                                    </div>
                                    {previewResults.results.causes.slice(0, 3).map((result: any, idx: number) => (
                                      <button
                                        key={idx}
                                        type="button"
                                        onClick={() => handleSelectSuggestion(result.title)}
                                        className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                                      >
                                        <HeartIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                          <div className="font-medium text-gray-900 truncate">{result.title}</div>
                                          <div className="text-sm text-gray-600 truncate">
                                            {result.breadcrumb || result.subtitle || result.description || ''}
                                          </div>
                                        </div>
                                      </button>
                                    ))}
                                  </div>
                                )}

                                {/* People (Contacts) Section */}
                                {previewResults.results.contacts.length > 0 && (
                                  <div className="border-b border-gray-200">
                                    <div className="px-4 py-2 bg-gray-50 flex items-center justify-between">
                                      <div className="flex items-center gap-2">
                                        <UserIcon className="h-4 w-4 text-gray-500" />
                                        <span className="text-xs font-semibold text-gray-700 uppercase">People</span>
                                      </div>
                                      <button
                                        type="button"
                                        onClick={() => handleViewAllCategory('contacts')}
                                        className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                                      >
                                        View All
                                      </button>
                                    </div>
                                    {previewResults.results.contacts.slice(0, 3).map((result: any, idx: number) => (
                                      <button
                                        key={idx}
                                        type="button"
                                        onClick={() => handleSelectSuggestion(result.title)}
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
                                      <button
                                        type="button"
                                        onClick={() => handleViewAllCategory('organizations')}
                                        className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                                      >
                                        View All
                                      </button>
                                    </div>
                                    {previewResults.results.organizations.slice(0, 3).map((result: any, idx: number) => (
                                      <button
                                        key={idx}
                                        type="button"
                                        onClick={() => handleSelectSuggestion(result.title)}
                                        className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors last:rounded-b-lg"
                                      >
                                        {result.metadata?.logo_url ? (
                                          <img 
                                            src={result.metadata.logo_url} 
                                            alt={`${result.title} logo`}
                                            className="h-5 w-5 rounded object-contain mt-0.5 flex-shrink-0"
                                            onError={(e) => {
                                              // Fallback to icon if image fails to load
                                              e.currentTarget.style.display = 'none';
                                              e.currentTarget.nextElementSibling?.classList.remove('hidden');
                                            }}
                                          />
                                        ) : null}
                                        <BuildingOfficeIcon className={`h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0 ${result.metadata?.logo_url ? 'hidden' : ''}`} />
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
                                      <button
                                        type="button"
                                        onClick={() => handleViewAllCategory('bills')}
                                        className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                                      >
                                        View All
                                      </button>
                                    </div>
                                    {previewResults.results.bills.slice(0, 3).map((result: any, idx: number) => (
                                      <button
                                        key={idx}
                                        type="button"
                                        onClick={() => handleSelectSuggestion(result.title)}
                                        className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                                      >
                                        <DocumentTextIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                          <div className="font-medium text-gray-900 truncate">{result.title}</div>
                                          <div className="text-sm text-gray-600 truncate">{result.subtitle || result.description}</div>
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
                                      <button
                                        type="button"
                                        onClick={() => handleViewAllCategory('topics')}
                                        className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                                      >
                                        View All
                                      </button>
                                    </div>
                                    {previewResults.results.topics.slice(0, 3).map((result: any, idx: number) => (
                                      <button
                                        key={idx}
                                        type="button"
                                        onClick={() => handleSelectSuggestion(result.title)}
                                        className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                                      >
                                        <ChatBubbleBottomCenterTextIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                          <div className="font-medium text-gray-900 truncate">{result.title}</div>
                                          <div className="text-sm text-gray-600 truncate">{result.subtitle || result.description}</div>
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
                                        type="button"
                                        onClick={() => handleViewAllCategory('decisions')}
                                        className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                                      >
                                        View All
                                      </button>
                                    </div>
                                    {previewResults.results.decisions.slice(0, 3).map((result: any, idx: number) => (
                                      <button
                                        key={idx}
                                        type="button"
                                        onClick={() => handleSelectSuggestion(result.title)}
                                        className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-start gap-3 transition-colors"
                                      >
                                        <ScaleIcon className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                          <div className="font-medium text-gray-900 truncate">{result.title}</div>
                                          <div className="text-sm text-gray-600 truncate">{result.subtitle || result.description}</div>
                                        </div>
                                      </button>
                                    ))}
                                  </div>
                                )}

                                {/* Footer with total results */}
                                <div className="px-4 py-2 bg-gray-50 text-center border-t border-gray-200">
                                  <button
                                    type="submit"
                                    className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                                  >
                                    See all {previewResults.total_results} results →
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="lg:col-span-3">
                          <label className="block text-left text-sm font-medium text-gray-700 mb-2">
                            Search In
                          </label>
                          {location ? (
                            <div className="relative">
                              <select
                                value={searchScope}
                                onChange={(e) => setSearchScope(e.target.value)}
                                className="w-full px-4 py-3 text-lg border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white text-gray-900"
                              >
                                <option value="city">My City ({location.city})</option>
                                <option value="county">My County ({location.county || 'County'})</option>
                                <option value="community">School Board ({location.city})</option>
                                <option value="state">My State ({location.state})</option>
                                <option value="national">National</option>
                              </select>
                              <button
                                type="button"
                                onClick={() => navigate('/?tab=community')}
                                className="absolute -bottom-6 left-0 right-0 text-xs text-primary-600 hover:text-primary-700 font-medium underline flex items-center justify-center gap-1"
                              >
                                <MapPinIcon className="h-3 w-3" />
                                Change Location
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={() => navigate('/?tab=community')}
                              className="w-full px-4 py-3 text-lg border-2 border-primary-600 rounded-lg bg-primary-50 text-primary-700 hover:bg-primary-100 transition-colors font-semibold flex items-center justify-center gap-2"
                            >
                              <MapPinIcon className="h-5 w-5" />
                              Set Your Location First
                            </button>
                          )}
                        </div>

                        <div className="lg:col-span-2">
                          <label className="block text-left text-sm font-medium text-gray-700 mb-2 invisible">
                            Search
                          </label>
                          <button
                            type="submit"
                            className="w-full text-white px-6 py-3 rounded-lg transition-colors text-lg font-semibold flex items-center justify-center gap-2"
                            style={{ backgroundColor: '#354F52' }}
                            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#2e4346'}
                            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#354F52'}
                          >
                            <MagnifyingGlassIcon className="h-6 w-6" />
                            Search
                          </button>
                        </div>
                      </div>
                    </form>
                  </div>
                </Tab.Panel>

                {/* Find My Community Tab */}
                <Tab.Panel>
                  <div className="bg-white rounded-xl shadow-lg p-8">
                    <h2 className="text-2xl font-bold mb-3 text-center" style={{ color: '#354F52' }}>
                      {location ? `What's Happening in ${location.city}, ${location.state}?` : "What's Happening in Your Community?"}
                    </h2>
                    <p className="text-gray-600 text-center mb-6">
                      {location 
                        ? 'Update your address to change your community location' 
                        : 'Enter your address to find local organizations, city councils, county boards, school districts, and charities near you'}
                    </p>
                    <AddressLookup onLocationFound={handleAddressFound} />
                    
                    {/* Success message and return to search button */}
                    {location && (
                      <div className="mt-8 p-6 bg-green-50 border-2 border-green-200 rounded-xl">
                        <div className="flex items-start gap-3 mb-4">
                          <CheckCircleIcon className="h-6 w-6 text-green-600 flex-shrink-0 mt-0.5" />
                          <div className="flex-1">
                            <h3 className="text-lg font-bold text-green-900 mb-1">
                              Location Set Successfully!
                            </h3>
                            <p className="text-green-700">
                              You're all set for <strong>{location.city}, {location.state}</strong>. Now you can search for topics in your community.
                            </p>
                          </div>
                        </div>
                        <button
                          onClick={() => setSelectedTab(0)}
                          className="w-full bg-green-600 hover:bg-green-700 text-white px-6 py-4 rounded-lg font-semibold text-lg flex items-center justify-center gap-2 transition-all shadow-lg hover:shadow-xl"
                        >
                          <MagnifyingGlassIcon className="h-6 w-6" />
                          Search Topics in My Community
                          <ArrowRightIcon className="h-5 w-5" />
                        </button>
                      </div>
                    )}
                  </div>
                </Tab.Panel>
              </Tab.Panels>
            </Tab.Group>
          </div>

          {/* Quick Topics */}
          <div className="max-w-5xl mx-auto mb-6">
            <p className="text-sm text-gray-600 text-center mb-3">Popular topics:</p>
            <div className="flex flex-wrap justify-center gap-3">
              {categories.map((category) => (
                <button
                  key={category.name}
                  onClick={() => quickSearch(category)}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-white border-2 border-gray-300 rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors"
                >
                  <category.icon className="h-5 w-5 text-gray-600" />
                  <span className="font-medium text-gray-700">{category.name}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Terms */}
          <p className="text-sm text-gray-500">
            By continuing, you agree to the{' '}
            <a href="#" className="text-primary-600 hover:underline">Terms</a>
            {' & '}
            <a href="#" className="text-primary-600 hover:underline">Privacy</a>.
          </p>
        </div>
      </div>

      {/* Features Grid */}
      <div className="py-16" style={{ backgroundColor: '#354F52' }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center mb-12 text-white">Explore the Platform</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            <Link to="/analytics" className="group">
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

      {/* Stats Section */}
      <div className="py-16" style={{ backgroundColor: '#F1F5F9' }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 text-center">
            <div>
              <div className="text-4xl font-bold text-primary-600 mb-2">2,500+</div>
              <div className="text-gray-600">Causes Tracked</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-emerald-600 mb-2">15,000+</div>
              <div className="text-gray-600">Government Decisions</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-amber-600 mb-2">8 Years</div>
              <div className="text-gray-600">Historical Coverage</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-cyan-600 mb-2">5,000+</div>
              <div className="text-gray-600">Meeting Records</div>
            </div>
            <div>
              <div className="text-4xl font-bold mb-2" style={{ color: '#354F52' }}>12,000+</div>
              <div className="text-gray-600">Hours of Video</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-purple-600 mb-2">100%</div>
              <div className="text-gray-600">Free & Open</div>
            </div>
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
          
          <div className="flex justify-center gap-8 text-sm text-gray-400">
            <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Documentation</a>
            <a href={import.meta.env.PROD ? 'https://www.communityone.com/api/docs' : 'http://localhost:8000/docs'} target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">API</a>
            <Link to="/explore" className="hover:text-white transition-colors">Explore</Link>
          </div>
          <p className="text-gray-500 text-sm mt-6">
            © 2026 CommunityOne. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  )
}
