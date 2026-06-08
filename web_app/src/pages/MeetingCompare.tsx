import { useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  SparklesIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  LightBulbIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import api from '../lib/api'
import { withSpan } from '../instrumentation'
import DocumentViewer from '../components/DocumentViewer'

/**
 * MeetingCompare — read a meeting's AI summary side-by-side with the OFFICIAL
 * scraped agenda or minutes, and (on demand) highlight where they disagree.
 *
 * The AI summary is derived from the meeting VIDEO transcript; the agenda/minutes
 * are the official record, so the differences are genuine discrepancies. The page
 * shows the summary + exactly ONE document at a time (toggle Agenda/Minutes).
 *
 * Gap analysis is an explicit, billed AI call: clicking "Analyze gaps" POSTs to
 * /api/meeting/{id}/document-gaps. Results are cached server-side, so reloads are
 * free — already-analyzed documents render immediately from `cached_gaps`.
 */

interface GapItem {
  quote: string
  detail: string
}

interface GapAnalysis {
  status: 'ok' | 'no_document_text' | 'parse_error'
  omissions: GapItem[]
  possible_errors: GapItem[]
  interesting_gaps: GapItem[]
  overall: string
  model: string | null
}

interface ComparisonDecision {
  event_decision_id: string
  headline: string | null
  outcome: string | null
  decision_statement: string | null
  vote_tally: unknown | null
  primary_theme: string | null
}

interface ComparisonResponse {
  event_meeting_id: number
  body_name: string | null
  meeting_date: string | null
  jurisdiction_name: string | null
  summary: {
    meeting_summary: string | null
    agenda_summary: string | null
    decisions: ComparisonDecision[]
  }
  documents: Array<{ document_type: string; document_url: string }>
  cached_gaps: Record<string, GapAnalysis>
}

function typeLabel(documentType: string): string {
  if (!documentType) return 'Document'
  return documentType.charAt(0).toUpperCase() + documentType.slice(1)
}

function formatDate(docDate: string | null): string {
  if (!docDate) return ''
  const d = new Date(docDate)
  if (Number.isNaN(d.getTime())) return docDate
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

/** Compact, never-fabricated rendering of a vote tally object. Returns null if
 *  there's nothing real to show (the No-Fabricated-Data rule). */
function voteTallyText(tally: unknown): string | null {
  if (!tally || typeof tally !== 'object' || Array.isArray(tally)) return null
  const entries = Object.entries(tally as Record<string, unknown>).filter(
    ([, v]) => v !== null && v !== undefined && v !== '',
  )
  if (entries.length === 0) return null
  return entries.map(([k, v]) => `${k}: ${v}`).join(' · ')
}

/** One color-coded gap subsection (omissions / errors / interesting). */
function GapSection({
  title,
  items,
  tone,
  Icon,
}: {
  title: string
  items: GapItem[]
  tone: 'amber' | 'red' | 'teal'
  Icon: typeof ExclamationTriangleIcon
}) {
  const tones = {
    amber: {
      head: 'text-amber-800',
      border: 'border-amber-200',
      bar: 'border-amber-300',
    },
    red: {
      head: 'text-red-800',
      border: 'border-red-200',
      bar: 'border-red-300',
    },
    teal: {
      head: 'text-[#155448]',
      border: 'border-[#1d6b5f]/20',
      bar: 'border-[#1d6b5f]/40',
    },
  }[tone]

  return (
    <div className={`rounded-lg border ${tones.border} bg-white p-4`}>
      <h3 className={`mb-3 flex items-center gap-2 text-sm font-bold ${tones.head}`}>
        <Icon className="h-4 w-4" />
        {title}
        <span className="text-xs font-normal text-gray-400">({items.length})</span>
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-gray-400">None found.</p>
      ) : (
        <ul className="space-y-3">
          {items.map((item, idx) => (
            <li key={idx} className="text-sm">
              {item.quote && (
                <blockquote
                  className={`mb-1 border-l-2 ${tones.bar} pl-3 italic text-gray-600`}
                >
                  “{item.quote}”
                </blockquote>
              )}
              <p className="text-gray-800">{item.detail}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function GapResult({ gaps }: { gaps: GapAnalysis }) {
  if (gaps.status === 'no_document_text') {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-6 text-center text-sm text-gray-600">
        Couldn’t extract text from this document to compare it with the summary.
      </div>
    )
  }
  if (gaps.status === 'parse_error') {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-6 text-center text-sm text-gray-600">
        The analysis couldn’t be parsed — try re-analyzing.
      </div>
    )
  }
  return (
    <div className="space-y-4">
      {gaps.overall && (
        <p className="rounded-lg bg-gray-50 p-4 text-sm leading-relaxed text-gray-700">
          {gaps.overall}
        </p>
      )}
      <div className="grid gap-4 md:grid-cols-3">
        <GapSection
          title="Omissions"
          items={gaps.omissions}
          tone="amber"
          Icon={ExclamationTriangleIcon}
        />
        <GapSection
          title="Possible errors"
          items={gaps.possible_errors}
          tone="red"
          Icon={XCircleIcon}
        />
        <GapSection
          title="Interesting gaps"
          items={gaps.interesting_gaps}
          tone="teal"
          Icon={LightBulbIcon}
        />
      </div>
      {gaps.model && (
        <p className="text-right text-xs text-gray-400">Analyzed with {gaps.model}</p>
      )}
    </div>
  )
}

export default function MeetingCompare() {
  const { jurisdictionId, eventMeetingId } = useParams<{
    jurisdictionId: string
    eventMeetingId: string
  }>()

  const { data, isLoading, isError } = useQuery<ComparisonResponse>({
    queryKey: ['meeting-comparison', eventMeetingId],
    queryFn: async () => {
      return withSpan(
        'meeting_compare.load',
        async () => {
          const response = await api.get<ComparisonResponse>(
            `/meeting/${encodeURIComponent(eventMeetingId ?? '')}/comparison`,
          )
          return response.data
        },
        { 'meeting.event_meeting_id': eventMeetingId ?? '' },
      )
    },
    enabled: Boolean(eventMeetingId),
  })

  // Gap results keyed by document_url. Seeded from the server cache; extended as
  // the user runs new analyses.
  const [gapsByUrl, setGapsByUrl] = useState<Record<string, GapAnalysis>>({})
  const cachedGaps = data?.cached_gaps ?? {}

  // The available document types (deduped, agenda before minutes). One doc per
  // type is shown — the first of that type in the (already ordered) list.
  const docByType = useMemo(() => {
    const map = new Map<string, string>()
    for (const doc of data?.documents ?? []) {
      if (!map.has(doc.document_type)) map.set(doc.document_type, doc.document_url)
    }
    return map
  }, [data])

  const availableTypes = useMemo(() => Array.from(docByType.keys()), [docByType])
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const activeType =
    selectedType && docByType.has(selectedType)
      ? selectedType
      : docByType.has('minutes')
        ? 'minutes'
        : (availableTypes[0] ?? null)
  const activeUrl = activeType ? (docByType.get(activeType) ?? null) : null

  const gapsForActive = activeUrl
    ? (gapsByUrl[activeUrl] ?? cachedGaps[activeUrl] ?? null)
    : null

  const mutation = useMutation<GapAnalysis, Error, string>({
    mutationFn: async (documentUrl: string) => {
      return withSpan(
        'meeting_compare.analyze_gaps',
        async () => {
          const response = await api.post<GapAnalysis>(
            `/meeting/${encodeURIComponent(eventMeetingId ?? '')}/document-gaps`,
            { document_url: documentUrl },
          )
          return response.data
        },
        { 'meeting.event_meeting_id': eventMeetingId ?? '' },
      )
    },
    onSuccess: (result, documentUrl) => {
      setGapsByUrl((prev) => ({ ...prev, [documentUrl]: result }))
    },
  })

  const meetingDateLabel = formatDate(data?.meeting_date ?? null)

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-7xl px-6 py-8">
        {/* Header */}
        <div className="mb-6">
          <Link
            to={`/jurisdiction/${encodeURIComponent(jurisdictionId ?? '')}/meetings`}
            className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-gray-700"
          >
            <ArrowLeftIcon className="h-4 w-4" />
            Back to meeting documents
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">
            {data?.body_name || 'Meeting'}
            {meetingDateLabel && (
              <span className="ml-3 text-xl font-normal text-gray-400">
                {meetingDateLabel}
              </span>
            )}
          </h1>
          {data?.jurisdiction_name && (
            <p className="mt-1 text-gray-600">{data.jurisdiction_name}</p>
          )}
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="rounded-lg border border-gray-200 bg-white p-12 text-center">
            <div className="mx-auto mb-4 inline-block h-10 w-10 animate-spin rounded-full border-b-2 border-[#1d6b5f]" />
            <p className="text-gray-600">Loading comparison…</p>
          </div>
        )}

        {/* Error */}
        {isError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
            <p className="text-red-600">Couldn’t load this meeting. Please try again.</p>
          </div>
        )}

        {/* No documents to compare */}
        {!isLoading && !isError && availableTypes.length === 0 && (
          <div className="rounded-lg border border-gray-200 bg-white p-12 text-center text-gray-600">
            No agenda or minutes on file for this meeting to compare against.
          </div>
        )}

        {!isLoading && !isError && activeType && activeUrl && (
          <>
            {/* Document type toggle — summary + exactly one document at a time. */}
            <div className="mb-4 inline-flex rounded-lg border border-gray-200 bg-white p-1">
              {availableTypes.map((t) => {
                const active = t === activeType
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setSelectedType(t)}
                    className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                      active
                        ? 'bg-[#1d6b5f] text-white'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {typeLabel(t)}
                  </button>
                )
              })}
            </div>

            {/* Two-pane: document (left) ↔ AI summary (right). */}
            <div className="grid gap-6 lg:grid-cols-2">
              <DocumentViewer
                key={activeUrl}
                url={activeUrl}
                label={typeLabel(activeType)}
                caption={meetingDateLabel}
              />

              <div className="mb-6 rounded-lg bg-white p-6 shadow-sm">
                <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-gray-900">
                  <SparklesIcon className="h-5 w-5 text-[#1d6b5f]" />
                  AI Summary
                  <span className="text-sm font-normal text-gray-400">
                    from meeting recording
                  </span>
                </h2>

                {data?.summary.meeting_summary ? (
                  <p className="mb-4 whitespace-pre-line text-sm leading-relaxed text-gray-700">
                    {data.summary.meeting_summary}
                  </p>
                ) : (
                  <p className="mb-4 text-sm text-gray-400">No summary available.</p>
                )}

                {data?.summary.agenda_summary && (
                  <div className="mb-4">
                    <h3 className="mb-1 text-sm font-semibold text-gray-800">
                      Agenda overview
                    </h3>
                    <p className="whitespace-pre-line text-sm leading-relaxed text-gray-700">
                      {data.summary.agenda_summary}
                    </p>
                  </div>
                )}

                {data && data.summary.decisions.length > 0 && (
                  <div>
                    <h3 className="mb-2 text-sm font-semibold text-gray-800">
                      Decisions ({data.summary.decisions.length})
                    </h3>
                    <ul className="space-y-3">
                      {data.summary.decisions.map((d) => {
                        const votes = voteTallyText(d.vote_tally)
                        return (
                          <li
                            key={d.event_decision_id}
                            className="border-b border-gray-100 pb-3 last:border-b-0"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <p className="font-medium text-gray-900">
                                {d.headline || 'Decision'}
                              </p>
                              {d.outcome && (
                                <span className="shrink-0 rounded-full bg-[#1d6b5f]/10 px-2 py-0.5 text-xs font-medium text-[#155448]">
                                  {d.outcome}
                                </span>
                              )}
                            </div>
                            {d.decision_statement && (
                              <p className="mt-1 text-sm text-gray-600">
                                {d.decision_statement}
                              </p>
                            )}
                            {votes && (
                              <p className="mt-1 text-xs tabular-nums text-gray-500">
                                {votes}
                              </p>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                )}
              </div>
            </div>

            {/* Gap analysis */}
            <div className="mt-2">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-xl font-bold text-gray-900">
                  Gaps between the {typeLabel(activeType).toLowerCase()} and the summary
                </h2>
                {gapsForActive ? (
                  <button
                    type="button"
                    onClick={() => mutation.mutate(activeUrl)}
                    disabled={mutation.isPending}
                    className="inline-flex items-center gap-1.5 text-sm font-medium text-[#1d6b5f] hover:text-[#155448] disabled:opacity-50"
                  >
                    <ArrowPathIcon
                      className={`h-4 w-4 ${mutation.isPending ? 'animate-spin' : ''}`}
                    />
                    {mutation.isPending ? 'Analyzing…' : 'Re-analyze'}
                  </button>
                ) : null}
              </div>

              {mutation.isError && (
                <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
                  The analysis failed. Please try again.
                </div>
              )}

              {gapsForActive ? (
                <GapResult gaps={gapsForActive} />
              ) : (
                <div className="rounded-lg border border-dashed border-gray-300 bg-white p-8 text-center">
                  <SparklesIcon className="mx-auto mb-3 h-8 w-8 text-[#1d6b5f]" />
                  <button
                    type="button"
                    onClick={() => mutation.mutate(activeUrl)}
                    disabled={mutation.isPending}
                    className="inline-flex items-center gap-2 rounded-lg bg-[#1d6b5f] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#155448] disabled:opacity-50"
                  >
                    {mutation.isPending && (
                      <span className="h-4 w-4 animate-spin rounded-full border-b-2 border-white" />
                    )}
                    {mutation.isPending ? 'Analyzing…' : 'Analyze gaps'}
                  </button>
                  <p className="mt-2 text-xs text-gray-500">
                    Runs an AI comparison of this {typeLabel(activeType).toLowerCase()}{' '}
                    against the summary.
                  </p>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
