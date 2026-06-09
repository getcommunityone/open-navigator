import { useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  SparklesIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  MapPinIcon,
  DocumentTextIcon,
  BanknotesIcon,
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

interface Correction {
  quote: string
  ai_claim: string
  correction: string
}

interface DollarAmount {
  amount: string
  description: string
  quote: string
}

interface DecisionEnrichment {
  decision_ref: string
  addresses: string[]
  legislation: string[]
  dollar_amounts: DollarAmount[]
}

interface GapAnalysis {
  status: 'ok' | 'no_document_text' | 'parse_error'
  corrections: Correction[]
  corrected_summary: string
  decision_enrichments: DecisionEnrichment[]
  minutes_omissions: GapItem[]
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

/** "What the official record left out" — the editorially interesting bias signal. */
function OmissionsSection({ items, docType }: { items: GapItem[]; docType: string }) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50/40 p-4">
      <h3 className="mb-1 flex items-center gap-2 text-sm font-bold text-amber-800">
        <ExclamationTriangleIcon className="h-4 w-4" />
        What the official {docType} left out
        <span className="text-xs font-normal text-amber-700/70">({items.length})</span>
      </h3>
      <p className="mb-3 text-xs text-amber-700/80">
        Discussed in the meeting (per the recording) but absent from the official
        record — worth a closer look.
      </p>
      {items.length === 0 ? (
        <p className="text-sm text-gray-500">Nothing notable was left out.</p>
      ) : (
        <ul className="space-y-3">
          {items.map((item, idx) => (
            <li key={idx} className="text-sm">
              {item.quote && (
                <blockquote className="mb-1 border-l-2 border-amber-300 pl-3 italic text-gray-600">
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

/** Factual fixes the official record forced onto the AI recap. */
function CorrectionsSection({ items, docType }: { items: Correction[]; docType: string }) {
  if (items.length === 0) return null
  return (
    <div className="rounded-lg border border-[#1d6b5f]/20 bg-white p-4">
      <h3 className="mb-1 flex items-center gap-2 text-sm font-bold text-[#155448]">
        <XCircleIcon className="h-4 w-4" />
        AI facts corrected from the {docType}
        <span className="text-xs font-normal text-gray-400">({items.length})</span>
      </h3>
      <p className="mb-3 text-xs text-gray-500">
        The official {docType} is authoritative for these facts; the recap above
        reflects the corrected values.
      </p>
      <ul className="space-y-3">
        {items.map((c, idx) => (
          <li key={idx} className="text-sm">
            <p className="text-gray-800">
              <span className="text-red-600 line-through">{c.ai_claim}</span>{' '}
              <span aria-hidden>→</span>{' '}
              <span className="font-medium text-[#155448]">{c.correction}</span>
            </p>
            {c.quote && (
              <blockquote className="mt-1 border-l-2 border-[#1d6b5f]/40 pl-3 text-xs italic text-gray-500">
                “{c.quote}”
              </blockquote>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

function GapResult({ gaps, docType }: { gaps: GapAnalysis; docType: string }) {
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
      <OmissionsSection items={gaps.minutes_omissions} docType={docType} />
      <CorrectionsSection items={gaps.corrections} docType={docType} />
      {gaps.model && (
        <p className="text-right text-xs text-gray-400">Analyzed with {gaps.model}</p>
      )}
    </div>
  )
}

/** Exact detail pulled from the official document for one decision: addresses,
 *  related legislation, and dollar amounts/transactions. Renders nothing when the
 *  document added no detail for this decision. */
function DecisionDetailFromDoc({
  enrich,
  docType,
}: {
  enrich: DecisionEnrichment
  docType: string
}) {
  const hasAny =
    enrich.addresses.length > 0 ||
    enrich.legislation.length > 0 ||
    enrich.dollar_amounts.length > 0
  if (!hasAny) return null
  return (
    <div className="mt-2 rounded-md bg-[#1d6b5f]/5 px-3 py-2 text-xs text-gray-700">
      <p className="mb-1 font-semibold uppercase tracking-wide text-[#155448]">
        From the official {docType}
      </p>
      <div className="space-y-1">
        {enrich.addresses.length > 0 && (
          <p className="flex items-start gap-1.5">
            <MapPinIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#1d6b5f]" />
            <span>{enrich.addresses.join(' · ')}</span>
          </p>
        )}
        {enrich.legislation.length > 0 && (
          <p className="flex items-start gap-1.5">
            <DocumentTextIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#1d6b5f]" />
            <span>{enrich.legislation.join(' · ')}</span>
          </p>
        )}
        {enrich.dollar_amounts.length > 0 && (
          <div className="flex items-start gap-1.5">
            <BanknotesIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#1d6b5f]" />
            <ul className="space-y-0.5">
              {enrich.dollar_amounts.map((amt, i) => (
                <li key={i}>
                  <span className="font-semibold tabular-nums text-[#155448]">
                    {amt.amount}
                  </span>
                  {amt.description && <span> — {amt.description}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
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

  // When the active document's analysis produced a corrected summary, show that
  // (the recap with its facts fixed from the official record); else the original.
  const correctedSummary =
    gapsForActive?.status === 'ok' && gapsForActive.corrected_summary.trim()
      ? gapsForActive.corrected_summary
      : null

  // Per-decision enrichment (addresses / legislation / dollar amounts) pulled from
  // the official document, keyed by the decision id the model referenced.
  const enrichmentByDecision = useMemo(() => {
    const map = new Map<string, DecisionEnrichment>()
    for (const e of gapsForActive?.decision_enrichments ?? []) {
      if (e.decision_ref) map.set(e.decision_ref, e)
    }
    return map
  }, [gapsForActive])

  const activeDocType = activeType ?? 'document'

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
                <h2 className="mb-4 flex flex-wrap items-center gap-2 text-lg font-bold text-gray-900">
                  <SparklesIcon className="h-5 w-5 text-[#1d6b5f]" />
                  AI Summary
                  <span className="text-sm font-normal text-gray-400">
                    from meeting recording
                  </span>
                  {correctedSummary && (
                    <span className="rounded-full bg-[#1d6b5f]/10 px-2 py-0.5 text-xs font-medium text-[#155448]">
                      Corrected from {activeDocType}
                    </span>
                  )}
                </h2>

                {correctedSummary ?? data?.summary.meeting_summary ? (
                  <p className="mb-4 whitespace-pre-line text-sm leading-relaxed text-gray-700">
                    {correctedSummary ?? data?.summary.meeting_summary}
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
                        const enrich = enrichmentByDecision.get(d.event_decision_id)
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
                            {enrich && <DecisionDetailFromDoc enrich={enrich} docType={activeDocType} />}
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
                  Reconciling the {typeLabel(activeType).toLowerCase()} with the AI recap
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
                <GapResult gaps={gapsForActive} docType={activeDocType} />
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
                    {mutation.isPending ? 'Analyzing…' : 'Reconcile with the official record'}
                  </button>
                  <p className="mt-2 text-xs text-gray-500">
                    Runs an AI pass that fixes factual errors, enriches each decision
                    with addresses, legislation and dollar amounts from the{' '}
                    {typeLabel(activeType).toLowerCase()}, and flags what the official
                    record left out.
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
