import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import {
  ArrowLeftIcon,
  ScaleIcon,
  MapPinIcon,
  ChartBarIcon,
  SparklesIcon,
  UsersIcon,
  CalendarIcon,
  VideoCameraIcon,
} from '@heroicons/react/24/outline'

interface DecisionDetail {
  event_decision_id: string
  headline?: string | null
  decision_statement?: string | null
  outcome?: string | null
  primary_theme?: string | null
  vote_tally?: Record<string, number> | null
  human_element?: unknown
  competing_views?: unknown
  smart_brevity?: unknown
  legislation_refs?: unknown
  financial_item_refs?: unknown
  place_refs?: unknown
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

// snake_case / camelCase JSON key -> human label
function humanizeKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined || value === '') return true
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') return Object.keys(value as object).length === 0
  return false
}

// Stable reading order for the AI JSONB payloads. Postgres returns JSONB keys in
// storage order, not schema order, so without this `one_big_thing` can render
// after `whats_next`. Known keys sort by this list; unknown keys keep their
// original order, appended after.
const KEY_ORDER = [
  // smart_brevity
  'one_big_thing',
  'why_it_matters',
  'by_the_numbers',
  'big_picture',
  'for_it_summary',
  'against_it_summary',
  'whats_next',
  // competing_views
  'dominant_view',
  'counter_views',
  'view_label',
  'problem_diagnosis',
  'causal_story',
  'proposed_remedy',
  // human_element
  'emotional_tone',
  'supporters',
  'opponents',
  'personal_stories',
  'humor_and_light_moments',
  'intensity',
  'primary_emotions',
  'plain_summary',
  'story_headline',
  'story_detail',
  'why_it_mattered_to_the_decision',
  'speaker_id',
  'summary',
  'tone',
]

function orderedEntries(obj: Record<string, unknown>): [string, unknown][] {
  const rank = (k: string) => {
    const i = KEY_ORDER.indexOf(k)
    return i === -1 ? KEY_ORDER.length : i
  }
  return Object.entries(obj)
    .filter(([, v]) => !isEmpty(v))
    .map((entry, idx) => [entry, idx] as const)
    .sort(([a, ai], [b, bi]) => rank(a[0]) - rank(b[0]) || ai - bi)
    .map(([entry]) => entry)
}

// Generic, defensive renderer: the AI JSONB payloads vary in shape, so render
// strings as paragraphs, numbers/booleans inline, arrays as lists, and objects
// as labeled nested sections — never crash on an unexpected structure.
function JsonValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (isEmpty(value)) return null

  if (typeof value === 'string') {
    return <p className="text-sm text-gray-700 whitespace-pre-line">{value}</p>
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return <span className="text-sm text-gray-900 font-medium">{String(value)}</span>
  }
  if (Array.isArray(value)) {
    return (
      <ul className="list-disc list-inside space-y-1">
        {value.map((item, idx) => (
          <li key={idx} className="text-sm text-gray-700">
            <JsonValue value={item} depth={depth + 1} />
          </li>
        ))}
      </ul>
    )
  }
  // object
  return (
    <div className={depth > 0 ? 'space-y-2 pl-3 border-l border-gray-100' : 'space-y-3'}>
      {orderedEntries(value as Record<string, unknown>).map(([k, v]) => (
        <div key={k}>
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">
            {humanizeKey(k)}
          </div>
          <JsonValue value={v} depth={depth + 1} />
        </div>
      ))}
    </div>
  )
}

function outcomeColor(outcome?: string | null): string {
  const o = (outcome || '').toLowerCase()
  if (/(approv|pass|adopt|grant)/.test(o)) return 'bg-green-100 text-green-800'
  if (/(defer|table|postpon|continu|hold)/.test(o)) return 'bg-yellow-100 text-yellow-800'
  if (/(den|reject|fail|veto|withdraw)/.test(o)) return 'bg-red-100 text-red-800'
  return 'bg-gray-100 text-gray-800'
}

function Section({
  title,
  icon,
  children,
}: {
  title: string
  icon?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
      <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
        {icon}
        {title}
      </h2>
      {children}
    </div>
  )
}

