import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ChevronDownIcon,
  ChevronUpIcon,
  CheckCircleIcon,
  GlobeAltIcon,
  VideoCameraIcon,
  DocumentTextIcon,
  ClipboardDocumentListIcon,
  ShareIcon
} from '@heroicons/react/24/outline'
import api from '../lib/api'

interface JurisdictionDiscoveryProps {
  jurisdiction: {
    /** Stable jurisdiction id (Census GEOID) — enables the scoped meeting-docs route. */
    jurisdiction_id?: string
    name: string
    state: string
    website?: string
    youtube_channels?: string[]
    facebook?: string
    twitter?: string
    agenda_portal?: string
    meeting_platform?: string
    completeness: number
  }
}

/** Shape of GET /api/jurisdiction/{id}/meeting-documents (see MeetingDocuments.tsx). */
interface MeetingDocument {
  document_type: string
  document_url: string
  source: string
}
interface MeetingDocumentGroup {
  doc_date: string
  body_name: string | null
  event_meeting_id: string | null
  documents: MeetingDocument[]
}
interface MeetingDocumentsResponse {
  jurisdiction_id: string
  jurisdiction_name?: string | null
  meeting_count: number
  document_count: number
  meetings: MeetingDocumentGroup[]
}

/** How many recent meetings to preview inline before linking out to the full page. */
const PREVIEW_MEETING_LIMIT = 3

function typeLabel(documentType: string): string {
  if (!documentType) return 'Document'
  return documentType.charAt(0).toUpperCase() + documentType.slice(1)
}

