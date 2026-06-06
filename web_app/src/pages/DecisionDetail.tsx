import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import MeetingPlayer from '../components/MeetingPlayer'
import {
  ArrowLeftIcon,
  ScaleIcon,
  MapPinIcon,
  ChartBarIcon,
  SparklesIcon,
  UsersIcon,
  CalendarIcon,
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

// Frame analysis ("Where they disagreed"). competing_views is a stable AI shape:
//   { dominant_view, counter_views: [...] } where each view is
//   { view_label, problem_diagnosis, causal_story, proposed_remedy }.
// Render it as a narrative — the side's stance, then the worry / why / the ask —
// instead of a raw key/value dump. Falls back to the generic JsonValue for any
// unexpected shape so we never render an empty section.
const VIEW_SUBFIELDS: { key: string; label: string; hint: string; emphasize?: boolean }[] = [
  { key: 'problem_diagnosis', label: 'The worry', hint: "what's the concern?" },
  { key: 'causal_story', label: 'Why', hint: "what's behind it?" },
  { key: 'proposed_remedy', label: 'What they want', hint: 'the proposed fix', emphasize: true },
]

// Serif stack matching the homepage "story" typography (Newsreader → Georgia).
const CV_SERIF = { fontFamily: "'Newsreader', Georgia, 'Times New Roman', serif" } as const

function ViewColumn({
  side,
  view,
}: {
  side: 'prevailing' | 'other'
  view: Record<string, unknown>
}) {
  const isPrev = side === 'prevailing'
  const accent = isPrev ? '#1d6b5f' : '#e0603a'
  const tint = isPrev ? '#e7f2ef' : '#fdeee7'
  const kicker = isPrev ? 'THE PREVAILING VIEW' : 'THE OTHER SIDE'
  const label = typeof view?.view_label === 'string' ? view.view_label : null

  const rows = VIEW_SUBFIELDS.map(({ key, label: l, hint, emphasize }) => {
    const v = view?.[key]
    if (typeof v !== 'string' || !v.trim()) return null
    return (
      <div key={key} className="mt-5 first:mt-0">
        <div className="text-[13px] font-semibold text-[#16201d]">
          {l} <span className="font-normal text-[#9bb8b8]">· {hint}</span>
        </div>
        <p
          className={`mt-1.5 whitespace-pre-line text-[14px] leading-relaxed ${
            emphasize ? 'font-semibold text-[#16201d]' : 'text-[#56635e]'
          }`}
        >
          {v}
        </p>
      </div>
    )
  }).filter(Boolean)

  if (!label && rows.length === 0) return <JsonValue value={view} />

  return (
    <div>
      <span
        className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11.5px] font-bold tracking-wide"
        style={{ background: tint, color: accent }}
      >
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: accent }} />
        {kicker}
      </span>
      {label && (
        <h3 className="mt-3 text-[22px] font-semibold leading-tight text-[#16201d]" style={CV_SERIF}>
          {label}
        </h3>
      )}
      {rows.length > 0 && <div className="mt-3">{rows}</div>}
    </div>
  )
}

function CompetingViews({ data }: { data: unknown }) {
  const fallback = (value: unknown) => (
    <Section title="Where they disagreed" icon={<UsersIcon className="h-5 w-5" />}>
      <JsonValue value={value} />
    </Section>
  )
  if (!data || typeof data !== 'object') return fallback(data)
  const cv = data as Record<string, unknown>
  const dominant =
    cv.dominant_view && typeof cv.dominant_view === 'object'
      ? (cv.dominant_view as Record<string, unknown>)
      : null
  const counters = Array.isArray(cv.counter_views)
    ? (cv.counter_views.filter((c) => c && typeof c === 'object') as Record<string, unknown>[])
    : []
  // Optional editorial lead-in; only shown if the extraction supplies one.
  const debate =
    typeof cv.central_question === 'string'
      ? cv.central_question
      : typeof cv.debate === 'string'
        ? cv.debate
        : null

  // Recognized neither side -> generic fallback, so we never drop content.
  if (!dominant && counters.length === 0) return fallback(data)

  // Left column = the prevailing view (or the first stated view if there's no
  // explicit dominant); remaining views stack on the right as "the other side".
  const leftView = dominant ?? counters[0]
  const rightViews = dominant ? counters : counters.slice(1)

  return (
    <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
      <div className="text-[12px] font-bold uppercase tracking-[0.12em] text-[#1d6b5f]">
        Where they disagreed
      </div>

      {debate && (
        <div className="mt-4">
          <div className="text-[13px] text-[#8a958f]">The debate</div>
          <p className="mt-1 whitespace-pre-line text-[22px] leading-snug text-[#16201d]" style={CV_SERIF}>
            {debate}
          </p>
        </div>
      )}

      <div className="my-5 border-t border-[#e1ebe7]" />

      <div className="grid gap-7 md:grid-cols-2 md:gap-0">
        <div className="md:pr-7">
          <ViewColumn side={dominant ? 'prevailing' : 'other'} view={leftView} />
        </div>
        {rightViews.length > 0 && (
          <div className="space-y-8 border-t border-[#e1ebe7] pt-7 md:border-l md:border-t-0 md:pl-7 md:pt-0">
            {rightViews.map((c, i) => (
              <ViewColumn key={i} side="other" view={c} />
            ))}
          </div>
        )}
      </div>

      <div className="mt-6 flex items-center justify-between gap-3 border-t border-[#e1ebe7] pt-3 text-[12.5px]">
        <span className="flex items-center gap-1.5 text-[#8a958f]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <path d="M4 6h16M4 12h16M4 18h10" strokeLinecap="round" />
          </svg>
          Summarized from the meeting transcript
        </span>
        <Link to="/documents" className="shrink-0 font-medium text-[#1d6b5f] hover:underline">
          Read the discussion →
        </Link>
      </div>
    </div>
  )
}