export default function DecisionDetail() {
  const { id } = useParams<{ id: string }>()

  const { data: decision, isLoading, error } = useQuery<DecisionDetail>({
    queryKey: ['decision', id],
    queryFn: async () => {
      const response = await api.get(`/decision/${id}`)
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
              <p className="text-gray-600">Loading decision details...</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error || !decision) {
    const errorMessage =
      (error as any)?.response?.data?.detail ||
      (error as any)?.message ||
      'Unable to load decision details'
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center">
            <div className="text-red-600 text-5xl mb-4">⚠️</div>
            <h3 className="text-lg font-semibold text-red-900 mb-2">Decision not found</h3>
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

  const location = [decision.jurisdiction_name, decision.state].filter(Boolean).join(', ')
  const voteEntries = decision.vote_tally
    ? Object.entries(decision.vote_tally).filter(([, v]) => typeof v === 'number')
    : []

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
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium bg-amber-100 text-amber-800">
              <ScaleIcon className="h-4 w-4" />
              Policy Decision
            </span>
            {decision.outcome && (
              <span
                className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${outcomeColor(
                  decision.outcome,
                )}`}
              >
                {decision.outcome}
              </span>
            )}
            {decision.primary_theme && (
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
                {decision.primary_theme}
              </span>
            )}
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            {decision.headline || 'Untitled Decision'}
          </h1>
          {location && (
            <div className="flex items-center gap-1 text-sm text-gray-600">
              <MapPinIcon className="h-4 w-4" />
              <span>{location}</span>
            </div>
          )}
        </div>

        {/* Meeting context */}
        {(decision.meeting_name || decision.meeting_date) && (
          <Section title="Meeting" icon={<CalendarIcon className="h-5 w-5" />}>
            <div className="text-sm text-gray-700">
              {decision.meeting_name && <span className="font-medium">{decision.meeting_name}</span>}
              {decision.meeting_name && decision.meeting_date && (
                <span className="text-gray-400"> • </span>
              )}
              {decision.meeting_date && (
                <span>{new Date(decision.meeting_date).toLocaleDateString()}</span>
              )}
            </div>
            {decision.meeting_video_id && (
              <a
                href={`https://www.youtube.com/watch?v=${decision.meeting_video_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 hover:underline"
              >
                <VideoCameraIcon className="h-4 w-4" />
                Watch meeting recording →
              </a>
            )}
          </Section>
        )}

        {/* Decision Statement */}
        {decision.decision_statement && (
          <Section title="Decision">
            <p className="text-sm text-gray-700 whitespace-pre-line">
              {decision.decision_statement}
            </p>
          </Section>
        )}

        {/* Vote Tally */}
        {voteEntries.length > 0 && (
          <Section title="Vote Tally" icon={<ChartBarIcon className="h-5 w-5" />}>
            <div className="flex flex-wrap gap-3">
              {voteEntries.map(([label, count]) => (
                <div
                  key={label}
                  className="flex items-baseline gap-2 px-4 py-2 rounded-lg bg-gray-50 border border-gray-100"
                >
                  <span className="text-2xl font-bold text-gray-900">{count}</span>
                  <span className="text-sm text-gray-600 capitalize">{label}</span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Key Takeaways (smart_brevity) */}
        {!isEmpty(decision.smart_brevity) && (
          <Section title="Key Takeaways" icon={<SparklesIcon className="h-5 w-5" />}>
            {(() => {
              const sb = decision.smart_brevity as Record<string, unknown>
              const lead = typeof sb?.one_big_thing === 'string' ? sb.one_big_thing : null
              const rest = lead
                ? Object.fromEntries(
                    Object.entries(sb).filter(([k]) => k !== 'one_big_thing'),
                  )
                : sb
              return (
                <>
                  {lead && (
                    <p className="text-base font-semibold text-gray-900 mb-4 leading-snug">
                      {lead}
                    </p>
                  )}
                  <JsonValue value={rest} />
                </>
              )
            })()}
          </Section>
        )}

        {/* Competing Views */}
        {!isEmpty(decision.competing_views) && (
          <Section title="Competing Views" icon={<UsersIcon className="h-5 w-5" />}>
            <JsonValue value={decision.competing_views} />
          </Section>
        )}

        {/* Human Element */}
        {!isEmpty(decision.human_element) && (
          <Section title="Human Element">
            <JsonValue value={decision.human_element} />
          </Section>
        )}

        {/* Provenance */}
        <div className="bg-white rounded-lg shadow-sm p-6 text-xs text-gray-500 space-y-1">
          {decision.source_ai_model && <div>Extracted by {decision.source_ai_model}</div>}
          {decision.extracted_at && (
            <div>Extracted {new Date(decision.extracted_at).toLocaleDateString()}</div>
          )}
          {decision.c1_event_id && <div>Event: {decision.c1_event_id}</div>}
        </div>
      </div>
    </div>
  )
}
