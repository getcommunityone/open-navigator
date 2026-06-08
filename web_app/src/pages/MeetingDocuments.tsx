import { useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  DocumentTextIcon,
  ClipboardDocumentListIcon,
  ArrowLeftIcon,
  ArrowsRightLeftIcon,
} from '@heroicons/react/24/outline'
import api from '../lib/api'
import { withSpan } from '../instrumentation'
import {
  DocumentViewerProvider,
  useDocumentViewer,
} from '../components/DocumentViewerContext'

/**
 * Jurisdiction-scoped "Meeting Documents" browser.
 *
 * Lists a jurisdiction's scraped agenda/minutes documents (2021–2026) grouped by
 * year and meeting, fetched from
 *   GET /api/jurisdiction/{jurisdiction_id}/meeting-documents
 * (the `api` client already prefixes `/api`).
 *
 * Clicking a document opens it in the shared inline DocumentViewer (PDF paged
 * inline; HTML/Word fall back to a typed "open original" card) via
 * DocumentViewerContext — the same popout used on the decision detail page.
 */

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

/** Derive the 4-digit calendar year (string) from an ISO-ish date. */
function yearOf(docDate: string): string {
  // doc_date is "YYYY-MM-DD"; the year is the leading 4 chars.
  const match = /^(\d{4})/.exec(docDate)
  return match ? match[1] : 'Undated'
}

/** Human label for a document type ("agenda" -> "Agenda"). */
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
 * A clickable document chip. Opens the document in the shared inline viewer when a
 * DocumentViewerProvider is mounted; otherwise degrades to opening the original in
 * a new tab. Mirrors DecisionDetail's DocLinkChip.
 */