// "Key Takeaways" (smart_brevity). Render the AI fields as an editorial brief:
// the lead in serif, then labelled sections, with `by_the_numbers` (a
// semicolon-joined string) parsed into stat chips (leading figure + caption).
const SB_NUMBER_RE =
  /^([$]?\d[\d.,]*(?:\s*[-–/]\s*\d[\d.,]*)?\s*(?:%|acres?|units?|lots?|days?|weeks?|months?|years?|hours?|hrs?|jobs?|votes?|miles?|mi)?)\s+(.+)$/i

function parseByTheNumbers(s: string | null): { value: string | null; label: string }[] {
  if (!s) return []
  return s
    .split(/;\s*/)
    .map((c) => c.trim().replace(/\.$/, ''))
    .filter(Boolean)
    .map((clause) => {
      const m = clause.match(SB_NUMBER_RE)
      return m ? { value: m[1].trim(), label: m[2].trim() } : { value: null, label: clause }
    })
}

function SBSection({ label, body }: { label: string; body: string }) {
  return (
    <div className="mt-5 first:mt-0">
      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-[#8a958f]">
        {label}
      </div>
      <p className="whitespace-pre-line text-[15px] leading-relaxed text-[#56635e]">{body}</p>
    </div>
  )
}

function SmartBrevityBody({ sb }: { sb: Record<string, unknown> }) {
  const str = (k: string) =>
    typeof sb[k] === 'string' && (sb[k] as string).trim() ? (sb[k] as string).trim() : null
  const lead = str('one_big_thing')
  const numbers = parseByTheNumbers(str('by_the_numbers'))
  const sections: [string, string | null][] = [
    ['Why it matters', str('why_it_matters')],
    ['The big picture', str('big_picture')],
    ['The case for', str('for_it_summary')],
    ['The case against', str('against_it_summary')],
    ["What's next", str('whats_next')],
  ]
  const [why, big, ...restSections] = sections

  // Unexpected/empty shape -> defer to the generic renderer so nothing is dropped.
  if (!lead && !numbers.length && sections.every(([, v]) => !v)) {
    return <JsonValue value={sb} />
  }

  return (
    <div>
      {lead && (
        <p className="mb-1 text-[24px] font-semibold leading-snug text-[#16201d]" style={CV_SERIF}>
          {lead}
        </p>
      )}
      {why[1] && <SBSection label={why[0]} body={why[1]} />}
      {numbers.length > 0 && (
        <div className="mt-5">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-[#8a958f]">
            By the numbers
          </div>
          <div className="flex flex-wrap gap-2.5">
            {numbers.map((it, i) => (
              <div key={i} className="flex items-baseline gap-2 rounded-xl bg-[#f3f7f6] px-3.5 py-2.5">
                {it.value && (
                  <span className="text-[20px] font-semibold leading-none text-[#16201d]" style={CV_SERIF}>
                    {it.value}
                  </span>
                )}
                <span className="max-w-[230px] text-[13px] leading-snug text-[#56635e]">{it.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {big[1] && <SBSection label={big[0]} body={big[1]} />}
      {restSections.map(([label, body]) => (body ? <SBSection key={label} label={label} body={body} /> : null))}
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
          </Section>
        )}

        {/* Meeting recording + clickable transcript */}
        {decision.meeting_video_id && (
          <MeetingPlayer
            videoId={decision.meeting_video_id}
            caption={[decision.meeting_name, decision.meeting_date
              ? new Date(decision.meeting_date).toLocaleDateString()
              : null]
              .filter(Boolean)
              .join(' • ') || undefined}
            targetText={[decision.headline, decision.decision_statement]
              .filter(Boolean)
              .join('. ') || undefined}
          />
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
          <Section title="Key Takeaways" icon={<SparklesIcon className="h-5 w-5 text-[#1d6b5f]" />}>
            <SmartBrevityBody sb={decision.smart_brevity as Record<string, unknown>} />
          </Section>
        )}

        {/* Frame analysis: where the sides disagreed (renders its own card) */}
        {!isEmpty(decision.competing_views) && (
          <CompetingViews data={decision.competing_views} />
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