function formatDate(docDate: string): string {
  const d = new Date(docDate)
  if (Number.isNaN(d.getTime())) return docDate
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

/**
 * Inline meeting-documents preview shown by default in each jurisdiction card.
 *
 * Fetches the jurisdiction's scraped agenda/minutes from
 *   GET /api/jurisdiction/{jurisdiction_id}/meeting-documents
 * and shows the most recent few meetings with their document chips, plus a link
 * to the full meeting-documents browser. Renders an explicit empty state (never
 * fabricated rows) when the jurisdiction has no scraped documents.
 */
function MeetingDocumentsPreview({ jurisdictionId }: { jurisdictionId: string }) {
  const { data, isLoading, isError } = useQuery<MeetingDocumentsResponse>({
    queryKey: ['meeting-documents-preview', jurisdictionId],
    queryFn: async () => {
      const response = await api.get<MeetingDocumentsResponse>(
        `/jurisdiction/${encodeURIComponent(jurisdictionId)}/meeting-documents`,
      )
      return response.data
    },
    enabled: Boolean(jurisdictionId),
    staleTime: 5 * 60 * 1000,
  })

  if (isLoading) {
    return (
      <div className="border-t border-gray-200 px-4 py-4 text-sm text-gray-500">
        Loading meeting documents…
      </div>
    )
  }

  if (isError) {
    return (
      <div className="border-t border-gray-200 px-4 py-4 text-sm text-gray-500">
        Couldn’t load meeting documents.
      </div>
    )
  }

  const meetings = data?.meetings ?? []

  if (meetings.length === 0) {
    return (
      <div className="border-t border-gray-200 px-4 py-4 text-sm text-gray-500">
        No meeting documents available yet.
      </div>
    )
  }

  const preview = meetings.slice(0, PREVIEW_MEETING_LIMIT)

  return (
    <div className="border-t border-gray-200 px-4 py-3">
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
        <ClipboardDocumentListIcon className="h-4 w-4" />
        Recent meeting documents
      </p>
      <div className="divide-y divide-gray-100">
        {preview.map((group, idx) => (
          <div
            key={group.event_meeting_id ?? `${group.doc_date}-${idx}`}
            className="flex flex-col gap-2 py-2 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-gray-900">
                {group.body_name || 'Meeting'}
              </p>
              <p className="text-xs text-gray-500">{formatDate(group.doc_date)}</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {group.documents.map((doc, docIdx) => (
                <a
                  key={`${doc.document_type}-${docIdx}`}
                  href={doc.document_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded-md border border-[#1d6b5f]/30 px-2.5 py-1 text-xs font-medium text-[#1d6b5f] transition-colors hover:bg-[#1d6b5f]/5"
                >
                  <DocumentTextIcon className="h-3.5 w-3.5" />
                  {typeLabel(doc.document_type)}
                </a>
              ))}
            </div>
          </div>
        ))}
      </div>
      <Link
        to={`/jurisdiction/${encodeURIComponent(jurisdictionId)}/meetings`}
        className="mt-2 inline-block text-sm font-medium text-[#1d6b5f] hover:underline"
      >
        View all {data!.document_count.toLocaleString()} document
        {data!.document_count === 1 ? '' : 's'} across{' '}
        {data!.meeting_count.toLocaleString()} meeting
        {data!.meeting_count === 1 ? '' : 's'} →
      </Link>
    </div>
  )
}

export default function JurisdictionDiscovery({ jurisdiction }: JurisdictionDiscoveryProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const hasData = jurisdiction.website || jurisdiction.youtube_channels?.length || jurisdiction.facebook

  return (
    <div className="border border-gray-200 rounded-lg bg-white hover:shadow-md transition-shadow">
      {/* Header - Always Visible */}
      <div className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <CheckCircleIcon className="h-5 w-5 text-green-600" />
              <h3 className="font-bold text-gray-900 uppercase">
                {jurisdiction.name}, {jurisdiction.state} - DISCOVERY COMPLETE!
              </h3>
            </div>
            
            {/* Summary Stats */}
            <div className="mt-2 flex flex-wrap gap-3 text-sm text-gray-600">
              {jurisdiction.website && (
                <span className="flex items-center gap-1">
                  <GlobeAltIcon className="h-4 w-4" />
                  Website
                </span>
              )}
              {jurisdiction.youtube_channels && jurisdiction.youtube_channels.length > 0 && (
                <span className="flex items-center gap-1">
                  <VideoCameraIcon className="h-4 w-4" />
                  {jurisdiction.youtube_channels.length} YouTube Channel{jurisdiction.youtube_channels.length > 1 ? 's' : ''}
                </span>
              )}
              {jurisdiction.agenda_portal && (
                <span className="flex items-center gap-1">
                  <DocumentTextIcon className="h-4 w-4" />
                  Agenda Portal
                </span>
              )}
              {(jurisdiction.facebook || jurisdiction.twitter) && (
                <span className="flex items-center gap-1">
                  <ShareIcon className="h-4 w-4" />
                  Social Media
                </span>
              )}
            </div>

            {/* Completeness Bar */}
            {hasData && (
              <div className="mt-3">
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-green-600 h-2 rounded-full transition-all"
                      style={{ width: `${jurisdiction.completeness}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-gray-700">
                    {jurisdiction.completeness}%
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Completeness: ~{Math.round(jurisdiction.completeness)}% - {
                    jurisdiction.completeness >= 75 ? 'Good' : 
                    jurisdiction.completeness >= 50 ? 'Fair' : 
                    'Limited'
                  } digital infrastructure!
                </p>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="ml-4 flex items-center gap-2">
            {jurisdiction.jurisdiction_id && (
              <Link
                to={`/jurisdiction/${encodeURIComponent(jurisdiction.jurisdiction_id)}/meetings`}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#1d6b5f]/30 px-3 py-1.5 text-sm font-medium text-[#1d6b5f] transition-colors hover:bg-[#1d6b5f]/5"
              >
                <DocumentTextIcon className="h-4 w-4" />
                Meeting documents
              </Link>
            )}

            {/* Expand/Collapse Button */}
            {hasData && (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                {isExpanded ? (
                  <ChevronUpIcon className="h-5 w-5 text-gray-600" />
                ) : (
                  <ChevronDownIcon className="h-5 w-5 text-gray-600" />
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Expandable Details */}
      {isExpanded && hasData && (
        <div className="border-t border-gray-200 p-4 bg-gray-50">
          <h4 className="text-lg font-bold text-gray-900 mb-4">
            🎯 {jurisdiction.name.toUpperCase()}, {jurisdiction.state} FINDINGS
          </h4>

          <div className="space-y-4">
            {/* Website */}
            {jurisdiction.website && (
              <div>
                <h5 className="font-semibold text-gray-700 mb-2">🌐 Official Website:</h5>
                <a 
                  href={jurisdiction.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline flex items-center gap-2"
                >
                  ✅ {jurisdiction.website}
                </a>
              </div>
            )}

            {/* Agenda Portal */}
            {jurisdiction.agenda_portal && (
              <div>
                <h5 className="font-semibold text-gray-700 mb-2">📄 Meeting/Agenda Portal:</h5>
                <a 
                  href={jurisdiction.agenda_portal}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline flex items-center gap-2"
                >
                  ✅ {jurisdiction.agenda_portal}
                </a>
              </div>
            )}

            {/* YouTube Channels */}
            {jurisdiction.youtube_channels && jurisdiction.youtube_channels.length > 0 && (
              <div>
                <h5 className="font-semibold text-gray-700 mb-2">📺 YouTube Channels:</h5>
                {jurisdiction.youtube_channels.map((channel, idx) => (
                  <div key={idx} className="ml-4 text-blue-600 hover:underline">
                    ✅ @{channel}
                  </div>
                ))}
              </div>
            )}

            {/* Social Media */}
            {(jurisdiction.facebook || jurisdiction.twitter) && (
              <div>
                <h5 className="font-semibold text-gray-700 mb-2">📱 Social Media:</h5>
                <div className="ml-4 space-y-1">
                  {jurisdiction.facebook && (
                    <div className="text-blue-600">
                      ✅ Facebook: {jurisdiction.facebook}
                    </div>
                  )}
                  {jurisdiction.twitter && (
                    <div className="text-blue-600">
                      ✅ Twitter: {jurisdiction.twitter}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Meeting Platform */}
            {jurisdiction.meeting_platform && (
              <div>
                <h5 className="font-semibold text-gray-700 mb-2">🏛️ Meeting Platform:</h5>
                <div className="ml-4">
                  {jurisdiction.meeting_platform}
                </div>
              </div>
            )}

            {/* Summary Table */}
            <div className="mt-6 border-t border-gray-300 pt-4">
              <h5 className="font-semibold text-gray-700 mb-3">📊 {jurisdiction.name.toUpperCase()} SUMMARY</h5>
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead>
                  <tr className="bg-gray-100">
                    <th className="px-3 py-2 text-left font-semibold">Category</th>
                    <th className="px-3 py-2 text-left font-semibold">Found</th>
                    <th className="px-3 py-2 text-left font-semibold">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  <tr>
                    <td className="px-3 py-2">Website</td>
                    <td className="px-3 py-2">{jurisdiction.website ? '✅' : '❌'}</td>
                    <td className="px-3 py-2 text-gray-600">
                      {jurisdiction.website ? new URL(jurisdiction.website).hostname : 'Not found'}
                    </td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2">YouTube</td>
                    <td className="px-3 py-2">{jurisdiction.youtube_channels?.length ? '✅' : '❌'}</td>
                    <td className="px-3 py-2 text-gray-600">
                      {jurisdiction.youtube_channels?.length || 0} channel{jurisdiction.youtube_channels?.length !== 1 ? 's' : ''}
                    </td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2">Agendas</td>
                    <td className="px-3 py-2">{jurisdiction.agenda_portal ? '✅' : '❌'}</td>
                    <td className="px-3 py-2 text-gray-600">
                      {jurisdiction.agenda_portal ? 'Portal found' : 'Not available'}
                    </td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2">Social</td>
                    <td className="px-3 py-2">{jurisdiction.facebook || jurisdiction.twitter ? '✅' : '❌'}</td>
                    <td className="px-3 py-2 text-gray-600">
                      {[jurisdiction.facebook && 'Facebook', jurisdiction.twitter && 'Twitter'].filter(Boolean).join(', ') || 'None'}
                    </td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2">Platform</td>
                    <td className="px-3 py-2">{jurisdiction.meeting_platform ? '✅' : '❌'}</td>
                    <td className="px-3 py-2 text-gray-600">
                      {jurisdiction.meeting_platform || 'Unknown'}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Key Takeaway */}
            <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <h5 className="font-semibold text-blue-900 mb-2">💡 KEY TAKEAWAY</h5>
              <p className="text-sm text-blue-800">
                The automation successfully discovered:
              </p>
              <ul className="mt-2 space-y-1 text-sm text-blue-800">
                {jurisdiction.website && <li>✅ Official website (automatic)</li>}
                {(jurisdiction.youtube_channels?.length ?? 0) > 0 && <li>✅ YouTube channels (automatic)</li>}
                {jurisdiction.agenda_portal && <li>✅ Agenda portal (found via link scanning)</li>}
                {(jurisdiction.facebook || jurisdiction.twitter) && <li>✅ Social media (automatic)</li>}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Default body: meeting documents for this jurisdiction. */}
      {jurisdiction.jurisdiction_id && (
        <MeetingDocumentsPreview jurisdictionId={jurisdiction.jurisdiction_id} />
      )}
    </div>
  )
}
