import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { MagnifyingGlassIcon, UserGroupIcon, AcademicCapIcon, UsersIcon, CodeBracketIcon } from '@heroicons/react/24/outline'
import { useLocation } from '../contexts/LocationContext'
import FollowButton from '../components/FollowButton'

type PersonRole = 'decision-makers' | 'support' | 'public' | 'open-source'

interface Person {
  id: number
  name: string
  role: PersonRole
  specificRole: string
  organization: string
  location: string
  contact?: string
}

const roleCategories = {
  'decision-makers': {
    title: 'Decision Makers',
    subtitle: 'People who vote on policy and budgets',
    icon: UserGroupIcon,
    color: '#354F52',
    roles: [
      'Community Representatives',
      'The Decision Makers',
      'Board Members',
      'Policy Voters',
    ]
  },
  'support': {
    title: 'Support Staff',
    subtitle: 'People who help and advise',
    icon: AcademicCapIcon,
    color: '#64748B',
    roles: [
      'Expert Advisors',
      'Community Guides',
      'Program Staff',
    ]
  },
  'public': {
    title: 'Community Members',
    subtitle: 'Residents and advocates',
    icon: UsersIcon,
    color: '#8a9d9e',
    roles: [
      'Neighbors & Residents',
      'Parents & Families',
      'Advocates',
    ]
  },
  'open-source': {
    title: 'Open Source Contributors',
    subtitle: 'Civic tech maintainers and developers',
    icon: CodeBracketIcon,
    color: '#06B6D4',
    roles: [
      'Project Maintainers',
      'Core Contributors',
      'Community Developers',
    ]
  }
}

