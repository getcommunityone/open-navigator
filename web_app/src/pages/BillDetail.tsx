import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { ArrowLeftIcon, CalendarIcon, DocumentTextIcon, BuildingLibraryIcon } from '@heroicons/react/24/outline'

interface BillDetail {
  bill_id: string
  bill_number: string
  title: string
  classification: string[]
  session: string
  session_name: string
  first_action_date: string
  latest_action_date: string
  latest_action: string
  jurisdiction: string
  state: string
  openstates_url?: string
  limited_data?: boolean
  note?: string
  sponsors?: Array<{
    name: string
    primary: boolean
    classification?: string
  }>
  actions?: Array<{
    date: string
    description: string
    classification: string[]
  }>
  sources?: Array<{
    url: string
    note: string
  }>
}

export default function BillDetail() {
  const { billId } = useParams<{ billId: string }>()

  const { data: bill, isLoading, error } = useQuery<BillDetail>({
    queryKey: ['bill', billId],
    queryFn: async () => {
      const response = await api.get(`/bills/${billId}`)
      return response.data
    },
    enabled: !!billId,
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="flex justify-center items-center h-96">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading bill details...</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error || !bill) {
    const errorMessage = error instanceof Error 
      ? error.message 
      : (error as any)?.response?.data?.detail 
      ? (error as any).response.data.detail 
      : (error as any)?.message 
      ? (error as any).message 
      : 'Unable to load bill details'
    
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center">
            <div className="text-red-600 text-5xl mb-4">⚠️</div>
            <h3 className="text-lg font-semibold text-red-900 mb-2">Bill not found</h3>
            <p className="text-red-700 mb-4">{errorMessage}</p>
            <Link
              to="/policy-map"
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              <ArrowLeftIcon className="h-5 w-5" />
              Back to Policy Map
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const statusColor = bill.latest_action?.toLowerCase().includes('enact') ? 'green' :
                      bill.latest_action?.toLowerCase().includes('fail') ? 'red' :
                      bill.latest_action?.toLowerCase().includes('veto') ? 'red' : 'yellow'

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Back Button */}
        <div className="mb-6">
          <Link
            to="/policy-map"
            className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium"
          >
            <ArrowLeftIcon className="h-5 w-5" />
            Back to Policy Map
          </Link>
        </div>

        {/* Limited Data Notice */}
        {bill.limited_data && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
            <div className="flex gap-3">
              <div className="text-yellow-600 text-xl">ℹ️</div>
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-yellow-900 mb-1">Limited Information Available</h3>
                <p className="text-sm text-yellow-800">{bill.note || 'Full bill details are not available yet for this state. Only summary information is shown.'}</p>
              </div>
            </div>
          </div>
        )}

        {/* Bill Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <span className="inline-flex items-center px-4 py-2 rounded-lg text-lg font-bold bg-blue-100 text-blue-800">
                  {bill.bill_number}
                </span>
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
                  {bill.state}
                </span>
                <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                  statusColor === 'green' ? 'bg-green-100 text-green-800' :
                  statusColor === 'red' ? 'bg-red-100 text-red-800' :
                  'bg-yellow-100 text-yellow-800'
                }`}>
                  {bill.latest_action || 'Status Unknown'}
                </span>
              </div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                {bill.title}
              </h1>
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <div className="flex items-center gap-1">
                  <BuildingLibraryIcon className="h-4 w-4" />
                  <span>{bill.session_name}</span>
                </div>
                {bill.classification && bill.classification.length > 0 && (
                  <span className="text-gray-400">•</span>
                )}
                {bill.classification && bill.classification.length > 0 && (
                  <span>{bill.classification.join(', ')}</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Timeline */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
            <CalendarIcon className="h-5 w-5" />
            Timeline
          </h2>
          <div className="space-y-3">
            {bill.first_action_date && (
              <div className="flex gap-4">
                <div className="text-sm text-gray-600 w-32">
                  {new Date(bill.first_action_date).toLocaleDateString()}
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-900">First Action</div>
                </div>
              </div>
            )}
            {bill.latest_action_date && (
              <div className="flex gap-4">
                <div className="text-sm text-gray-600 w-32">
                  {new Date(bill.latest_action_date).toLocaleDateString()}
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-900">Latest Action</div>
                  <div className="text-sm text-gray-600">{bill.latest_action}</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Sponsors */}
        {bill.sponsors && bill.sponsors.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Sponsors</h2>
            <div className="space-y-2">
              {bill.sponsors.map((sponsor, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <span className={`px-2 py-1 text-xs font-medium rounded ${
                    sponsor.primary ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'
                  }`}>
                    {sponsor.primary ? 'Primary' : 'Co-sponsor'}
                  </span>
                  <span className="text-sm text-gray-900">{sponsor.name}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions History */}
        {bill.actions && bill.actions.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <DocumentTextIcon className="h-5 w-5" />
              Legislative Actions
            </h2>
            <div className="space-y-3">
              {bill.actions.map((action, idx) => (
                <div key={idx} className="flex gap-4 border-l-2 border-gray-200 pl-4">
                  <div className="text-sm text-gray-600 w-32">
                    {new Date(action.date).toLocaleDateString()}
                  </div>
                  <div className="flex-1">
                    <div className="text-sm text-gray-900">{action.description}</div>
                    {action.classification && action.classification.length > 0 && (
                      <div className="text-xs text-gray-500 mt-1">
                        {action.classification.join(', ')}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Source Links */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">Official Sources</h2>
          <div className="space-y-2">
            {bill.openstates_url && (
              <a
                href={bill.openstates_url}
                target="_blank"
                rel="noopener noreferrer"
                className="block text-blue-600 hover:text-blue-700 text-sm hover:underline"
              >
                View on OpenStates →
              </a>
            )}
            {bill.sources && bill.sources.map((source: any, idx: number) => (
              <a
                key={idx}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block text-blue-600 hover:text-blue-700 text-sm hover:underline"
              >
                {source.note || 'View on Legislature Website'} →
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