function DocumentChip({
  document,
  caption,
}: {
  document: MeetingDocument
  caption?: string
}) {
  const viewer = useDocumentViewer()
  const label = typeLabel(document.document_type)
  const isAgenda = document.document_type.toLowerCase() === 'agenda'
  const Icon = isAgenda ? ClipboardDocumentListIcon : DocumentTextIcon
  const base =
    'inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors'
  const style = isAgenda
    ? 'border-[#1d6b5f]/30 text-[#1d6b5f] hover:bg-[#1d6b5f]/5'
    : 'border-amber-300 text-amber-700 hover:bg-amber-50'

  if (viewer) {
    return (
      <button
        type="button"
        onClick={() => {
          withSpan('meeting_documents.open_document', () => {}, {
            'document.type': document.document_type,
            'document.source': document.source,
          })
          viewer.openDocument({ url: document.document_url, label, caption })
        }}
        className={`${base} ${style}`}
      >
        <Icon className="h-4 w-4" />
        {label}
      </button>
    )
  }

  return (
    <a
      href={document.document_url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={() =>
        withSpan('meeting_documents.open_document', () => {}, {
          'document.type': document.document_type,
          'document.source': document.source,
        })
      }
      className={`${base} ${style}`}
    >
      <Icon className="h-4 w-4" />
      {label}
    </a>
  )
}

function MeetingRow({
  group,
  jurisdictionId,
}: {
  group: MeetingDocumentGroup
  jurisdictionId: string
}) {
  const caption = `${group.body_name ?? 'Meeting'} • ${formatDate(group.doc_date)}`
  return (
    <div className="flex flex-col gap-3 border-b border-gray-100 px-4 py-4 last:border-b-0 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="font-medium text-gray-900">
          {group.body_name || 'Meeting'}
        </p>
        <p className="text-sm text-gray-500">{formatDate(group.doc_date)}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {group.documents.map((doc, idx) => (
          <DocumentChip
            key={`${doc.document_type}-${idx}`}
            document={doc}
            caption={caption}
          />
        ))}
        {/* Only meetings matched to an AI summary can be compared. */}
        {group.event_meeting_id && (
          <Link
            to={`/jurisdiction/${encodeURIComponent(jurisdictionId)}/meetings/${encodeURIComponent(group.event_meeting_id)}/compare`}
            className="inline-flex items-center gap-1.5 rounded-md border border-[#1d6b5f] bg-[#1d6b5f]/5 px-3 py-1.5 text-sm font-medium text-[#1d6b5f] transition-colors hover:bg-[#1d6b5f]/10"
          >
            <ArrowsRightLeftIcon className="h-4 w-4" />
            Compare with summary
          </Link>
        )}
      </div>
    </div>
  )
}

function MeetingDocumentsInner({ jurisdictionId }: { jurisdictionId: string }) {
  const { data, isLoading, isError } = useQuery<MeetingDocumentsResponse>({
    queryKey: ['meeting-documents', jurisdictionId],
    queryFn: async () => {
      return withSpan(
        'meeting_documents.load',
        async () => {
          const response = await api.get<MeetingDocumentsResponse>(
            `/jurisdiction/${encodeURIComponent(jurisdictionId)}/meeting-documents`,
          )
          return response.data
        },
        { 'jurisdiction.id': jurisdictionId },
      )
    },
    enabled: Boolean(jurisdictionId),
  })

  // Group meetings by year (API already sorts newest-first). Preserve that order
  // both for the year headings and the meetings within each year.
  const grouped = useMemo(() => {
    const years: { year: string; meetings: MeetingDocumentGroup[] }[] = []
    const index = new Map<string, MeetingDocumentGroup[]>()
    for (const meeting of data?.meetings ?? []) {
      const year = yearOf(meeting.doc_date)
      let bucket = index.get(year)
      if (!bucket) {
        bucket = []
        index.set(year, bucket)
        years.push({ year, meetings: bucket })
      }
      bucket.push(meeting)
    }
    return years
  }, [data])

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-5xl px-6 py-8">
        {/* Header */}
        <div className="mb-6">
          <Link
            to="/jurisdictions"
            className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-gray-700"
          >
            <ArrowLeftIcon className="h-4 w-4" />
            Back to jurisdictions
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">Meeting Documents</h1>
          <p className="mt-1 text-gray-600">
            {data?.jurisdiction_name || jurisdictionId}
          </p>
          {data && (
            <p className="mt-2 text-sm font-medium text-gray-500">
              {data.meeting_count.toLocaleString()} meeting
              {data.meeting_count === 1 ? '' : 's'} ·{' '}
              {data.document_count.toLocaleString()} document
              {data.document_count === 1 ? '' : 's'}
            </p>
          )}
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="rounded-lg border border-gray-200 bg-white p-12 text-center">
            <div className="mx-auto mb-4 inline-block h-10 w-10 animate-spin rounded-full border-b-2 border-[#1d6b5f]" />
            <p className="text-gray-600">Loading meeting documents…</p>
          </div>
        )}

        {/* Error */}
        {isError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
            <p className="text-red-600">
              Couldn’t load meeting documents. Please try again.
            </p>
          </div>
        )}

        {/* Empty */}
        {!isLoading && !isError && (data?.meetings?.length ?? 0) === 0 && (
          <div className="rounded-lg border border-gray-200 bg-white p-12 text-center">
            <DocumentTextIcon className="mx-auto mb-4 h-12 w-12 text-gray-300" />
            <p className="text-gray-600">
              No meeting documents on file for this jurisdiction.
            </p>
          </div>
        )}

        {/* Grouped results */}
        {!isLoading && !isError && grouped.length > 0 && (
          <div className="space-y-8">
            {grouped.map(({ year, meetings }) => (
              <section key={year}>
                <div className="mb-3 flex items-baseline gap-3">
                  <h2 className="text-xl font-bold text-gray-900">{year}</h2>
                  <span className="text-sm text-gray-500">
                    {meetings.length} meeting{meetings.length === 1 ? '' : 's'}
                  </span>
                </div>
                <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
                  {meetings.map((group, idx) => (
                    <MeetingRow
                      key={`${group.doc_date}-${group.body_name ?? idx}`}
                      group={group}
                      jurisdictionId={jurisdictionId}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function MeetingDocuments() {
  const { jurisdictionId } = useParams<{ jurisdictionId: string }>()

  if (!jurisdictionId) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="mx-auto max-w-5xl px-6 py-12">
          <div className="rounded-lg border border-gray-200 bg-white p-12 text-center text-gray-600">
            No jurisdiction specified.
          </div>
        </div>
      </div>
    )
  }

  // Provider mounted here so the inline document viewer popout is available to the
  // chips on this page (same pattern as DecisionDetail).
  return (
    <DocumentViewerProvider>
      <MeetingDocumentsInner jurisdictionId={jurisdictionId} />
    </DocumentViewerProvider>
  )
}