export default function PeopleFinder() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedRole, setSelectedRole] = useState<PersonRole | 'all'>('all')
  const [selectedCity, setSelectedCity] = useState<string>('all')
  const [currentPage, setCurrentPage] = useState(1)
  const { location } = useLocation()

  // Default to Alabama if no location is set
  const defaultState = 'AL'
  const effectiveState = location?.state || defaultState
  
  // Use location.city as default if available
  const defaultCity = location?.city || null

  // Fetch contacts from API
  const { data: contactsData, isLoading, error } = useQuery({
    queryKey: ['people-finder', effectiveState, currentPage],
    queryFn: async () => {
      const params: any = {
        types: 'contacts',
        limit: 100, // API max is 100
        state: effectiveState,
        page: currentPage
      }
      
      const response = await api.get('/search', { params })
      return response.data
    },
    staleTime: 60000, // Cache for 1 minute
  })

  // Convert API contacts to Person format
  const people: Person[] = (contactsData?.results?.contacts || []).map((contact: any, index: number) => ({
    id: index + 1,
    name: contact.title || 'Unknown',  // API puts name in title field
    role: 'decision-makers' as PersonRole,
    specificRole: contact.metadata.title || contact.metadata.role_type || 'Official',
    organization: contact.metadata.organization || contact.metadata.state || 'Government',
    location: `${contact.metadata.city || contact.metadata.state || ''}`.trim(),
    contact: contact.metadata.email || undefined,
  }))

  // Debug logging
  if (contactsData && !isLoading) {
    console.log('PeopleFinder Debug:', {
      effectiveState,
      defaultCity,
      totalResults: contactsData.total_results,
      contactsReturned: contactsData.results?.contacts?.length || 0,
      peopleConverted: people.length,
      sampleContact: contactsData.results?.contacts?.[0]
    })
  }

  // Get unique cities for filter dropdown
  const cities = Array.from(new Set(people.map(p => p.organization).filter(Boolean))).sort()
  
  // Auto-select user's city if they have a location set
  useEffect(() => {
    if (defaultCity && cities.includes(defaultCity) && selectedCity === 'all') {
      setSelectedCity(defaultCity)
    }
  }, [defaultCity, cities, selectedCity])
  
  // Add summary counts by city
  const cityCounts = people.reduce((acc, person) => {
    const city = person.organization || 'Unknown'
    acc[city] = (acc[city] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  const filteredPeople = people.filter(person => {
    const matchesSearch = searchQuery === '' || 
      person.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      person.organization.toLowerCase().includes(searchQuery.toLowerCase()) ||
      person.location.toLowerCase().includes(searchQuery.toLowerCase()) ||
      person.specificRole.toLowerCase().includes(searchQuery.toLowerCase())
    
    const matchesRole = selectedRole === 'all' || person.role === selectedRole
    
    // City filter
    const matchesCity = selectedCity === 'all' || person.organization === selectedCity
    
    return matchesSearch && matchesRole && matchesCity
  })

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2" style={{ color: '#354F52' }}>
          Find Leaders
        </h1>
        <p className="text-gray-600">
          Discover elected officials, decision makers, and community leaders
          <span className="font-medium text-primary-600"> in {effectiveState}</span>
          {!location?.state && (
            <span className="text-sm text-gray-500 ml-2">(default state - set your location to customize)</span>
          )}
        </p>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex justify-center items-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 mb-8">
          <h3 className="text-red-800 font-semibold mb-2">Error loading contacts</h3>
          <p className="text-red-600 text-sm">
            {error instanceof Error ? error.message : 'Failed to load contacts from the API'}
          </p>
          <button 
            onClick={() => window.location.reload()} 
            className="mt-3 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Reload Page
          </button>
        </div>
      )}

      {/* Search Bar and Filters */}
      {!isLoading && !error && (
        <>
      <div className="mb-6 space-y-4">
        {/* Search Input */}
        <div className="relative">
          <input
            type="text"
            placeholder="Search by name, title, organization, or location..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-4 py-3 pl-12 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-gray-900"
          />
          <MagnifyingGlassIcon className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" />
        </div>

        {/* City Filter Dropdown */}
        <div className="flex gap-4 items-center">
          <label htmlFor="city-filter" className="text-sm font-medium text-gray-700">
            Filter by City/Jurisdiction:
          </label>
          <select
            id="city-filter"
            value={selectedCity}
            onChange={(e) => {
              setSelectedCity(e.target.value)
              setCurrentPage(1) // Reset to first page when filter changes
            }}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-gray-900"
          >
            <option value="all">All Cities ({people.length} officials)</option>
            {cities.map((city) => (
              <option key={city} value={city}>
                {city} ({cityCounts[city]} officials)
              </option>
            ))}
          </select>

          {/* Clear Filters */}
          {(selectedCity !== 'all' || searchQuery !== '' || selectedRole !== 'all') && (
            <button
              onClick={() => {
                setSelectedCity('all')
                setSearchQuery('')
                setSelectedRole('all')
                setCurrentPage(1)
              }}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 underline"
            >
              Clear all filters
            </button>
          )}
        </div>

        {/* Summary Info */}
        <div className="flex items-center gap-4 text-sm text-gray-600">
          <span>
            Showing {filteredPeople.length} of {people.length} officials
          </span>
          {selectedCity !== 'all' && (
            <span className="font-medium text-primary-600">
              • Filtered to {selectedCity}
            </span>
          )}
          <span className="text-gray-400">
            • Page {currentPage} • {effectiveState}
          </span>
        </div>
      </div>

      {/* Role Filter Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        <button
          onClick={() => setSelectedRole('all')}
          className={`p-4 rounded-lg border-2 transition-all ${
            selectedRole === 'all'
              ? 'border-[#354F52] bg-[#354F52] bg-opacity-10'
              : 'border-gray-200 hover:border-gray-300'
          }`}
        >
          <div className="text-center">
            <div className="font-semibold" style={{ color: '#354F52' }}>All People</div>
            <div className="text-sm text-gray-500 mt-1">{people.length} total</div>
          </div>
        </button>

        {(Object.keys(roleCategories) as PersonRole[]).map((roleKey) => {
          const category = roleCategories[roleKey]
          const Icon = category.icon
          const count = people.filter(p => p.role === roleKey).length
          
          return (
            <button
              key={roleKey}
              onClick={() => setSelectedRole(roleKey)}
              className={`p-4 rounded-lg border-2 transition-all ${
                selectedRole === roleKey
                  ? 'border-[#354F52] bg-[#354F52] bg-opacity-10'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="flex flex-col items-center text-center">
                <Icon className="h-8 w-8 mb-2" style={{ color: category.color }} />
                <div className="font-semibold" style={{ color: category.color }}>
                  {category.title}
                </div>
                <div className="text-sm text-gray-500 mt-1">{count} people</div>
              </div>
            </button>
          )
        })}
      </div>

      {/* Role Categories Explanation */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {(Object.keys(roleCategories) as PersonRole[]).map((roleKey) => {
          const category = roleCategories[roleKey]
          const Icon = category.icon
          
          return (
            <div key={roleKey} className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center gap-3 mb-3">
                <Icon className="h-6 w-6" style={{ color: category.color }} />
                <h3 className="text-lg font-semibold" style={{ color: category.color }}>
                  {category.title}
                </h3>
              </div>
              <p className="text-sm text-gray-600 mb-3">{category.subtitle}</p>
              <ul className="space-y-1">
                {category.roles.map((role) => (
                  <li key={role} className="text-sm text-gray-700">
                    • {role}
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>

      {/* Results */}
      <div>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold" style={{ color: '#354F52' }}>
            {selectedRole === 'all' ? 'All People' : roleCategories[selectedRole].title}
            <span className="text-gray-500 font-normal ml-2">({filteredPeople.length} results)</span>
          </h2>

          {/* Pagination Controls */}
          {contactsData && contactsData.pagination && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={!contactsData.pagination.has_prev}
                className="px-3 py-1 border rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                ← Prev
              </button>
              <span className="text-sm text-gray-600">
                Page {currentPage} of {contactsData.pagination.total_pages}
              </span>
              <button
                onClick={() => setCurrentPage(p => p + 1)}
                disabled={!contactsData.pagination.has_next}
                className="px-3 py-1 border rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                Next →
              </button>
            </div>
          )}
        </div>

        {filteredPeople.length === 0 ? (
          <div className="bg-white rounded-lg shadow-md p-8 text-center">
            <p className="text-gray-500">No people found matching your criteria</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredPeople.map((person) => {
              const category = roleCategories[person.role]
              const Icon = category.icon
              
              return (
                <div key={person.id} className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
                  <div className="flex items-start gap-3 mb-3">
                    <Icon className="h-6 w-6 mt-1" style={{ color: category.color }} />
                    <div className="flex-1">
                      <h3 className="font-semibold text-lg" style={{ color: '#354F52' }}>
                        {person.name}
                      </h3>
                      <p className="text-sm font-medium" style={{ color: category.color }}>
                        {person.specificRole}
                      </p>
                    </div>
                  </div>
                  
                  <div className="space-y-2 text-sm mb-4">
                    <div>
                      <span className="font-medium text-gray-700">
                        {person.role === 'open-source' ? 'Repository:' : 'Organization:'}
                      </span>
                      {person.role === 'open-source' ? (
                        <a 
                          href={`https://github.com/${person.organization}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-cyan-600 hover:underline block"
                        >
                          {person.organization}
                        </a>
                      ) : (
                        <p className="text-gray-600">{person.organization}</p>
                      )}
                    </div>
                    <div>
                      <span className="font-medium text-gray-700">Location:</span>
                      <p className="text-gray-600">{person.location}</p>
                    </div>
                    {person.contact && (
                      <div>
                        <span className="font-medium text-gray-700">Contact:</span>
                        {person.role === 'open-source' && person.contact.startsWith('@') ? (
                          <a 
                            href={`https://github.com/${person.contact.substring(1)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-cyan-600 hover:underline block"
                          >
                            {person.contact}
                          </a>
                        ) : person.contact.includes('@') ? (
                          <a 
                            href={`mailto:${person.contact}`}
                            className="text-cyan-600 hover:underline block"
                          >
                            {person.contact}
                          </a>
                        ) : (
                          <p className="text-gray-600">{person.contact}</p>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Follow button (LinkedIn/Facebook style) */}
                  <div className="pt-4 border-t border-gray-100">
                    <FollowButton 
                      type="leader" 
                      id={person.id}
                      initialFollowing={false}
                      initialCount={Math.floor(Math.random() * 500)}
                      compact={true}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
      </>
      )}
    </div>
  )
}
