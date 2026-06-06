import { useState } from 'react'
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import MeetingPlayer from '../components/MeetingPlayer'
import { MeetingVideoProvider, EvidenceLink, WatchRecordingLink } from '../components/MeetingVideoContext'
import {
  ArrowLeftIcon,
  MapPinIcon,
  ChartBarIcon,
  SparklesIcon,
  UsersIcon,
  CalendarIcon,
  FilmIcon,
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

// Outline-pill colors for the hero status chip (uppercase mono treatment).
function outcomePill(outcome?: string | null): string {
  const o = (outcome || '').toLowerCase()
  if (/(approv|pass|adopt|grant)/.test(o)) return 'border-emerald-300 bg-emerald-50 text-emerald-700'
  if (/(defer|table|postpon|continu|hold)/.test(o)) return 'border-amber-300 bg-amber-50 text-amber-700'
  if (/(den|reject|fail|veto|withdraw)/.test(o)) return 'border-rose-300 bg-rose-50 text-rose-700'
  return 'border-slate-300 bg-slate-50 text-slate-600'
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
// Body stack matching the homepage (DM Sans) so the detail page reads as the
// same product, not a stock-Tailwind screen.
const CV_FONT = { fontFamily: "'DM Sans', sans-serif" } as const

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
  // Who argued this side (populated by the extraction's `held_by` person_ids).
  const heldBy = Array.isArray(view?.held_by)
    ? (view.held_by as unknown[])
        .filter((p): p is string => typeof p === 'string' && p.trim().length > 0)
        .map(parseSpeaker)
    : []

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
          <EvidenceLink text={v} />
        </p>
      </div>
    )
  }).filter(Boolean)

  if (!label && rows.length === 0) return <JsonValue value={view} />

  return (
    <div
      className="h-full rounded-xl border border-[#e1ebe7] p-4 sm:p-5"
      style={{ borderLeftWidth: 4, borderLeftColor: accent, background: isPrev ? '#f6faf9' : '#fef8f5' }}
    >
      <span
        className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11.5px] font-bold tracking-wide"
        style={{ background: tint, color: accent }}
      >
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: accent }} />
        {kicker}
      </span>
      {label && (
        <h3 className="mt-3 text-[19px] font-semibold leading-tight text-[#16201d] sm:text-[22px]" style={CV_SERIF}>
          {label}
        </h3>
      )}
      {heldBy.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-[#9bb8b8]">Argued by</span>
          {heldBy.map((sp, i) => (
            <span key={i} className="inline-flex items-center gap-1.5">
              <Avatar speaker={sp} size={26} />
              <span className="text-[12.5px] font-medium text-[#16201d]">{sp.name}</span>
            </span>
          ))}
        </div>
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

      <div className="grid items-stretch gap-4 md:grid-cols-2">
        <ViewColumn side={dominant ? 'prevailing' : 'other'} view={leftView} />
        {rightViews.length > 0 && (
          <div className="space-y-4">
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

// ---------------------------------------------------------------------------
// Voices in the room (human_element) — puts faces to the testimony.
//
// The AI `person_id`/`speaker_id` are descriptive slugs
// (e.g. "chuck_tracy_resident_baldwin_01003"), NOT MDM person ids, so no
// contact photo joins. We derive a display name + role + a deterministic
// initials avatar from the slug — the honest universal fallback that still
// works when a real photo isn't available.
// ---------------------------------------------------------------------------
const AVATAR_COLORS = [
  { bg: '#e7f2ef', fg: '#1d6b5f' },
  { bg: '#fdeee7', fg: '#c0432a' },
  { bg: '#eaf1f8', fg: '#2f6fb0' },
  { bg: '#efebfb', fg: '#6b5bd2' },
  { bg: '#fbf3e2', fg: '#9a6b12' },
  { bg: '#fdeef5', fg: '#b03a78' },
]

const ROLE_WORDS = new Set([
  'resident', 'residents', 'applicant', 'representative', 'rep', 'owner', 'official', 'officials',
  'council', 'councilmember', 'member', 'mayor', 'attorney', 'director', 'chair', 'chairman',
  'chairwoman', 'chairperson', 'president', 'vice', 'spokesperson', 'staff', 'citizen', 'speaker',
  'public', 'commissioner', 'commission', 'developer', 'petitioner', 'neighbor', 'business',
  'manager', 'planner', 'engineer', 'consultant', 'pastor', 'professor', 'teacher', 'student',
  'parent', 'advocate', 'opponent', 'supporter', 'clerk', 'administrator', 'superintendent',
  'sheriff', 'trustee', 'board', 'deputy', 'assistant',
])

interface Speaker {
  name: string
  role: string
  initials: string
  color: { bg: string; fg: string }
}

function parseSpeaker(id: string): Speaker {
  const toks = id.split('_').filter(Boolean)
  while (toks.length && /^\d+$/.test(toks[toks.length - 1])) toks.pop() // drop trailing FIPS
  const nameToks = toks.slice(0, 2)
  const lowerName = nameToks.map((t) => t.toLowerCase())
  const cap = (t: string) => t.charAt(0).toUpperCase() + t.slice(1)
  const roleToks = [
    ...new Set(
      toks
        .slice(nameToks.length)
        .map((t) => t.toLowerCase())
        .filter((t) => ROLE_WORDS.has(t) && !lowerName.includes(t)),
    ),
  ]
  const name = nameToks.map(cap).join(' ') || 'Speaker'
  const role = roleToks.map(cap).join(' ')
  const initials = nameToks.map((t) => t.charAt(0).toUpperCase()).join('').slice(0, 2) || '?'
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0
  return { name, role, initials, color: AVATAR_COLORS[h % AVATAR_COLORS.length] }
}

function Avatar({ speaker, size = 40 }: { speaker: Speaker; size?: number }) {
  return (
    <span
      className="flex shrink-0 items-center justify-center rounded-full font-bold"
      style={{
        width: size,
        height: size,
        background: speaker.color.bg,
        color: speaker.color.fg,
        fontSize: Math.round(size * 0.36),
      }}
      title={speaker.name}
      aria-hidden
    >
      {speaker.initials}
    </span>
  )
}

interface Story {
  person_id?: string
  story_headline?: string
  story_detail?: string
  why_it_mattered_to_the_decision?: string
}

// One side of emotional_tone: { intensity, plain_summary, primary_emotions[] }.
function ToneSide({ label, accent, side }: { label: string; accent: string; side: Record<string, unknown> }) {
  const intensity = typeof side.intensity === 'string' ? side.intensity : null
  const summary = typeof side.plain_summary === 'string' ? side.plain_summary : null
  const emotions = Array.isArray(side.primary_emotions)
    ? (side.primary_emotions.filter((e) => typeof e === 'string') as string[])
    : []
  if (!intensity && !summary && emotions.length === 0) return null
  return (
    <div className="rounded-xl border border-[#e1ebe7] p-4" style={{ borderLeftWidth: 4, borderLeftColor: accent }}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-bold uppercase tracking-wide" style={{ color: accent }}>
          {label}
        </span>
        {intensity && <span className="text-[11.5px] font-medium text-[#8a958f]">Intensity: {intensity}</span>}
      </div>
      {emotions.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {emotions.map((e) => (
            <span key={e} className="rounded-full bg-[#f3f7f6] px-2 py-0.5 text-[11.5px] text-[#56635e]">
              {e}
            </span>
          ))}
        </div>
      )}
      {summary && <p className="mt-2 text-[13px] leading-relaxed text-[#56635e]">{summary}</p>}
    </div>
  )
}

function HumanElement({ data }: { data: unknown }) {
  if (!data || typeof data !== 'object') return null
  const he = data as Record<string, unknown>
  const stories = Array.isArray(he.personal_stories)
    ? (he.personal_stories.filter((s) => s && typeof s === 'object') as Story[])
    : []
  const tone = he.emotional_tone && typeof he.emotional_tone === 'object' ? (he.emotional_tone as Record<string, unknown>) : null
  const sup = tone && tone.supporters && typeof tone.supporters === 'object' ? (tone.supporters as Record<string, unknown>) : null
  const opp = tone && tone.opponents && typeof tone.opponents === 'object' ? (tone.opponents as Record<string, unknown>) : null
  const humor = Array.isArray(he.humor_and_light_moments)
    ? (he.humor_and_light_moments.filter((h) => h && typeof h === 'object') as Record<string, unknown>[])
    : []

  // Recognized nothing structured -> generic fallback so content is never dropped.
  if (stories.length === 0 && !sup && !opp && humor.length === 0) {
    return (
      <Section title="Human Element" icon={<UsersIcon className="h-5 w-5" />}>
        <JsonValue value={data} />
      </Section>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
      <div className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-[0.12em] text-[#1d6b5f]">
        <UsersIcon className="h-4 w-4" /> Voices in the room
      </div>

      {stories.length > 0 && (
        <ul className="mt-4 space-y-5">
          {stories.map((s, i) => {
            const sp = parseSpeaker(s.person_id || 'speaker')
            return (
              <li key={i} className="flex gap-3">
                <Avatar speaker={sp} />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-[15px] font-semibold text-[#16201d]">{sp.name}</span>
                    {sp.role && <span className="text-[12px] text-[#8a958f]">{sp.role}</span>}
                  </div>
                  {s.story_headline && <div className="mt-0.5 text-[13.5px] font-medium text-[#16201d]">{s.story_headline}</div>}
                  {s.story_detail && <p className="mt-1 text-[13.5px] leading-relaxed text-[#56635e]">{s.story_detail}</p>}
                  {s.why_it_mattered_to_the_decision && (
                    <p className="mt-1.5 border-l-2 border-[#e1ebe7] pl-3 text-[12.5px] italic leading-relaxed text-[#8a958f]">
                      Why it mattered: {s.why_it_mattered_to_the_decision}
                    </p>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {(sup || opp) && (
        <div className={stories.length > 0 ? 'mt-6 border-t border-[#e1ebe7] pt-5' : 'mt-4'}>
          <div className="text-[12.5px] font-semibold text-[#16201d]">How the room felt</div>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            {sup && <ToneSide label="Supporters" accent="#1d6b5f" side={sup} />}
            {opp && <ToneSide label="Opponents" accent="#e0603a" side={opp} />}
          </div>
        </div>
      )}

      {humor.length > 0 && (
        <div className="mt-6 border-t border-[#e1ebe7] pt-4">
          <div className="text-[12.5px] font-semibold text-[#16201d]">Lighter moments</div>
          <ul className="mt-2 space-y-2">
            {humor.map((h, i) => {
              const sp = typeof h.speaker_id === 'string' ? parseSpeaker(h.speaker_id) : null
              return (
                <li key={i} className="flex items-start gap-2 text-[13px] leading-relaxed text-[#56635e]">
                  <span aria-hidden>😄</span>
                  <span>
                    {typeof h.summary === 'string' ? h.summary : ''}
                    {sp && <span className="text-[#8a958f]"> — {sp.name}</span>}
                  </span>
                </li>
              )
            })}
          </ul>
        </div>
      )}
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

// The committee/council decision itself, styled to sit inline within Key
// Takeaways directly under "Why it matters" (neutral slate accent so it reads
// as the factual outcome, distinct from the green "why it matters" callout).
function DecisionBlock({ statement }: { statement: string }) {
  return (
    <div className="mt-4 rounded-xl border-l-4 border-[#94a3a0] bg-[#f3f6f5] px-4 py-3.5">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#56635e]">
        The decision
      </div>
      <p className="whitespace-pre-line text-[15px] leading-relaxed text-[#16201d]">{statement}</p>
    </div>
  )
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

function SmartBrevityBody({
  sb,
  afterWhyItMatters,
}: {
  sb: Record<string, unknown>
  afterWhyItMatters?: React.ReactNode
}) {
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
      {why[1] && (
        <div className="mt-4 rounded-xl border-l-4 border-[#1d6b5f] bg-[#e7f2ef] px-4 py-3.5">
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#1d6b5f]">
            Why it matters
          </div>
          <p className="whitespace-pre-line text-[15px] leading-relaxed text-[#16201d]">{why[1]}</p>
        </div>
      )}
      {afterWhyItMatters}
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

// Visual vote result (idea from the PolicyDecision mockup): big yes/no figures,
// a Passed/Failed badge, and a colored cell strip — from the real vote_tally.
function VoteResult({ votes }: { votes: [string, number][] }) {
  const get = (k: string) => votes.find(([l]) => l.toLowerCase() === k)?.[1] ?? 0
  const yes = get('yes')
  const no = get('no')
  const others = votes.filter(([l]) => !['yes', 'no'].includes(l.toLowerCase()))
  const passed = yes > no
  const cells = [...Array(yes).fill('y'), ...Array(no).fill('n')] as string[]
  return (
    <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-bold text-gray-900">
          <ChartBarIcon className="h-5 w-5 text-[#1d6b5f]" />
          The vote
        </h2>
        <span
          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider ${
            passed ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
          }`}
        >
          {passed ? 'Passed' : 'Failed'}
        </span>
      </div>
      <div className="flex items-end gap-2" style={CV_SERIF}>
        <span className="text-4xl font-semibold text-emerald-600">{yes}</span>
        <span className="pb-1 text-sm text-gray-400">Yes</span>
        <span className="px-1 pb-1 text-gray-300">·</span>
        <span className="text-4xl font-semibold text-rose-500">{no}</span>
        <span className="pb-1 text-sm text-gray-400">No</span>
        {others.map(([l, c]) => (
          <span key={l} className="flex items-end gap-2">
            <span className="px-1 pb-1 text-gray-300">·</span>
            <span className="text-4xl font-semibold text-gray-400">{c}</span>
            <span className="pb-1 text-sm text-gray-400 capitalize">{l}</span>
          </span>
        ))}
      </div>
      {cells.length > 0 && cells.length <= 40 && (
        <div className="mt-4 flex gap-1.5">
          {cells.map((v, i) => (
            <div
              key={i}
              className={`grid h-8 flex-1 place-items-center rounded-md text-sm font-bold text-white ${
                v === 'y' ? 'bg-emerald-500' : 'bg-rose-400'
              }`}
            >
              {v === 'y' ? '✓' : '–'}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// "Related decisions" rail — similar items by shared theme / body, from
// /api/decision/{id}/related (our metadata, not a video platform).
interface RelatedItem {
  event_decision_id: string
  headline?: string | null
  jurisdiction_name?: string | null
  state_code?: string | null
  primary_theme?: string | null
  outcome?: string | null
  shared_theme?: boolean
  shared_jurisdiction?: boolean
}

function RelatedDecisions({ id }: { id: string }) {
  const { data } = useQuery({
    queryKey: ['decision-related', id],
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => (await api.get(`/decision/${id}/related`)).data as RelatedItem[],
  })
  const items = data ?? []
  if (items.length === 0) return null
  return (
    <div className="mb-6">
      <div className="mb-3 flex items-center gap-2">
        <UsersIcon className="h-5 w-5 text-[#1d6b5f]" />
        <h2 className="text-lg font-bold text-gray-900">Related decisions</h2>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((it) => {
          const tags = [
            it.shared_theme ? it.primary_theme : null,
            it.shared_jurisdiction ? it.jurisdiction_name : null,
          ].filter(Boolean) as string[]
          return (
            <Link
              key={it.event_decision_id}
              to={`/decisions/${it.event_decision_id}`}
              className="group flex flex-col rounded-xl border border-gray-200 bg-white p-4 transition-colors hover:border-[#1d6b5f]/40 hover:bg-[#f7fafb]"
            >
              <div className="line-clamp-2 text-sm font-semibold text-gray-900 group-hover:text-[#1d6b5f]" style={CV_SERIF}>
                {it.headline || 'Decision'}
              </div>
              <div className="mt-1 text-[12px] text-gray-400">
                {[it.jurisdiction_name, it.state_code].filter(Boolean).join(', ')}
                {it.outcome ? ` · ${it.outcome}` : ''}
              </div>
              {tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {tags.slice(0, 2).map((t) => (
                    <span key={t} className="rounded-full bg-[#e7f2ef] px-2 py-0.5 text-[10.5px] font-medium text-[#1d6b5f]">
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </Link>
          )
        })}
      </div>
    </div>
  )
}

// Full recording + searchable transcript, collapsed by default and lazily
// mounted on expand so the heavy embed never blocks the read or double-loads
// alongside the evidence popout.
function WatchAndVerify({
  videoId,
  caption,
  targetText,
}: {
  videoId: string
  caption?: string
  targetText?: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <details
      className="mb-6 rounded-lg bg-white shadow-sm"
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 p-6 text-lg font-bold text-gray-900">
        <FilmIcon className="h-5 w-5 text-[#1d6b5f]" />
        Watch &amp; verify
        <span className="text-sm font-normal text-gray-400">full recording + transcript</span>
      </summary>
      {open && (
        <div className="px-2 pb-2 sm:px-4 sm:pb-4">
          <MeetingPlayer videoId={videoId} caption={caption} targetText={targetText} />
        </div>
      )}
    </details>
  )
}

export default function DecisionDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const routerLoc = useLocation()
  // Go back to wherever the user came from (homepage, search, a related card…),
  // falling back to /search only on a direct/cold load with no in-app history.
  const goBack = () => {
    if (routerLoc.key && routerLoc.key !== 'default') navigate(-1)
    else navigate('/search')
  }

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
      <div className="min-h-screen bg-[#f6faf8] py-8">
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
    const err = error as { response?: { data?: { detail?: string } }; message?: string } | null
    const errorMessage =
      err?.response?.data?.detail || err?.message || 'Unable to load decision details'
    return (
      <div className="min-h-screen bg-[#f6faf8] py-8">
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
  const videoCaption = [
    decision.meeting_name,
    decision.meeting_date ? new Date(decision.meeting_date).toLocaleDateString() : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <MeetingVideoProvider videoId={decision.meeting_video_id} caption={videoCaption || undefined}>
    <div className="min-h-screen bg-[#f6faf8] py-8" style={CV_FONT}>
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Back Button — returns to wherever the user came from */}
        <div className="mb-6">
          <button
            type="button"
            onClick={goBack}
            className="inline-flex items-center gap-2 text-[14px] font-medium text-[#1a6b6b] transition-colors hover:text-[#0f2b2b]"
          >
            <ArrowLeftIcon className="h-4 w-4" />
            Back
          </button>
        </div>

        {/* Header — editorial hero on the page background (status chips → serif
            headline → location · body · date · watch), matching the spec. */}
        <header className="mb-6">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            {decision.primary_theme && (
              <span className="rounded-full bg-[#1d6b5f] px-3 py-1 font-mono text-[11px] font-semibold uppercase tracking-wider text-white">
                {decision.primary_theme}
              </span>
            )}
            {decision.outcome && (
              <span
                className={`rounded-full border px-3 py-1 font-mono text-[11px] font-semibold uppercase tracking-wider ${outcomePill(
                  decision.outcome,
                )}`}
              >
                {decision.outcome}
              </span>
            )}
          </div>
          <h1
            className="text-[2rem] font-semibold leading-tight tracking-tight text-[#0f2b2b] sm:text-[2.2rem]"
            style={CV_SERIF}
          >
            {decision.headline || 'Untitled Decision'}
          </h1>
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13.5px] text-[#56635e]">
            {location && (
              <span className="flex items-center gap-1.5">
                <MapPinIcon className="h-4 w-4 text-[#9bb8b8]" />
                {location}
              </span>
            )}
            {decision.meeting_name && (
              <span className="flex items-center gap-1.5">
                <UsersIcon className="h-4 w-4 text-[#9bb8b8]" />
                {decision.meeting_name}
              </span>
            )}
            {decision.meeting_date && (
              <span className="flex items-center gap-1.5">
                <CalendarIcon className="h-4 w-4 text-[#9bb8b8]" />
                {new Date(decision.meeting_date).toLocaleDateString()}
              </span>
            )}
            <WatchRecordingLink />
          </div>
        </header>


        {/* Key Takeaways (smart_brevity) — leads, with "Why it matters", then
            the decision tucked directly under it. If there's no smart_brevity,
            the decision still shows in its own card. */}
        {!isEmpty(decision.smart_brevity) ? (
          <Section title="Key Takeaways" icon={<SparklesIcon className="h-5 w-5 text-[#1d6b5f]" />}>
            <SmartBrevityBody
              sb={decision.smart_brevity as Record<string, unknown>}
              afterWhyItMatters={
                decision.decision_statement ? (
                  <DecisionBlock statement={decision.decision_statement} />
                ) : null
              }
            />
          </Section>
        ) : (
          decision.decision_statement && (
            <Section title="Decision">
              <p className="text-sm leading-relaxed text-gray-700 whitespace-pre-line">
                {decision.decision_statement}
              </p>
            </Section>
          )
        )}

        {/* Vote result (visual) */}
        {voteEntries.length > 0 && (
          <VoteResult votes={voteEntries as [string, number][]} />
        )}

        {/* Frame analysis: where the sides disagreed (renders its own card) */}
        {!isEmpty(decision.competing_views) && (
          <CompetingViews data={decision.competing_views} />
        )}

        {/* Human Element — named voices with avatars + room sentiment */}
        {!isEmpty(decision.human_element) && <HumanElement data={decision.human_element} />}

        {/* Related decisions — shared theme / body */}
        <RelatedDecisions id={decision.event_decision_id} />

        {/* Watch & verify — full recording + transcript, collapsed */}
        {decision.meeting_video_id && (
          <WatchAndVerify
            videoId={decision.meeting_video_id}
            caption={videoCaption || undefined}
            targetText={[decision.headline, decision.decision_statement]
              .filter(Boolean)
              .join('. ') || undefined}
          />
        )}

        {/* Provenance / attribution */}
        <div className="mt-2 rounded-xl border border-dashed border-gray-300 bg-white/60 p-4">
          <div className="flex items-start gap-2.5">
            <SparklesIcon className="mt-0.5 h-4 w-4 shrink-0 text-[#1d6b5f]" />
            <div className="text-[12px] leading-relaxed text-gray-400">
              <span className="text-gray-500">AI-extracted summary</span>
              {decision.source_ai_model && <> — {decision.source_ai_model}</>}
              {decision.extracted_at && (
                <>, {new Date(decision.extracted_at).toLocaleDateString()}</>
              )}
              , from the meeting transcript. Verify against the recording.
              {decision.c1_event_id && (
                <div className="mt-1">Event: {decision.c1_event_id}</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
    </MeetingVideoProvider>
  )
}
