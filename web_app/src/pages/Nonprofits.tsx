import { useState, useEffect } from 'react'
import { formatCurrency } from '../utils/formatters'

interface Nonprofit {
  source: string
  ein: string
  name: string
  city?: string
  state?: string
  description?: string
  mission?: string
  logo_url?: string
  website_url?: string
  ntee_code?: string
  ntee_description?: string
  revenue_amount?: number
  asset_amount?: number
  income_amount?: number
}

interface SearchParams {
  location: string
  keyword: string
  state: string
  nteeCode: string
}

export default function Nonprofits() {
  const [nonprofits, setNonprofits] = useState<Nonprofit[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchParams, setSearchParams] = useState<SearchParams>({
    location: 'Tuscaloosa, AL',
    keyword: 'dental',
    state: '',
    nteeCode: 'E' // E = Health
  })

  const searchNonprofits = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const params = new URLSearchParams()
      if (searchParams.location) params.append('location', searchParams.location)
      if (searchParams.keyword) params.append('keyword', searchParams.keyword)
      if (searchParams.state) params.append('state', searchParams.state)
      if (searchParams.nteeCode) params.append('ntee_code', searchParams.nteeCode)
      
      const response = await fetch(`/api/nonprofits?${params}`)
      if (!response.ok) throw new Error('Failed to fetch nonprofits')
      
      const data = await response.json()
      setNonprofits(data.nonprofits || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    searchNonprofits()
  }, [])

  // formatCurrency imported from utils/formatters

  return (
    <div className="min-h-screen p-8" style={{ backgroundColor: '#F1F5F9' }}>
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold mb-2" style={{ color: '#354F52' }}>Local Charities</h1>
          <p className="text-gray-600">
            Find charities and nonprofits providing services in your community
          </p>
        </div>

      {/* Search Form */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Location
            </label>
            <input
              type="text"
              value={searchParams.location}
              onChange={(e) => setSearchParams({ ...searchParams, location: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="City, State"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Keyword
            </label>
            <input
              type="text"
              value={searchParams.keyword}
              onChange={(e) => setSearchParams({ ...searchParams, keyword: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="dental, health, etc."
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              NTEE Code
            </label>
            <select
              value={searchParams.nteeCode}
              onChange={(e) => setSearchParams({ ...searchParams, nteeCode: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Categories</option>
              <option value="E">Health (E)</option>
              <option value="E20">Hospitals (E20)</option>
              <option value="E30">Community Clinics (E30)</option>
              <option value="E32">School-Based Health (E32)</option>
              <option value="B">Education (B)</option>
              <option value="P">Human Services (P)</option>
            </select>
          </div>
          
          <div className="flex items-end">
            <button
              onClick={searchNonprofits}
              disabled={loading}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>
        </div>
        
        <div className="mt-4 text-sm text-gray-500">
          <p>
            <strong>Data Sources:</strong> ProPublica Nonprofit Explorer • Every.org • IRS TEOS
          </p>
          <p className="mt-1">
            <a 
              href="https://projects.propublica.org/nonprofits/api" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
            >
              ProPublica API
            </a>
            {' • '}
            <a 
              href="https://www.every.org/nonprofit-api" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
            >
              Every.org API
            </a>
            {' • '}
            <a 
              href="https://www.irs.gov/charities-non-profits/tax-exempt-organization-search-bulk-data-downloads" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
            >
              IRS TEOS
            </a>
          </p>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error}
        </div>
      )}

      {/* Results */}
      <div className="bg-white rounded-lg shadow-sm">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {loading ? 'Loading...' : `Found ${nonprofits.length} Organizations`}
          </h2>
        </div>
        
        <div className="divide-y divide-gray-200">
          {nonprofits.length === 0 && !loading ? (
            <div className="px-6 py-12 text-center text-gray-500">
              No nonprofits found. Try adjusting your search criteria.
            </div>
          ) : (
            nonprofits.map((org, index) => (
              <div key={`${org.ein}-${index}`} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      {org.logo_url ? (
                        <img 
                          src={org.logo_url} 
                          alt={org.name}
                          className="w-12 h-12 rounded object-contain bg-gray-100 border border-gray-200"
                          onError={(e) => {
                            e.currentTarget.style.display = 'none'
                            const fallback = e.currentTarget.nextElementSibling as HTMLElement | null
                            if (fallback) fallback.style.display = 'flex'
                          }}
                        />
                      ) : null}
                      <div 
                        className="w-12 h-12 rounded flex items-center justify-center text-white text-lg font-bold"
                        style={{ 
                          backgroundColor: '#52796F',
                          display: org.logo_url ? 'none' : 'flex'
                        }}
                      >
                        {org.name.charAt(0)}
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900">
                          {org.name}
                        </h3>
                        <p className="text-sm text-gray-500">
                          EIN: {org.ein} • {org.city}, {org.state}
                        </p>
                      </div>
                    </div>
                    
                    {(org.description || org.mission) && (
                      <p className="mt-2 text-gray-600">
                        {org.description || org.mission}
                      </p>
                    )}
                    
                    <div className="mt-2 flex flex-wrap gap-2">
                      {org.ntee_description && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          {org.ntee_description}
                        </span>
                      )}
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                        Source: {org.source}
                      </span>
                    </div>
                    
                    {/* Financial Info (from ProPublica) */}
                    {(org.revenue_amount || org.asset_amount) && (
                      <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
                        {org.revenue_amount && (
                          <div>
                            <span className="text-gray-500">Revenue: </span>
                            <span className="font-medium text-gray-900">
                              {formatCurrency(org.revenue_amount)}
                            </span>
                          </div>
                        )}
                        {org.asset_amount && (
                          <div>
                            <span className="text-gray-500">Assets: </span>
                            <span className="font-medium text-gray-900">
                              {formatCurrency(org.asset_amount)}
                            </span>
                          </div>
                        )}
                        {org.income_amount && (
                          <div>
                            <span className="text-gray-500">Income: </span>
                            <span className="font-medium text-gray-900">
                              {formatCurrency(org.income_amount)}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  
                  {org.website_url && (
                    <a
                      href={org.website_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-4 px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
                    >
                      Visit Website
                    </a>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
      
      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-blue-900 mb-2">
          Why This Matters
        </h3>
        <p className="text-blue-800">
          When officials reject policy proposals with technical objections ("We can't do dental 
          screenings - legal liability"), you can instantly show citizens the nonprofits{' '}
          <strong>already doing it successfully</strong>. This bypasses technocratic vetoes, 
          creates accountability pressure, and mobilizes citizens with direct volunteer/donation pathways.
        </p>
        <div className="mt-4 space-y-2 text-sm text-blue-700">
          <p>✓ Access financial data from 3+ million organizations</p>
          <p>✓ Find local service providers already solving the problem</p>
          <p>✓ Show working alternatives to government inaction</p>
          <p>✓ All data is 100% free from public APIs</p>
        </div>
      </div>
      </div>
    </div>
  )
}
