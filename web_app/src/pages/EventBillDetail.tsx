import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import MeetingPlayer from '../components/MeetingPlayer'
import {
  ArrowLeftIcon,
  DocumentTextIcon,
  MapPinIcon,
  CalendarIcon,
} from '@heroicons/react/24/outline'

interface BillReferenceDetail {
  event_bill_id: string
  official_number?: string | null
  title?: string | null
  leg_type?: string | null
  status?: string | null
  relevance?: string | null
  jurisdiction_name?: string | null
  jurisdiction_type?: string | null
  state?: string | null
  state_code?: string | null
  city?: string | null
  c1_event_id?: string | null
  meeting_name?: string | null
  meeting_date?: string | null
  meeting_video_id?: string | null
  source_ai_model?: string | null
  extracted_at?: string | null
}

function statusColor(status?: string | null): string {
  const s = (status || '').toLowerCase()
  if (/(approv|pass|adopt|grant)/.test(s)) return 'bg-green-100 text-green-800'
  if (/(defer|table|postpon|continu|discuss|hold|read)/.test(s)) return 'bg-yellow-100 text-yellow-800'
  if (/(den|reject|fail|veto|withdraw)/.test(s)) return 'bg-red-100 text-red-800'
  return 'bg-gray-100 text-gray-800'
}

export default function EventBillDetail() {
  const { id } = useParams<{ id: string }>()

  const { data: bill, isLoading, error } = useQuery<BillReferenceDetail>({
    queryKey: ['event-bill', id],
    queryFn: async () => {
      const response = await api.get(`/event-bill/${id}`)
      return response.data
    },
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="flex justify-center items-center h-96">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading legislation details...</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error || !bill) {
    const errorMessage =
      (error as any)?.response?.data?.detail ||
      (error as any)?.message ||
      'Unable to load legislation details'
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center">
            <div className="text-red-600 text-5xl mb-4">⚠️</div>
            <h3 className="text-lg font-semibold text-red-900 mb-2">Legislation not found</h3>
            <p className="text-red-700 mb-4">{errorMessage}</p>
            <Link
              to="/search"
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              <ArrowLeftIcon className="h-5 w-5" />
              Back to Search
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const location = [bill.jurisdiction_name, bill.state].filter(Boolean).join(', ')

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Back Button */}
        <div className="mb-6">
          <Link
            to="/search"
            className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium"
          >
            <ArrowLeftIcon className="h-5 w-5" />
            Back to Search
          </Link>
        </div>

        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-center gap-2 flex-wrap mb-3">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium bg-indigo-100 text-indigo-800">
              <DocumentTextIcon className="h-4 w-4" />
              {bill.leg_type || 'Legislation'}
            </span>
            {bill.official_number && (
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-bold bg-blue-100 text-blue-800">
                {bill.official_number}
              </span>
            )}
            {bill.status && (
              <span
                className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${statusColor(
                  bill.status,
                )}`}
              >
                {bill.status}
              </span>
            )}
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            {bill.title || 'Untitled legislation'}
          </h1>
          {location && (
            <div className="flex items-center gap-1 text-sm text-gray-600">
              <MapPinIcon className="h-4 w-4" />
              <span>{location}</span>
            </div>
          )}
        </div>

        {/* Why it matters */}
        {bill.relevance && (
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Why it matters</h2>
            <p className="text-sm text-gray-700 whitespace-pre-line">{bill.relevance}</p>
          </div>
        )}

        {/* Meeting context */}
        {(bill.meeting_name || bill.meeting_date) && (
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <CalendarIcon className="h-5 w-5" />
              Meeting
            </h2>
            <div className="text-sm text-gray-700">
              {bill.meeting_name && <span className="font-medium">{bill.meeting_name}</span>}
              {bill.meeting_name && bill.meeting_date && <span className="text-gray-400"> • </span>}
              {bill.meeting_date && (
                <span>{new Date(bill.meeting_date).toLocaleDateString()}</span>
              )}
            </div>
          </div>
        )}

        {/* Meeting recording + clickable transcript */}
        {bill.meeting_video_id && (
          <MeetingPlayer
            videoId={bill.meeting_video_id}
            caption={[bill.meeting_name, bill.meeting_date
              ? new Date(bill.meeting_date).toLocaleDateString()
              : null]
              .filter(Boolean)
              .join(' • ') || undefined}
            targetText={[bill.official_number, bill.title, bill.relevance]
              .filter(Boolean)
              .join('. ') || undefined}
          />
        )}

        {/* Provenance */}
        <div className="bg-white rounded-lg shadow-sm p-6 text-xs text-gray-500 space-y-1">
          {bill.source_ai_model && <div>Extracted by {bill.source_ai_model}</div>}
          {bill.extracted_at && (
            <div>Extracted {new Date(bill.extracted_at).toLocaleDateString()}</div>
          )}
          {bill.c1_event_id && <div>Event: {bill.c1_event_id}</div>}
        </div>
      </div>
    </div>
  )
}
