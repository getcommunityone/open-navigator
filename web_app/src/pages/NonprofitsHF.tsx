import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { searchNonprofits } from '../utils/huggingface'
import { formatCurrency } from '../utils/formatters'

const DATASET_NAME = "CommunityOne/one-nonprofits-organizations"

// NTEE Code categories
const NTEE_CATEGORIES = [
  { code: '', label: 'All Categories' },
  { code: 'E', label: 'Health (E)' },
  { code: 'E20', label: 'Hospitals & Medical Centers (E20)' },
  { code: 'E30', label: 'Community Health Centers (E30)' },
  { code: 'E40', label: 'Reproductive Health (E40)' },
  { code: 'E50', label: 'Rehabilitative Care (E50)' },
  { code: 'E60', label: 'Health Support Services (E60)' },
  { code: 'E70', label: 'Public Health (E70)' },
  { code: 'E80', label: 'Health - General & Financing (E80)' },
  { code: 'E90', label: 'Nursing Services (E90)' },
  { code: 'P', label: 'Human Services (P)' },
  { code: 'X', label: 'Religion-Related (X)' },
  { code: 'X20', label: 'Christian (X20)' },
  { code: 'X21', label: 'Protestant (X21)' },
  { code: 'X22', label: 'Roman Catholic (X22)' },
  { code: 'X30', label: 'Jewish (X30)' },
  { code: 'X40', label: 'Islamic (X40)' },
  { code: 'B', label: 'Education (B)' },
  { code: 'C', label: 'Environment (C)' },
  { code: 'D', label: 'Animal-Related (D)' },
  { code: 'F', label: 'Mental Health (F)' },
  { code: 'G', label: 'Disease-Specific (G)' },
  { code: 'H', label: 'Medical Research (H)' },
]

// U.S. States
const US_STATES = [
  { code: '', label: 'All States' },
  { code: 'AL', label: 'Alabama' },
  { code: 'AK', label: 'Alaska' },
  { code: 'AZ', label: 'Arizona' },
  { code: 'AR', label: 'Arkansas' },
  { code: 'CA', label: 'California' },
  { code: 'CO', label: 'Colorado' },
  { code: 'CT', label: 'Connecticut' },
  { code: 'DE', label: 'Delaware' },
  { code: 'FL', label: 'Florida' },
  { code: 'GA', label: 'Georgia' },
  { code: 'HI', label: 'Hawaii' },
  { code: 'ID', label: 'Idaho' },
  { code: 'IL', label: 'Illinois' },
  { code: 'IN', label: 'Indiana' },
  { code: 'IA', label: 'Iowa' },
  { code: 'KS', label: 'Kansas' },
  { code: 'KY', label: 'Kentucky' },
  { code: 'LA', label: 'Louisiana' },
  { code: 'ME', label: 'Maine' },
  { code: 'MD', label: 'Maryland' },
  { code: 'MA', label: 'Massachusetts' },
  { code: 'MI', label: 'Michigan' },
  { code: 'MN', label: 'Minnesota' },
  { code: 'MS', label: 'Mississippi' },
  { code: 'MO', label: 'Missouri' },
  { code: 'MT', label: 'Montana' },
  { code: 'NE', label: 'Nebraska' },
  { code: 'NV', label: 'Nevada' },
  { code: 'NH', label: 'New Hampshire' },
  { code: 'NJ', label: 'New Jersey' },
  { code: 'NM', label: 'New Mexico' },
  { code: 'NY', label: 'New York' },
  { code: 'NC', label: 'North Carolina' },
  { code: 'ND', label: 'North Dakota' },
  { code: 'OH', label: 'Ohio' },
  { code: 'OK', label: 'Oklahoma' },
  { code: 'OR', label: 'Oregon' },
  { code: 'PA', label: 'Pennsylvania' },
  { code: 'RI', label: 'Rhode Island' },
  { code: 'SC', label: 'South Carolina' },
  { code: 'SD', label: 'South Dakota' },
  { code: 'TN', label: 'Tennessee' },
  { code: 'TX', label: 'Texas' },
  { code: 'UT', label: 'Utah' },
  { code: 'VT', label: 'Vermont' },
  { code: 'VA', label: 'Virginia' },
  { code: 'WA', label: 'Washington' },
  { code: 'WV', label: 'West Virginia' },
  { code: 'WI', label: 'Wisconsin' },
  { code: 'WY', label: 'Wyoming' },
]

