import { useState } from 'react'
import {
  ChartBarIcon,
  CurrencyDollarIcon,
  ArrowTrendingUpIcon,
  DocumentChartBarIcon,
} from '@heroicons/react/24/outline'

// Commented out for now - will be used when API is ready
// import { useQuery } from '@tanstack/react-query'
// import axios from 'axios'

// interface BudgetData {
//   jurisdiction: string
//   state: string
//   fiscal_year: string
//   total_budget: number
//   budget_change: number
//   categories: {
//     education: number
//     infrastructure: number
//     public_safety: number
//     health: number
//     other: number
//   }
// }

export default function Analytics() {
  const [selectedState, setSelectedState] = useState<string>('all')
  const [fiscalYear, setFiscalYear] = useState<string>('2024')

  // Commented out for now - will be implemented when API is ready
  // const { data, isLoading } = useQuery<BudgetData[]>({
  //   queryKey: ['budget-analytics', selectedState, fiscalYear],
  //   queryFn: async () => {
  //     const response = await axios.get('/api/budgets', {
  //       params: { state: selectedState, year: fiscalYear },
  //     })
  //     return response.data.budgets || []
  //   },
  // })

  return (
    <div className="min-h-screen p-8" style={{ backgroundColor: '#F1F5F9' }}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <ChartBarIcon className="h-8 w-8" style={{ color: '#52796F' }} />
            <h1 className="text-3xl font-bold" style={{ color: '#354F52' }}>
              Budget Analysis
            </h1>
          </div>
          <p className="text-gray-600">
            Explore city, county, and school budgets with budget-to-minutes delta analysis
          </p>
        </div>

        {/* Filter Controls */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                State
              </label>
              <select
                value={selectedState}
                onChange={(e) => setSelectedState(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:outline-none"
              >
                <option value="all">All States</option>
                <option value="AL">Alabama</option>
                <option value="GA">Georgia</option>
                <option value="MA">Massachusetts</option>
                <option value="WA">Washington</option>
                <option value="WI">Wisconsin</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Fiscal Year
              </label>
              <select
                value={fiscalYear}
                onChange={(e) => setFiscalYear(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:outline-none"
              >
                <option value="2024">FY 2024</option>
                <option value="2023">FY 2023</option>
                <option value="2022">FY 2022</option>
              </select>
            </div>
          </div>
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4" style={{ borderColor: '#354F52' }}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 uppercase tracking-wide">
                  Jurisdictions Tracked
                </p>
                <p className="mt-2 text-3xl font-bold" style={{ color: '#354F52' }}>
                  90,000+
                </p>
              </div>
              <DocumentChartBarIcon className="h-12 w-12 text-gray-400" />
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4" style={{ borderColor: '#52796F' }}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 uppercase tracking-wide">
                  Budget Records
                </p>
                <p className="mt-2 text-3xl font-bold" style={{ color: '#52796F' }}>
                  15,000+
                </p>
              </div>
              <CurrencyDollarIcon className="h-12 w-12 text-gray-400" />
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-emerald-500">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 uppercase tracking-wide">
                  Avg Budget Increase
                </p>
                <p className="mt-2 text-3xl font-bold text-emerald-600 flex items-center gap-2">
                  +3.2%
                  <ArrowTrendingUpIcon className="h-6 w-6" />
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-amber-500">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 uppercase tracking-wide">
                  States Covered
                </p>
                <p className="mt-2 text-3xl font-bold text-amber-600">
                  50
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Features Section */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h3 className="text-lg font-semibold mb-4" style={{ color: '#354F52' }}>
              Budget-to-Minutes Delta Analysis
            </h3>
            <p className="text-gray-600 mb-4">
              Compare what governments <strong>say</strong> in meeting minutes versus what they <strong>actually allocate</strong> in budgets.
            </p>
            <ul className="space-y-2 text-sm text-gray-700">
              <li className="flex items-start gap-2">
                <span className="text-green-600 font-bold">✓</span>
                Track rhetoric vs. reality in budget decisions
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600 font-bold">✓</span>
                Identify funding priorities and gaps
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-600 font-bold">✓</span>
                Monitor year-over-year changes
              </li>
            </ul>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <h3 className="text-lg font-semibold mb-4" style={{ color: '#52796F' }}>
              Budget Categories Tracked
            </h3>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-700">Education & Schools</span>
                  <span className="font-semibold">35%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div className="bg-blue-600 h-2 rounded-full" style={{ width: '35%' }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-700">Public Safety</span>
                  <span className="font-semibold">25%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div className="bg-red-600 h-2 rounded-full" style={{ width: '25%' }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-700">Infrastructure</span>
                  <span className="font-semibold">20%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div className="bg-amber-600 h-2 rounded-full" style={{ width: '20%' }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-700">Health & Human Services</span>
                  <span className="font-semibold">15%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div className="bg-green-600 h-2 rounded-full" style={{ width: '15%' }}></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Coming Soon / Data Integration Notice */}
        <div className="bg-white rounded-lg shadow-sm p-8 text-center border-2 border-dashed border-gray-300">
          <ChartBarIcon className="h-16 w-16 mx-auto text-gray-400 mb-4" />
          <h3 className="text-xl font-semibold mb-2" style={{ color: '#354F52' }}>
            Budget Data Integration In Progress
          </h3>
          <p className="text-gray-600 max-w-2xl mx-auto">
            We're currently integrating budget data from cities, counties, and school districts across all 50 states.
            Check back soon for interactive budget comparisons, trend analysis, and meeting-to-budget correlation insights.
          </p>
          <div className="mt-6">
            <a
              href="/documents?search=budget"
              className="inline-block px-6 py-3 rounded-lg text-white transition-colors"
              style={{ backgroundColor: '#52796F' }}
              onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#354F52'}
              onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#52796F'}
            >
              Search Budget Meeting Minutes
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