export default function Nonprofits() {
  const [searchParams] = useSearchParams()
  
  // Initialize from URL parameters
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || 'dental')
  const [state, setState] = useState(searchParams.get('state') || 'AL')
  const [nteeCode, setNteeCode] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 100

  // Update search query from URL when it changes
  useEffect(() => {
    const searchParam = searchParams.get('search')
    const stateParam = searchParams.get('state')
    if (searchParam) setSearchQuery(searchParam)
    if (stateParam) setState(stateParam)
  }, [searchParams])

  // Query HuggingFace dataset
  const { data: nonprofits, isLoading, error } = useQuery({
    queryKey: ['nonprofits-hf', searchQuery, state, nteeCode, page],
    queryFn: async () => {
      return await searchNonprofits({
        dataset: DATASET_NAME,
        query: searchQuery || undefined,
        state: state || undefined,
        nteeCode: nteeCode || undefined,
        limit: pageSize
      })
    },
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  })

  // formatCurrency imported from utils/formatters

  const formatSubsection = (code?: string) => {
    const subsections: Record<string, string> = {
      '3': '501(c)(3) - Charitable',
      '4': '501(c)(4) - Social Welfare',
      '5': '501(c)(5) - Labor/Agricultural',
      '6': '501(c)(6) - Business League',
      '7': '501(c)(7) - Social/Recreational',
      '8': '501(c)(8) - Fraternal Beneficiary',
      '9': '501(c)(9) - Employees Association',
      '10': '501(c)(10) - Domestic Fraternal',
      '13': '501(c)(13) - Cemetery Company',
      '19': '501(c)(19) - Veterans Organization',
    }
    return subsections[code || ''] || `501(c)(${code})`
  }

  return (
    <div className="min-h-screen p-8" style={{ backgroundColor: '#F1F5F9' }}>
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold mb-2" style={{ color: '#354F52' }}>
            Nonprofit Organizations
          </h1>
          <p className="text-gray-600">
            Explore 1.9M+ U.S. nonprofits from IRS EO-BMF via HuggingFace Datasets
          </p>
          <div className="mt-2 flex items-center gap-2 text-sm text-gray-500">
            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded">
              📊 Source: HuggingFace Dataset
            </span>
            <span className="px-2 py-1 bg-green-100 text-green-700 rounded">
              ✅ 1,952,238 organizations
            </span>
            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded">
              🔄 Updated Monthly (IRS)
            </span>
          </div>
        </div>

        {/* Search Form */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Search Query */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search
              </label>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., dental, clinic, food bank"
              />
            </div>

            {/* State Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                State
              </label>
              <select
                value={state}
                onChange={(e) => setState(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {US_STATES.map(s => (
                  <option key={s.code} value={s.code}>{s.label}</option>
                ))}
              </select>
            </div>

            {/* NTEE Category */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Category (NTEE)
              </label>
              <select
                value={nteeCode}
                onChange={(e) => setNteeCode(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {NTEE_CATEGORIES.map(cat => (
                  <option key={cat.code} value={cat.code}>{cat.label}</option>
                ))}
              </select>
            </div>

            {/* Search Button */}
            <div className="flex items-end">
              <button
                onClick={() => setPage(0)} // Reset to page 0 on new search
                className="w-full px-4 py-2 text-white rounded-md hover:opacity-90 transition-opacity"
                style={{ backgroundColor: '#52796F' }}
              >
                🔍 Search
              </button>
            </div>
          </div>

          {/* Active Filters */}
          <div className="mt-4 flex flex-wrap gap-2">
            {searchQuery && (
              <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">
                Query: "{searchQuery}"
              </span>
            )}
            {state && (
              <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm">
                State: {US_STATES.find(s => s.code === state)?.label}
              </span>
            )}
            {nteeCode && (
              <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm">
                Category: {NTEE_CATEGORIES.find(c => c.code === nteeCode)?.label}
              </span>
            )}
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
            <p className="mt-4 text-gray-600">Loading nonprofits from HuggingFace...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <h3 className="text-red-800 font-semibold mb-2">Error Loading Data</h3>
            <p className="text-red-600">{error.message}</p>
            <p className="text-sm text-red-500 mt-2">
              Make sure the dataset is uploaded to HuggingFace. Run: <code>python scripts/upload_nonprofits_to_hf.py --all</code>
            </p>
          </div>
        )}

        {/* Results */}
        {!isLoading && !error && nonprofits && (
          <>
            <div className="bg-white rounded-lg shadow-sm p-4">
              <p className="text-gray-700">
                Found <strong>{nonprofits.length}</strong> nonprofits
                {nonprofits.length === pageSize && ' (showing first 100)'}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {nonprofits.map((org) => (
                <div
                  key={org.ein}
                  className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-shadow"
                >
                  <div className="space-y-3">
                    {/* Organization Name */}
                    <h3 className="text-lg font-semibold" style={{ color: '#354F52' }}>
                      {org.name}
                    </h3>

                    {/* EIN */}
                    <div className="text-sm text-gray-600">
                      <span className="font-medium">EIN:</span> {org.ein}
                    </div>

                    {/* Location */}
                    <div className="text-sm text-gray-600">
                      <span className="font-medium">📍 Location:</span>{' '}
                      {org.city && org.state ? (
                        <>
                          {org.city}, {org.state} {org.zip_code}
                        </>
                      ) : (
                        org.state || 'N/A'
                      )}
                    </div>

                    {/* NTEE Code */}
                    {org.ntee_code && (
                      <div className="text-sm">
                        <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs">
                          {org.ntee_code}
                        </span>
                      </div>
                    )}

                    {/* Subsection */}
                    {org.subsection_code && (
                      <div className="text-sm text-gray-600">
                        <span className="font-medium">Type:</span> {formatSubsection(org.subsection_code)}
                      </div>
                    )}

                    {/* Financials */}
                    <div className="pt-3 border-t space-y-1">
                      <div className="text-sm text-gray-600">
                        <span className="font-medium">Assets:</span> {formatCurrency(org.asset_amount)}
                      </div>
                      <div className="text-sm text-gray-600">
                        <span className="font-medium">Income:</span> {formatCurrency(org.income_amount)}
                      </div>
                      <div className="text-sm text-gray-600">
                        <span className="font-medium">Revenue:</span> {formatCurrency(org.revenue_amount)}
                      </div>
                    </div>

                    {/* Status */}
                    {org.tax_exempt_status && (
                      <div className="text-sm">
                        <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs">
                          {org.tax_exempt_status === '1' ? '✅ Tax-Exempt' : 'Status: ' + org.tax_exempt_status}
                        </span>
                      </div>
                    )}

                    {/* Ruling Date */}
                    {org.ruling_date && (
                      <div className="text-xs text-gray-500">
                        Ruling Date: {org.ruling_date}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* No Results */}
            {nonprofits.length === 0 && (
              <div className="bg-gray-50 rounded-lg p-12 text-center">
                <p className="text-gray-600 text-lg">No nonprofits found matching your criteria</p>
                <p className="text-gray-500 text-sm mt-2">Try adjusting your filters or search query</p>
              </div>
            )}
          </>
        )}

        {/* Data Source Attribution */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-lg font-semibold mb-3" style={{ color: '#354F52' }}>
            📚 Data Source
          </h3>
          <div className="space-y-2 text-sm text-gray-600">
            <p>
              <strong>Source:</strong> IRS Exempt Organizations Business Master File (EO-BMF)
            </p>
            <p>
              <strong>Dataset:</strong>{' '}
              <a
                href={`https://huggingface.co/datasets/${DATASET_NAME}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                {DATASET_NAME}
              </a>
            </p>
            <p>
              <strong>Records:</strong> 1,952,238 organizations
            </p>
            <p>
              <strong>Updated:</strong> Monthly by IRS
            </p>
            <p>
              <strong>License:</strong> Public Domain (U.S. government data)
            </p>
            <p className="pt-2 border-t">
              <a
                href="https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                View IRS EO-BMF Documentation →
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
