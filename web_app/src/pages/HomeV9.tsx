// Open Navigator — Homepage (v9 prototype design), single-column.
//
// This is a faithful port of the "OpenNavigatorHome (9)" design prototype, but
// EVERY figure is wired to REAL data (CLAUDE.md: No Fabricated Data). The
// prototype's invented numbers — the ZIP→rate table, the $5.7M/8/18 snapshot,
// the hard-coded THIS_WEEK / feed stories, the directory counts — are all
// replaced with live API values, and anything genuinely missing renders an
// honest empty state instead of a placeholder.
//
//   - Money hook + modal  → the real <MoneyHook> (/api/local-finance +
//                           /api/grandkid-outlook + the real ACS property-tax rate).
//   - Snapshot strip      → /api/lenses `activity` (tracked spending, contested,
//                           analyzed, coming-back-for-a-vote).
//   - This week / signals / Close-to-Home feed → /api/lenses `lenses[].cards`.
//   - Browse the directory counts → /search type_totals + policy-question registry.
//   - Trending questions  → real policy-question registry (/api/policy-question/).
//
// Editorial UI copy (signal descriptions, topic labels, "why people use it") is
// kept verbatim from the prototype — that's interface text, not data figures.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { getLaunchCounty } from '../lib/launchCounties'
import MoneyGameModal from '../components/MoneyGameModal'
import MoneyMovesTeaser from '../components/MoneyMovesTeaser'
import { useLocation as useLocationContext } from '../contexts/LocationContext'
import AddressLookup from '../components/AddressLookup'
import SiteHeader from '../components/SiteHeader'
import { LensCarousel, type ApiCard } from '../components/StoryLenses'
import MeetingThumbnail from '../components/MeetingThumbnail'
import { fetchMeetings, type MeetingCard } from '../api/meetings'
import { LAUNCH_CITIES } from '../lib/launchCoverage'

const TEAL = '#0d9488'
const TEAL_DARK = '#0f766e'
const INK = '#1c1917'

const FONTS = `
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;800;900&family=Source+Sans+3:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
.v9 .font-display { font-family: 'Playfair Display', Georgia, serif; }
.v9 .font-body { font-family: 'Source Sans 3', system-ui, sans-serif; }
.v9 .font-mono-x { font-family: 'IBM Plex Mono', monospace; }
.v9 .hide-scroll::-webkit-scrollbar { display: none; }
.v9 .hide-scroll { scrollbar-width: none; }
.v9 .clamp2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.v9 .v9-burger { display: none; }
html { scroll-behavior: smooth; }
.v9 .v9-navlink { position: relative; background: none; border: none; padding: 4px 0; font-size: 14.5px; font-weight: 600; color: #44403c; cursor: pointer; font-family: inherit; transition: color .2s ease; }
.v9 .v9-navlink::after { content: ''; position: absolute; left: 0; bottom: -3px; height: 2px; width: 0; background: ${TEAL}; transition: width .25s ease; }
.v9 .v9-navlink:hover { color: ${TEAL_DARK}; }
.v9 .v9-navlink:hover::after { width: 100%; }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@media (max-width: 760px) {
  .v9 .v9-nav { display: none; }
  .v9 .v9-nav.open { display: flex; flex-direction: column; align-items: stretch; position: absolute; top: 100%; left: 0; right: 0; background: #fff; border-bottom: 1px solid #e7e5e4; padding: 10px 16px 16px; gap: 4px; box-shadow: 0 16px 32px rgba(28,25,23,0.1); }
  .v9 .v9-burger { display: grid; margin-left: auto; }
  .v9 .v9-brand-sub { display: none; }
}
`

// Per-lens editorial styling, keyed by the API's lens id. Labels/descriptions
// are UI copy; the cards & counts under them are real.
const SIGNAL_META: Record<
  string,
  { name: string; icon: string; color: string; bg: string; desc: string }
> = {
  contested: { name: 'Contested', icon: '🔥', color: '#ea580c', bg: '#fff7ed', desc: 'Split votes and heated debate among officials or residents' },
  money: { name: 'Money Moves', icon: '💵', color: '#059669', bg: '#ecfdf5', desc: 'Contracts, grants, and budget changes pulled from the record' },
  flags: { name: 'Raised Eyebrows', icon: '🤨', color: '#7c3aed', bg: '#f5f3ff', desc: 'Unusual patterns — sole-source contracts, reversals, late additions' },
  soon: { name: 'Moving Fast', icon: '⚡', color: '#d97706', bg: '#fffbeb', desc: 'Items moving quicker than the usual process' },
  next: { name: 'Watch Next', icon: '👀', color: '#2563eb', bg: '#eff6ff', desc: 'Upcoming votes worth keeping on your radar' },
}
const WHEN: { label: string; window: string }[] = [
  { label: 'Past month', window: 'month' },
  { label: 'Past 3 months', window: 'quarter' },
  { label: 'Past year', window: 'year' },
  { label: 'All time', window: 'all' },
]

// Map a real /api/meetings card into the shared LensCarousel card shape so the
// "What's New" rail renders the most recent meetings in the same tiles the topic
// lenses use — regardless of whether the meeting produced a decision. Stat chips
// are shown only when there's a genuine count (no fabricated/zero filler).
function meetingToCard(m: MeetingCard): ApiCard {
  const stats: ApiCard['stats'] = []
  if (m.decision_count > 0)
    stats.push({ value: String(m.decision_count), label: m.decision_count === 1 ? 'Decision' : 'Decisions' })
  if (m.question_count > 0)
    stats.push({ value: String(m.question_count), label: m.question_count === 1 ? 'Topic' : 'Topics' })
  return {
    headline: m.title || 'Untitled meeting',
    stats,
    jurisdiction: m.city || m.jurisdiction || '',
    date: m.date || undefined,
    url: `/meetings/${m.meeting_id}`,
    state_code: m.state_code || undefined,
    state: m.state || undefined,
    video_id: m.video_id,
  }
}

// Left-side search scope. `types` is the comma list handed to /search (UnifiedSearch
// reads ?types=); 'all' sends no types param so the search spans everything.
const SEARCH_CATEGORIES: { id: string; label: string; types: string }[] = [
  { id: 'all', label: 'All', types: '' },
  { id: 'meetings', label: 'Meetings', types: 'meetings' },
  { id: 'transcripts', label: 'Videos', types: 'documents' },
  // Official meeting PDFs (agenda / minutes / attachments) from
  // public.event_meeting_document — full-text searched over extracted PDF body
  // where present. Distinct from 'Videos' (transcripts) above; backend type is
  // 'meeting_documents' (UnifiedSearch renders the tab + the agenda/minutes/
  // attachment document_type filter).
  { id: 'meeting_documents', label: 'Meeting Documents', types: 'meeting_documents' },
  { id: 'decisions', label: 'Decisions', types: 'decisions' },
  { id: 'leaders', label: 'Leaders', types: 'leaders' },
  { id: 'nonprofits', label: 'Nonprofits', types: 'organizations' },
  { id: 'causes', label: 'Causes', types: 'causes' },
  { id: 'questions', label: 'Questions', types: 'questions' },
  { id: 'topics', label: 'Topics', types: 'topics' },
  { id: 'bills', label: 'Bills', types: 'bills' },
  { id: 'grants', label: 'Grants', types: 'grants' },
]

// ---- /api/lenses response (the subset we render) ----
interface LensActivity {
  icon: string
  value: string
  label: string
  query?: string
}
interface LensCard {
  headline: string
  jurisdiction: string
  date?: string
  url?: string
  // The same /api/lenses cards also carry per-card stat chips ("5–4 Vote",
  // "1 Opposing views") and a state code — rendered by the LensCarousel.
  stats: { value: string; label: string; tone?: 'plain' | 'green' | 'amber' | 'red' | 'blue' | 'purple' }[]
  badge?: string
  state_code?: string
  state?: string
}
interface LensBlock {
  id: string
  label: string
  placeholder: boolean
  cards: LensCard[]
}
interface LensesResp {
  lenses: LensBlock[]
  activity: LensActivity[]
  location_label?: string
}

// One row of the hero search typeahead — a real /api/search result.
interface SearchSuggestion {
  type: string
  title: string
  subtitle?: string | null
  url: string
  score?: number
}

// One row from GET /api/browse/summary (categories[], pre-sorted by
// transcript_count desc with `place` always last — far right). transcript_count is a real
// distinct-transcript count; has_transcripts is false only for cause (no
// transcript linkage exists in the data).
interface BrowseSummaryCategory {
  entity_type: string
  label: string
  transcript_count: number
  entity_count: number
  has_transcripts: boolean
}

// Per-category lookup the browse cards read: the real transcript count, whether
// any transcripts are linked, and the API's ordering index (for card sort).
interface DirectorySummaryEntry {
  transcript_count: number
  has_transcripts: boolean
  order: number
}

interface DirectorySummary {
  byType: Record<string, DirectorySummaryEntry>
}

// One row from GET /api/browse/top-items — a single browseable item with its
// genuine distinct-transcript count. Drives the flyout previews so every
// dropdown row (including causes) shows a real transcript count.
interface BrowseTopItem {
  entity_id: string
  entity_name: string
  transcript_count: number
}

// Maps each browse card's stable `key` to the API's entity_type so cards can
// pull their real count + ordering from the /browse/summary lookup.
const BROWSE_CARD_ENTITY_TYPE: Record<'questions' | 'topics' | 'causes' | 'places', string> = {
  questions: 'question',
  topics: 'topic',
  causes: 'cause',
  places: 'place',
}

// Emoji marker per result type for the typeahead rows (visual scent only).
const SUGGEST_ICON: Record<string, string> = {
  topic: '🏷️',
  organization: '🏢',
  person: '👤',
  leader: '🎖️',
  decision: '⚖️',
  bill: '📜',
  cause: '💚',
  question: '⚖️',
  meeting: '🗓️',
}

// ── Small pieces ──────────────────────────────────────────────────────────
function Chip({
  active,
  children,
  onClick,
  style,
}: {
  active?: boolean
  children: React.ReactNode
  onClick?: () => void
  style?: React.CSSProperties
}) {
  return (
    <button
      onClick={onClick}
      className="font-body"
      style={{
        padding: '8px 16px',
        borderRadius: 999,
        border: `1px solid ${active ? TEAL : '#d6d3d1'}`,
        background: active ? TEAL : '#fff',
        color: active ? '#fff' : '#1c1917',
        boxShadow: active ? 'none' : '0 1px 2px rgba(28,25,23,0.05)',
        fontSize: 14.5,
        fontWeight: 600,
        cursor: 'pointer',
        whiteSpace: 'nowrap',
        transition: 'all 120ms ease',
        ...style,
      }}
    >
      {children}
    </button>
  )
}

// ── Money hook (compact banner; opens the REAL modal) ───────────────────────
// The "How much of your money is on the line?" teal banner. The CTA simply opens
// the real <MoneyGameModal>; the modal itself owns location — if we already know
// the user's place it loads the bill, otherwise tab 1 shows the "where's home?"
// ZIP gate. No location is ever fabricated.
function MoneyHookBanner() {
  const { location } = useLocationContext()
  const [modalOpen, setModalOpen] = useState(false)

  return (
    <section style={{ paddingTop: 22 }}>
      {/* Compact teal banner — the screenshot's "money on the line" hook. */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          flexWrap: 'wrap',
          background: '#ecfdf5',
          border: '1px solid #99f6e4',
          borderRadius: 16,
          padding: '16px 22px',
        }}
      >
        <span style={{ fontSize: 30, lineHeight: 1, flexShrink: 0 }}>💵</span>
        <div style={{ flex: 1, minWidth: 240 }}>
          <div className="font-display" style={{ fontSize: 'clamp(19px, 2.4vw, 23px)', fontWeight: 800, lineHeight: 1.15, color: INK }}>
            How much of <span style={{ color: TEAL }}>your money</span> is on the line?
          </div>
          <div style={{ fontSize: 14, color: '#57534e', marginTop: 4 }}>
            Four governments, one wallet. 90 seconds, mildly humbling, grandkids included.
          </div>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          style={{ background: TEAL, color: '#fff', border: 'none', borderRadius: 999, padding: '12px 24px', fontSize: 15, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap', flexShrink: 0 }}
        >
          Show me my money →
        </button>
      </div>

      <MoneyGameModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        stateCode={location?.state}
        city={location?.city || undefined}
        county={location?.county || undefined}
        requestedLabel={location?.city || location?.county || location?.state || undefined}
      />
    </section>
  )
}

// ── Step 0: Why should I care? (Personal Impact Assessment) ─────────────────
// The "before you do anything, here's why it matters to YOU" framing that opens
// the How-it-works section. Both CTAs open the REAL <MoneyGameModal>: the cost
// estimator lands on the bill stage, the income-trends button jumps straight to
// the Opportunity Atlas (grandkids) mobility view. No figures are shown here —
// every number lives behind the modal, sourced from the warehouse.
function StepZeroImpact() {
  const { location } = useLocationContext()
  const [modal, setModal] = useState<null | 'estimate' | 'grandkids'>(null)

  // Human label for the intro line, derived from the saved place — never faked.
  const placeLabel =
    location?.city && location?.county
      ? `${location.city} and ${location.county}`
      : location?.city || location?.county || location?.state || 'your community'

  return (
    <div
      style={{
        background: '#f0fdfa',
        border: '1px solid #99f6e4',
        borderRadius: 18,
        padding: 'clamp(16px, 2.2vw, 22px)',
        marginBottom: 22,
        maxWidth: 760,
        marginLeft: 'auto',
        marginRight: 'auto',
        textAlign: 'center',
      }}
    >
      <div className="font-display" style={{ fontSize: 'clamp(18px, 2.3vw, 21px)', fontWeight: 800, color: INK }}>
        Step 0 · Why should I care? <span style={{ color: TEAL_DARK }}>Personal Impact</span>
      </div>
      <p style={{ fontSize: 14, color: '#44403c', lineHeight: 1.45, margin: '6px auto 0', maxWidth: 560 }}>
        Local decisions shape your taxes, schools, safety, and your family&apos;s future — whether you engage or not.
        Doing nothing is a choice too, with real consequences for you and your children.
      </p>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap', marginTop: 14 }}>
        <button
          onClick={() => setModal('estimate')}
          style={{ background: TEAL, color: '#fff', border: 'none', borderRadius: 999, padding: '11px 22px', fontSize: 14.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
        >
          💵 Try the cost estimator
        </button>
        <button
          onClick={() => setModal('grandkids')}
          style={{ background: '#fff', color: TEAL_DARK, border: '1px solid #99f6e4', borderRadius: 999, padding: '11px 22px', fontSize: 14.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
        >
          📈 View income mobility trends
        </button>
      </div>

      <MoneyGameModal
        open={modal !== null}
        onClose={() => setModal(null)}
        stateCode={location?.state}
        city={location?.city || undefined}
        county={location?.county || undefined}
        requestedLabel={location?.city || location?.county || location?.state || undefined}
        initialStage={modal === 'grandkids' ? 'grandkids' : 'estimate'}
      />

      <p style={{ fontSize: 12.5, color: '#57534e', marginTop: 10 }}>
        Scoped to {placeLabel} once you confirm where home is.
      </p>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function HomeV9() {
  const navigate = useNavigate()
  const { location, setLocation } = useLocationContext()
  const locState = location?.state || undefined
  const locCity = location?.city || undefined

  // ── Location level — City / State / National ──
  // Restores the geography selector that used to live in the hero. Defaults to
  // the most specific level the saved location supports, and resets to that
  // default whenever the saved location changes — unless the user has manually
  // picked a level (via the dropdown or the "expand" prompt below).
  type Level = 'city' | 'state' | 'national'
  const naturalLevel = (): Level => (locCity ? 'city' : locState ? 'state' : 'national')
  const [level, setLevel] = useState<Level>(naturalLevel)
  const levelPicked = useRef(false)
  const [levelOpen, setLevelOpen] = useState(false)
  // Inline "change location" picker inside the level menu (restores the ability
  // to switch to a different city/place, not just City/State/National scope).
  const [changingLoc, setChangingLoc] = useState(false)
  // When the user picks a place we haven't loaded civic data for yet, we keep the
  // picker open and show a friendly "not loaded yet" notice (with the launch
  // cities as alternatives) instead of silently dropping them into an empty scope.
  const [uncoveredPick, setUncoveredPick] = useState<{ city?: string; state?: string } | null>(null)
  const uncoveredLabel = (l: { city?: string; state?: string } | null) =>
    l ? [l.city, l.state].filter(Boolean).join(', ') : ''
  const levelRef = useRef<HTMLButtonElement>(null)
  const levelMenuRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (levelPicked.current) return
    setLevel(locCity ? 'city' : locState ? 'state' : 'national')
  }, [locCity, locState])
  useEffect(() => {
    if (!levelOpen) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node
      if (levelRef.current?.contains(t) || levelMenuRef.current?.contains(t)) return
      setLevelOpen(false)
      setChangingLoc(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [levelOpen])
  const pickLevel = (v: Level) => {
    levelPicked.current = true
    setLevel(v)
    setLevelOpen(false)
  }

  // The active scope flows from `level` into every place-scoped query below.
  const national = level === 'national' || !locState
  const stateCode = national ? undefined : locState
  const city = level === 'city' ? locCity : undefined
  const placeLabel =
    level === 'national' || !locState
      ? 'the U.S.'
      : level === 'state'
        ? locState
        : locCity || location?.county || locState

  const levelOptions: { value: Level; label: string; disabled: boolean }[] = [
    { value: 'city', label: locCity ? `City · ${locCity}` : 'City', disabled: !locCity },
    { value: 'state', label: locState ? `State · ${locState}` : 'State', disabled: !locState },
    { value: 'national', label: 'National · U.S.', disabled: false },
  ]

  const [query, setQuery] = useState('')
  const [searchFocused, setSearchFocused] = useState(false)
  // Left-side category scope for the hero search box.
  const [cat, setCat] = useState(SEARCH_CATEGORIES[0])
  const [catOpen, setCatOpen] = useState(false)
  const catRef = useRef<HTMLButtonElement>(null)
  const catMenuRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!catOpen) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node
      if (catRef.current?.contains(t) || catMenuRef.current?.contains(t)) return
      setCatOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [catOpen])
  // Live typeahead: a debounced copy of `query` drives the suggestions query so
  // we don't fire a request per keystroke. `suggestOpen` lets a click on a
  // suggestion win the race against the input's blur (cleared on select/enter).
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [suggestOpen, setSuggestOpen] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 220)
    return () => clearTimeout(t)
  }, [query])
  const [when, setWhen] = useState(WHEN[0])
  const [showStrategicPlan, setShowStrategicPlan] = useState(false)

  // When arriving from another page via `/#how-it-works` (shared header nav),
  // scroll to the requested in-page section once it has rendered.
  useEffect(() => {
    const id = window.location.hash.replace('#', '')
    if (id) {
      requestAnimationFrame(() =>
        document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
      )
    }
  }, [])

  // ── Real data ──
  const { data: lensesData } = useQuery<LensesResp>({
    queryKey: ['home-v9-lenses', national, stateCode, city, when.window],
    queryFn: () => {
      const params: Record<string, string> = { window: when.window }
      if (!national && stateCode) params.state = stateCode
      if (!national && city) params.city = city
      return api.get('/lenses', { params }).then((r) => r.data)
    },
    staleTime: 5 * 60 * 1000,
  })

  // ── Recent meetings (REAL /api/meetings, sort=recent) ──
  // Fallback content for the Contested / Raised Eyebrows lenses: when this place
  // has analyzed transcripts but no lens activity yet (no contested votes or
  // flagged patterns surfaced), we'd otherwise show two empty "No activity"
  // cards. Instead we show the most recent meetings here — a real, useful
  // signal — and hide the empty lens sections. Always a small page; only
  // actually rendered when both lenses come back empty.
  const { data: recentMeetingsData } = useQuery<MeetingCard[]>({
    queryKey: ['home-v9-recent-meetings', national, stateCode, city],
    queryFn: () =>
      fetchMeetings({
        state: national ? undefined : stateCode || undefined,
        city: national ? undefined : city || undefined,
        sort: 'recent',
        limit: 6,
      }).then((r) => r.items),
    staleTime: 5 * 60 * 1000,
  })
  const recentMeetings = recentMeetingsData ?? []

  // Browse-card badges are a genuine distinct-transcript count per category,
  // served pre-sorted (transcript_count desc, place pinned far right) by /api/browse/summary.
  // We index by entity_type so each card can read its real count + ordering and
  // honor has_transcripts (cause has no transcript linkage → honest em-dash).
  const { data: directoryCounts } = useQuery<DirectorySummary>({
    queryKey: ['home-v9-directory-counts', stateCode, national],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (!national && stateCode) params.state = stateCode
      const res = await api
        .get('/browse/summary', { params })
        .then((r) => r.data as { categories?: BrowseSummaryCategory[] })
        .catch(() => null)
      const categories = res?.categories ?? []
      const byType: Record<string, DirectorySummaryEntry> = {}
      categories.forEach((c, index) => {
        byType[c.entity_type] = {
          transcript_count: c.transcript_count,
          has_transcripts: c.has_transcripts,
          order: index,
        }
      })
      return { byType }
    },
    staleTime: 5 * 60 * 1000,
  })

  // ── Browse-pill flyout state + top-item previews (REAL data only) ──
  // Exactly one flyout open at a time. On touch devices the pill toggles on
  // click; on hover-capable devices it opens on mouseenter.
  const [browseOpen, setBrowseOpen] = useState<'topics' | 'causes' | 'questions' | 'places' | null>(null)
  const [isTouch] = useState(
    () => typeof window !== 'undefined' && !!window.matchMedia?.('(hover: none)').matches,
  )

  // Flyout previews: the top ~5 items per browse category, each carrying its
  // REAL distinct-transcript count, from the canonical /api/browse/top-items
  // endpoint (ordered transcript_count desc). Sourcing all four categories —
  // including causes — from this one endpoint guarantees every dropdown row
  // shows a genuine transcript count. Causes are honestly 0: no cause↔transcript
  // linkage exists in the warehouse, so that 0 is real, not fabricated.
  // State-scoped (place/topic) when a state is selected.
  const { data: browseTopItems } = useQuery<Record<string, BrowseTopItem[]>>({
    queryKey: ['home-v9-browse-top-items', stateCode, national],
    queryFn: async () => {
      const fetchType = async (entityType: string): Promise<BrowseTopItem[]> => {
        const params: Record<string, string | number> = { entity_type: entityType, limit: 5 }
        if (!national && stateCode) params.state = stateCode
        const res = await api
          .get('/browse/top-items', { params })
          .then((r) => r.data as { items?: BrowseTopItem[] })
          .catch(() => null)
        return res?.items ?? []
      }
      const [topic, question, place, cause] = await Promise.all([
        fetchType('topic'),
        fetchType('question'),
        fetchType('place'),
        fetchType('cause'),
      ])
      return { topic, question, place, cause }
    },
    staleTime: 30 * 60 * 1000,
  })

  // ── "Search in" category counts (real /api/search type_totals) ──
  // Per-category match counts for the category dropdown, DYNAMIC on the search
  // text: re-runs as the (debounced) query / place changes so each row shows how
  // many real results that scope would return. Fetched lazily (only while the
  // menu is open) with limit=1 — we want `type_totals`, not rows — so it never
  // slows the hero. No fabricated numbers: a type the API doesn't count is blank.
  const { data: catCountsData, isFetching: catCountsFetching } = useQuery<Record<string, number>>({
    queryKey: ['home-v9-cat-counts', debouncedQuery, national, stateCode, city],
    queryFn: async () => {
      const params: Record<string, string> = {
        types: 'meetings,documents,meeting_documents,decisions,leaders,organizations,causes,questions,topics,bills,grants',
        limit: '1',
      }
      if (debouncedQuery.length >= 2) params.q = debouncedQuery
      if (!national && stateCode) params.state = stateCode
      if (!national && city) params.city = city
      const res = await api.get('/search/', { params }).then((r) => r.data).catch(() => null)
      return (res?.type_totals ?? {}) as Record<string, number>
    },
    enabled: catOpen,
    staleTime: 60 * 1000,
    placeholderData: (prev) => prev, // keep last counts while the next query loads
  })
  const catCounts = catCountsData ?? {}
  // Each row maps 1:1 to its type_totals key (c.types); undefined when the API
  // didn't count that type (→ no badge). 'All' intentionally shows NO count: its
  // only honest value would be the sum across every type, but those catalogs sit
  // at different geographic grains (local meetings/decisions vs. state bills,
  // grants, and national questions/topics), so a single total reads as nonsense
  // next to the local rows. The per-category numbers are the coherent signal.
  const countForCat = (c: { id: string; types: string }): number | undefined =>
    c.id === 'all' ? undefined : catCounts[c.types]

  // ── Search typeahead (real /api/search results) ──
  // Queries only the FAST search types — `documents` (transcript full-text) runs
  // a ~2-3s COUNT and is deliberately excluded so per-keystroke suggestions stay
  // snappy. Results are scoped to the active place. No fabricated rows: an empty
  // response renders nothing.
  const { data: suggestData, isFetching: suggestFetching } = useQuery<SearchSuggestion[]>({
    queryKey: ['home-v9-suggest', debouncedQuery, stateCode, city],
    queryFn: async () => {
      const params: Record<string, string> = {
        q: debouncedQuery,
        limit: '4',
        types: 'topics,organizations,people,leaders,decisions,bills,causes,questions',
      }
      if (!national && stateCode) params.state = stateCode
      if (!national && city) params.city = city
      const res = await api.get('/search/', { params }).then((r) => r.data)
      const groups = (res?.results ?? {}) as Record<string, SearchSuggestion[]>
      return Object.values(groups)
        .flat()
        .filter((r) => r && r.title && r.url)
        .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
        .slice(0, 7)
    },
    enabled: debouncedQuery.length >= 2,
    staleTime: 60 * 1000,
    placeholderData: (prev) => prev,
  })
  const suggestions = suggestData ?? []
  const showSuggest = suggestOpen && query.trim().length >= 2

  // ── Derived (all real) ──
  const lenses = lensesData?.lenses ?? []
  const lensById = useMemo(() => {
    const m: Record<string, LensBlock> = {}
    for (const l of lenses) m[l.id] = l
    return m
  }, [lenses])

  const runSearch = (q?: string) => {
    const term = (q ?? query).trim()
    setSuggestOpen(false)
    const params = new URLSearchParams()
    if (term) params.set('q', term)
    if (cat.types) params.set('types', cat.types)
    if (!national && stateCode) params.set('state', stateCode)
    // Carry the city through so a drill-down from e.g. Tuscaloosa reads
    // "City: Tuscaloosa" rather than just "State: AL" (UnifiedSearch reads ?city=).
    if (!national && city) {
      params.set('city', city)
      // Default a known launch city to the county-inclusive scope so search lands
      // on the surrounding-county view (e.g. Tuscaloosa → Tuscaloosa County) with
      // the "Include surrounding county" checkbox shown and checked. SF is a
      // consolidated city-county (no broadening), so leave it city-only.
      const lc = getLaunchCounty(city)
      if (lc && lc.countyFips !== '06075') params.set('county', '1')
    }
    navigate(`/search?${params.toString()}`, { state: { fromHome: true } })
  }

  // Jump straight to a suggested entity's real detail/search URL.
  const selectSuggestion = (s: SearchSuggestion) => {
    setSuggestOpen(false)
    setQuery(s.title)
    navigate(s.url, { state: { fromHome: true } })
  }

  return (
    <div className="v9 font-body" style={{ background: '#fafaf9', minHeight: '100vh', color: INK }}>
      <style>{FONTS}</style>

      {/* ── Shared header (identical to the search page) ── */}
      <SiteHeader />

      <main style={{ maxWidth: 1180, margin: '0 auto', padding: '0 24px' }}>
        {/* ── Money hook (compact teal banner; REAL geocode + REAL modal) — sits
            above the search hero ── */}
        <MoneyHookBanner />

        {/* ── Hero: thesis + search + trending ── */}
        <section style={{ padding: '44px 0 6px', textAlign: 'center' }}>
          <h1
            className="font-display"
            style={{ fontSize: 'clamp(38px, 6.4vw, 60px)', fontWeight: 900, margin: 0, lineHeight: 1.05, letterSpacing: '-0.02em', color: INK }}
          >
            Every local decision, in one place.
          </h1>
          <div style={{ fontSize: 'clamp(16px, 2vw, 19px)', fontWeight: 500, color: '#57534e', maxWidth: 760, margin: '16px auto 0', lineHeight: 1.5 }}>
            Search the meetings, votes, spending, and debates shaping your community.
            <br />
            Free, forever.
          </div>

          {/* ── Launch-coverage note: live in four cities (ordered by content
              volume), each linking to its state-scoped search. ── */}
          <div
            style={{
              display: 'inline-flex',
              flexWrap: 'wrap',
              justifyContent: 'center',
              alignItems: 'center',
              columnGap: 8,
              rowGap: 4,
              margin: '20px auto 0',
              maxWidth: 760,
              padding: '9px 18px',
              borderRadius: 999,
              background: 'rgba(13,148,136,0.08)',
              border: '1px solid rgba(13,148,136,0.25)',
              fontSize: 14,
              color: '#0f766e',
              lineHeight: 1.45,
            }}
          >
            <span style={{ fontWeight: 700 }}>📍 Live in</span>
            {LAUNCH_CITIES.map((c, i) => (
              <span key={`${c.city}-${c.state}`}>
                <Link
                  to={`/search?state=${c.state}&city=${encodeURIComponent(c.city)}`}
                  style={{ color: TEAL_DARK, fontWeight: 600, textDecoration: 'underline' }}
                >
                  {c.city}, {c.state}
                </Link>
                {i < LAUNCH_CITIES.length - 1 ? ' ·' : ''}
              </span>
            ))}
            <span style={{ fontWeight: 600, color: '#0d9488' }}>— more cities coming soon</span>
          </div>

          <div style={{ position: 'relative', maxWidth: 760, margin: '28px auto 0', textAlign: 'left' }}>
            <div
              style={{
                display: 'flex',
                background: '#fff',
                border: `2px solid ${TEAL}`,
                borderRadius: showSuggest ? '16px 16px 0 0' : 16,
                boxShadow: searchFocused
                  ? `0 0 0 4px rgba(13,148,136,0.18), 0 14px 36px rgba(13,148,136,0.22)`
                  : `0 10px 30px rgba(13,148,136,0.15)`,
                transition: 'box-shadow .2s ease',
                overflow: 'hidden',
              }}
            >
              {/* Left-side category scope — pick Decisions, Bills, Leaders, etc. */}
              <button
                ref={catRef}
                type="button"
                onClick={() => setCatOpen((o) => !o)}
                aria-haspopup="listbox"
                aria-expanded={catOpen}
                aria-label="Search category"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  flexShrink: 0,
                  background: 'none',
                  border: 'none',
                  borderRight: '1px solid #e7e5e4',
                  padding: '0 16px',
                  fontSize: 15,
                  fontWeight: 600,
                  color: INK,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  whiteSpace: 'nowrap',
                }}
              >
                {cat.label}
                <span
                  style={{
                    fontSize: 11,
                    color: '#78716c',
                    transform: catOpen ? 'rotate(180deg)' : 'none',
                    transition: 'transform .15s ease',
                  }}
                  aria-hidden
                >
                  ▾
                </span>
              </button>

              <input
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setSuggestOpen(true)
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') runSearch()
                  else if (e.key === 'Escape') setSuggestOpen(false)
                }}
                onFocus={() => {
                  setSearchFocused(true)
                  setSuggestOpen(true)
                }}
                // Delay the close so a mousedown on a suggestion row still fires
                // its onClick before the dropdown unmounts.
                onBlur={() => {
                  setSearchFocused(false)
                  setTimeout(() => setSuggestOpen(false), 140)
                }}
                placeholder="Search topics, people, organizations, or causes"
                style={{ flex: 1, border: 'none', outline: 'none', padding: '18px 20px', fontSize: 17, fontFamily: 'inherit', minWidth: 0 }}
              />
              <button
                ref={levelRef}
                type="button"
                onClick={() => setLevelOpen((o) => !o)}
                aria-haspopup="listbox"
                aria-expanded={levelOpen}
                aria-label="Location level"
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 14px', borderLeft: '1px solid #e7e5e4', background: 'none', color: '#44403c', fontSize: 14.5, fontWeight: 600, whiteSpace: 'nowrap', cursor: 'pointer', fontFamily: 'inherit' }}
              >
                📍 {placeLabel}
                <span
                  style={{ fontSize: 11, color: '#78716c', transform: levelOpen ? 'rotate(180deg)' : 'none', transition: 'transform .15s ease' }}
                  aria-hidden
                >
                  ▾
                </span>
              </button>
              <button
                aria-label="Search"
                onClick={() => runSearch()}
                style={{ background: TEAL, color: '#fff', border: 'none', padding: '0 28px', fontSize: 20, cursor: 'pointer' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = TEAL_DARK)}
                onMouseLeave={(e) => (e.currentTarget.style.background = TEAL)}
              >
                🔍
              </button>
            </div>

            {/* Category scope menu — anchored to the outer relative wrapper so it
                escapes the search box's overflow:hidden clipping. */}
            {catOpen && (
              <div
                ref={catMenuRef}
                role="listbox"
                aria-label="Search category"
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 8px)',
                  left: 0,
                  zIndex: 50,
                  minWidth: 220,
                  background: '#fff',
                  border: '1px solid #e7e5e4',
                  borderRadius: 14,
                  boxShadow: '0 16px 38px rgba(13,148,136,0.20)',
                  padding: 6,
                  maxHeight: 380,
                  overflowY: 'auto',
                }}
              >
                <div
                  style={{
                    padding: '6px 10px 8px',
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: '#a8a29e',
                  }}
                >
                  Search in
                </div>
                {SEARCH_CATEGORIES.map((c) => {
                  const selected = c.id === cat.id
                  const n = countForCat(c)
                  // While the (lazy, ~2s) count query is in flight and we don't yet
                  // have a number for this row, show a skeleton instead of a blank
                  // so the counts read as "loading", not "missing". 'All' never
                  // shows a count, so it never shows a skeleton.
                  const showCountSkeleton = c.id !== 'all' && n == null && catCountsFetching
                  return (
                    <button
                      key={c.id}
                      type="button"
                      role="option"
                      aria-selected={selected}
                      onClick={() => {
                        setCat(c)
                        setCatOpen(false)
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        width: '100%',
                        textAlign: 'left',
                        background: selected ? '#f0fdfa' : 'none',
                        border: 'none',
                        borderRadius: 9,
                        padding: '9px 12px',
                        fontSize: 14.5,
                        fontWeight: selected ? 700 : 500,
                        color: selected ? TEAL_DARK : '#44403c',
                        cursor: 'pointer',
                        fontFamily: 'inherit',
                      }}
                      onMouseEnter={(e) => {
                        if (!selected) e.currentTarget.style.background = '#f5f5f4'
                      }}
                      onMouseLeave={(e) => {
                        if (!selected) e.currentTarget.style.background = 'none'
                      }}
                    >
                      <span>{c.label}</span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {n != null ? (
                          <span
                            className="font-mono-x"
                            style={{ fontSize: 11.5, fontWeight: 600, color: selected ? TEAL : '#a8a29e', fontVariantNumeric: 'tabular-nums' }}
                          >
                            {n.toLocaleString('en-US')}
                          </span>
                        ) : showCountSkeleton ? (
                          <span
                            aria-hidden
                            className="animate-pulse"
                            style={{ width: 22, height: 9, borderRadius: 4, background: '#e7e5e4' }}
                          />
                        ) : null}
                        {selected && <span style={{ color: TEAL }} aria-hidden>✓</span>}
                      </span>
                    </button>
                  )
                })}
              </div>
            )}

            {/* Location-level menu — City / State / National. Anchored to the
                outer relative wrapper so it escapes the search box clipping. */}
            {levelOpen && (
              <div
                ref={levelMenuRef}
                role="listbox"
                aria-label="Location level"
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 8px)',
                  right: 64,
                  zIndex: 50,
                  minWidth: 220,
                  background: '#fff',
                  border: '1px solid #e7e5e4',
                  borderRadius: 14,
                  boxShadow: '0 16px 38px rgba(13,148,136,0.20)',
                  padding: 6,
                }}
              >
                <div
                  style={{ padding: '6px 10px 8px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#a8a29e' }}
                >
                  Show results for
                </div>
                {levelOptions.map((opt) => {
                  const selected = level === opt.value
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      role="option"
                      aria-selected={selected}
                      disabled={opt.disabled}
                      onClick={() => pickLevel(opt.value)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        width: '100%',
                        textAlign: 'left',
                        background: selected ? '#f0fdfa' : 'none',
                        border: 'none',
                        borderRadius: 9,
                        padding: '9px 12px',
                        fontSize: 14.5,
                        fontWeight: selected ? 700 : 500,
                        color: opt.disabled ? '#d6d3d1' : selected ? TEAL_DARK : '#44403c',
                        cursor: opt.disabled ? 'not-allowed' : 'pointer',
                        fontFamily: 'inherit',
                      }}
                      onMouseEnter={(e) => {
                        if (!selected && !opt.disabled) e.currentTarget.style.background = '#f5f5f4'
                      }}
                      onMouseLeave={(e) => {
                        if (!selected && !opt.disabled) e.currentTarget.style.background = 'none'
                      }}
                    >
                      <span>{opt.label}</span>
                      {selected && <span style={{ color: TEAL }} aria-hidden>✓</span>}
                    </button>
                  )
                })}
                <div style={{ borderTop: '1px solid #f5f5f4', marginTop: 4, paddingTop: 4 }}>
                  <button
                    type="button"
                    onClick={() => {
                      setLevelOpen(false)
                      setChangingLoc(true)
                    }}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left', background: 'none', border: 'none', borderRadius: 9, padding: '9px 12px', fontSize: 13.5, fontWeight: 600, color: TEAL_DARK, cursor: 'pointer', fontFamily: 'inherit' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#f5f5f4')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                  >
                    📍 {locState ? 'Change location' : 'Set your location'}
                  </button>
                </div>
              </div>
            )}

            {/* Change-location popup — the centered modal the home page used to
                use. Wraps the real geocoder (AddressLookup → api/routes/geocode.py
                → Nominatim). On a hit we swap the saved location and let `level`
                recompute to its natural scope for the new place. */}
            {changingLoc && (
              <div
                className="fixed inset-0 bg-black/50 z-[60] flex items-center justify-center p-4"
                onClick={() => {
                  setChangingLoc(false)
                  setUncoveredPick(null)
                }}
                style={{ animation: 'fadeIn 150ms ease' }}
              >
                <div
                  className="bg-white rounded-2xl shadow-2xl p-8 max-w-2xl w-full"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-2xl font-bold" style={{ color: TEAL_DARK, fontFamily: 'Playfair Display, Georgia, serif' }}>
                      {locState ? 'Change your location' : 'Find your community'}
                    </h2>
                    <button
                      type="button"
                      onClick={() => {
                        setChangingLoc(false)
                        setUncoveredPick(null)
                      }}
                      aria-label="Close"
                      style={{ padding: 8, borderRadius: 10, border: 'none', background: 'none', color: '#78716c', fontSize: 20, cursor: 'pointer', lineHeight: 1 }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = '#f5f5f4')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                    >
                      ✕
                    </button>
                  </div>
                  <p className="text-gray-600 mb-6">
                    {locState
                      ? `Currently set to ${[locCity, locState].filter(Boolean).join(', ')}. Enter a new address to change your location.`
                      : 'Enter your address to see the meetings, votes, spending, and debates near you.'}
                  </p>

                  {/* "Not loaded yet" notice — shown when the picked place isn't one
                      of our launch cities. We don't drop the user into an empty
                      scope; we tell them honestly and offer the loaded cities. */}
                  {uncoveredPick && (
                    <div
                      className="mb-6 rounded-xl border p-4"
                      style={{ borderColor: '#fcd34d', background: '#fffbeb' }}
                      role="status"
                    >
                      <p className="text-sm font-semibold" style={{ color: '#92400e' }}>
                        🚧 We haven&apos;t loaded {uncoveredLabel(uncoveredPick) || 'that area'} yet
                      </p>
                      <p className="mt-1 text-sm" style={{ color: '#92400e' }}>
                        Civic data for {uncoveredLabel(uncoveredPick) || 'this location'} is on the way.
                        For now, you can explore one of our launch cities:
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {LAUNCH_CITIES.map((c) => (
                          <Link
                            key={`${c.city}-${c.state}`}
                            to={`/search?state=${c.state}`}
                            onClick={() => {
                              setChangingLoc(false)
                              setUncoveredPick(null)
                            }}
                            className="rounded-full bg-white px-3 py-1.5 text-sm font-medium"
                            style={{ border: '1px solid #fcd34d', color: '#92400e' }}
                          >
                            {c.city}, {c.state}
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}

                  <AddressLookup
                    onUncovered={(loc) => {
                      // Block the switch and surface our custom in-modal notice
                      // rather than dropping the user into an empty scope.
                      setUncoveredPick({ city: loc.city, state: loc.state })
                    }}
                    onLocationFound={(loc) => {
                      setUncoveredPick(null)
                      setLocation(loc)
                      levelPicked.current = false
                      setChangingLoc(false)
                    }}
                  />
                </div>
              </div>
            )}

            {/* Live typeahead dropdown — real /api/search results, scoped to the
                active place. mouseDown-preventDefault keeps focus so onClick wins
                the blur race. */}
            {showSuggest && (
              <div
                style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  zIndex: 40,
                  background: '#fff',
                  border: `2px solid ${TEAL}`,
                  borderTop: 'none',
                  borderRadius: '0 0 16px 16px',
                  boxShadow: '0 18px 40px rgba(13,148,136,0.18)',
                  overflow: 'hidden',
                }}
                onMouseDown={(e) => e.preventDefault()}
              >
                {suggestions.length > 0 ? (
                  suggestions.map((s, i) => (
                    <button
                      key={`${s.type}-${s.url}-${i}`}
                      onClick={() => selectSuggestion(s)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        width: '100%',
                        textAlign: 'left',
                        background: 'transparent',
                        border: 'none',
                        borderTop: i === 0 ? 'none' : '1px solid #f5f5f4',
                        padding: '11px 18px',
                        cursor: 'pointer',
                        fontFamily: 'inherit',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = '#f0fdfa')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      <span style={{ fontSize: 17, flexShrink: 0 }}>{SUGGEST_ICON[s.type] ?? '🔎'}</span>
                      <span style={{ minWidth: 0, flex: 1 }}>
                        <span style={{ display: 'block', fontSize: 15, fontWeight: 600, color: INK, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {s.title}
                        </span>
                        {s.subtitle && (
                          <span style={{ display: 'block', fontSize: 12.5, color: '#78716c', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {s.subtitle}
                          </span>
                        )}
                      </span>
                      <span className="font-mono-x" style={{ fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#a8a29e', flexShrink: 0 }}>
                        {s.type}
                      </span>
                    </button>
                  ))
                ) : (
                  <div style={{ padding: '12px 18px', fontSize: 13.5, color: '#78716c' }}>
                    {suggestFetching ? 'Searching…' : `No quick matches — press Enter to search everything.`}
                  </div>
                )}
                <button
                  onClick={() => runSearch()}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    width: '100%',
                    textAlign: 'left',
                    background: '#fafaf9',
                    border: 'none',
                    borderTop: '1px solid #e7e5e4',
                    padding: '11px 18px',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    fontSize: 13.5,
                    fontWeight: 600,
                    color: TEAL_DARK,
                  }}
                >
                  🔍 Search everything for “{query.trim()}” →
                </button>
              </div>
            )}
          </div>

          {/* ── Browse pills: dropdown flyout previews, right under the search.
              Each pill previews its top ~5 items (questions/topics/causes) from
              the warehouse — no fabricated rows. ── */}
          <div style={{ display: 'flex', flexWrap: 'nowrap', gap: 10, marginTop: 16, justifyContent: 'center' }}>
            {[
              {
                key: 'questions' as const,
                name: 'Browse questions',
                icon: '⚖️',
                count: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.questions]?.transcript_count ?? null,
                hasTranscripts: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.questions]?.has_transcripts ?? true,
                order: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.questions]?.order ?? Number.MAX_SAFE_INTEGER,
                to: '/policy-questions',
                seeAllLabel: 'questions',
                desc: 'Open policy questions across jurisdictions.',
                header: '📌 Pinned questions',
                items: (browseTopItems?.question ?? [])
                  .filter((q) => !!q.entity_name)
                  .map((q) => ({
                    key: q.entity_id,
                    label: q.entity_name,
                    transcripts: q.transcript_count,
                    onSelect: () =>
                      navigate(`/policy-question/${q.entity_id}`, { state: { fromHome: true } }),
                  })),
              },
              {
                key: 'topics' as const,
                name: 'Browse topics',
                icon: '🗂️',
                count: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.topics]?.transcript_count ?? null,
                hasTranscripts: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.topics]?.has_transcripts ?? true,
                order: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.topics]?.order ?? Number.MAX_SAFE_INTEGER,
                // Carry the saved location into the Topics browse so it lands
                // scoped to that place — the city when we have one (so e.g.
                // Atlanta filters to Atlanta, not all of GA), else the state.
                // No location set → the full national catalog.
                to: locState
                  ? `/browse-topics?state=${encodeURIComponent(locState)}${
                      locCity ? `&city=${encodeURIComponent(locCity)}` : ''
                    }`
                  : '/browse-topics',
                seeAllLabel: 'topics',
                desc: 'Everything discussed in public meetings.',
                header: 'Top topics',
                items: (browseTopItems?.topic ?? []).map((t) => ({
                  key: t.entity_id,
                  label: t.entity_name,
                  transcripts: t.transcript_count,
                  onSelect: () =>
                    navigate(
                      locState
                        ? `/browse-topics?state=${encodeURIComponent(locState)}${
                            locCity ? `&city=${encodeURIComponent(locCity)}` : ''
                          }`
                        : '/browse-topics',
                      { state: { fromHome: true } },
                    ),
                })),
              },
              {
                key: 'causes' as const,
                name: 'Browse causes',
                icon: '💚',
                count: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.causes]?.transcript_count ?? null,
                hasTranscripts: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.causes]?.has_transcripts ?? true,
                order: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.causes]?.order ?? Number.MAX_SAFE_INTEGER,
                // Carry the saved location into Browse Causes (same as Topics)
                // so the cause pills + decision cards land scoped to that place.
                to: locState
                  ? `/browse-causes?state=${encodeURIComponent(locState)}${
                      locCity ? `&city=${encodeURIComponent(locCity)}` : ''
                    }`
                  : '/browse-causes',
                seeAllLabel: 'causes',
                desc: 'Local nonprofits, grants & charitable work.',
                header: 'Top causes',
                items: (browseTopItems?.cause ?? []).map((c) => ({
                  key: c.entity_id,
                  label: c.entity_name,
                  transcripts: c.transcript_count,
                  onSelect: () =>
                    navigate(
                      locState
                        ? `/browse-causes?state=${encodeURIComponent(locState)}${
                            locCity ? `&city=${encodeURIComponent(locCity)}` : ''
                          }`
                        : '/browse-causes',
                      { state: { fromHome: true } },
                    ),
                })),
              },
              {
                key: 'places' as const,
                name: 'Browse places',
                icon: '📍',
                count: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.places]?.transcript_count ?? null,
                hasTranscripts: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.places]?.has_transcripts ?? true,
                order: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.places]?.order ?? Number.MAX_SAFE_INTEGER,
                // Carry the saved location into the Places browse so it lands
                // pre-filtered (e.g. "Atlanta" → ?state=GA&city=Atlanta). City
                // takes precedence over county; state is included to disambiguate.
                // No location set → plain /jurisdictions browse.
                to: (() => {
                  const p = new URLSearchParams()
                  if (locState) p.set('state', locState)
                  if (locCity) p.set('city', locCity)
                  else if (location?.county) p.set('county', location.county)
                  const qs = p.toString()
                  return qs ? `/jurisdictions?${qs}` : '/jurisdictions'
                })(),
                seeAllLabel: 'places',
                desc: 'Cities, counties & districts with public records.',
                header: 'Top places',
                items: (browseTopItems?.place ?? []).map((p) => ({
                  key: p.entity_id,
                  label: p.entity_name,
                  transcripts: p.transcript_count,
                  onSelect: () =>
                    navigate(`/jurisdiction/${encodeURIComponent(p.entity_id)}/meetings`, {
                      state: { fromHome: true },
                    }),
                })),
              },
            ]
              // Order the cards to match the API's category ordering
              // (transcript_count desc, `place` pinned far right). Unknown/missing
              // entity types fall to the end via Number.MAX_SAFE_INTEGER.
              .slice()
              .sort((a, b) => a.order - b.order)
              .map((b) => {
              const open = browseOpen === b.key
              return (
                <div
                  key={b.key}
                  style={{ position: 'relative' }}
                  onMouseEnter={isTouch ? undefined : () => setBrowseOpen(b.key)}
                  onMouseLeave={isTouch ? undefined : () => setBrowseOpen((p) => (p === b.key ? null : p))}
                >
                  {/* One visual pill, two actions: the main area drills down to
                      the full page; the chevron toggles the preview combo. Hover
                      also opens the combo on desktop (handlers on the wrapper). */}
                  <div
                    style={{ display: 'flex', alignItems: 'stretch', background: '#fff', border: `1px solid ${open ? TEAL : '#e7e5e4'}`, boxShadow: open ? '0 4px 12px rgba(28,25,23,0.07)' : 'none', borderRadius: 999, overflow: 'hidden', transition: 'border-color 120ms ease, box-shadow 120ms ease' }}
                  >
                    <button
                      title={b.desc}
                      onClick={() => navigate(b.to, { state: { fromHome: true } })}
                      style={{ background: 'none', border: 'none', padding: '9px 6px 9px 10px', cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 10 }}
                    >
                      <span className="font-display" style={{ fontSize: 16.5, fontWeight: 700, color: INK, whiteSpace: 'nowrap' }}>
                        {b.name}
                      </span>
                      {/* Badge = real distinct-transcript count for this
                          category (from /api/browse/summary). The unit is made
                          explicit so the number reads as transcripts, not an
                          ambiguous tally. Causes have no transcript linkage in
                          the data → honest em-dash, never a fabricated "0". */}
                      {b.hasTranscripts && b.count != null && b.count > 0 ? (
                        <span
                          className="font-mono-x"
                          title={`${b.count.toLocaleString('en-US')} meetings`}
                          aria-label={`${b.count.toLocaleString('en-US')} meetings`}
                          style={{ display: 'inline-flex', alignItems: 'baseline', gap: 4, fontSize: 11, fontWeight: 600, background: '#f5f5f4', border: '1px solid #e7e5e4', borderRadius: 999, padding: '1px 8px', color: '#57534e' }}
                        >
                          {b.count.toLocaleString('en-US')}
                          <span style={{ fontSize: 9.5, fontWeight: 600, color: '#a8a29e', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            meetings
                          </span>
                        </span>
                      ) : (
                        !b.hasTranscripts && (
                          <span
                            className="font-mono-x"
                            title="No linked transcripts yet"
                            aria-label="No linked transcripts yet"
                            style={{ fontSize: 11, fontWeight: 600, background: '#f5f5f4', border: '1px solid #e7e5e4', borderRadius: 999, padding: '1px 8px', color: '#a8a29e' }}
                          >
                            —
                          </span>
                        )
                      )}
                    </button>
                    <button
                      aria-label={open ? `Hide top ${b.seeAllLabel}` : `Show top ${b.seeAllLabel}`}
                      aria-expanded={open}
                      aria-haspopup="true"
                      onClick={() => setBrowseOpen((p) => (p === b.key ? null : b.key))}
                      style={{ background: open ? '#f0fdfa' : 'none', border: 'none', borderLeft: '1px solid #f0efed', padding: '0 12px', cursor: 'pointer', fontFamily: 'inherit', color: TEAL_DARK, fontWeight: 700, fontSize: 11, display: 'flex', alignItems: 'center' }}
                    >
                      {open ? '▴' : '▾'}
                    </button>
                  </div>

                  {open && b.items.length > 0 && (
                    <div
                      role="menu"
                      aria-label={b.name}
                      style={{
                        position: 'absolute',
                        top: '100%',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        zIndex: 55,
                        width: b.key === 'questions' ? 330 : 280,
                        maxWidth: 'calc(100vw - 32px)',
                        // Transparent bridge over the gap so the cursor can travel
                        // from the pill into the menu without tripping mouseleave.
                        paddingTop: 6,
                        textAlign: 'left',
                      }}
                    >
                      <div
                        style={{
                          background: '#fff',
                          border: '1px solid #e7e5e4',
                          borderRadius: 12,
                          boxShadow: '0 10px 30px rgba(28,25,23,0.14)',
                          overflow: 'hidden',
                        }}
                      >
                        <div className="font-mono-x" style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: b.key === 'questions' ? '#ea580c' : '#a8a29e', padding: '11px 16px 7px' }}>
                          {b.header}
                        </div>
                        {b.items.map((it) => (
                          <button
                            key={it.key}
                            role="menuitem"
                            onClick={() => {
                              setBrowseOpen(null)
                              it.onSelect()
                            }}
                            style={{ display: 'flex', alignItems: 'center', gap: 9, width: '100%', textAlign: 'left', background: 'none', border: 'none', borderTop: '1px solid #f5f5f4', padding: '9px 16px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 13.5, color: INK }}
                            onMouseEnter={(e) => (e.currentTarget.style.background = '#fafaf9')}
                            onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                          >
                            {/* Wrap to at most two lines (then ellipsize) rather
                                than single-line truncation — question prompts are
                                full sentences and were getting cut mid-word.
                                minWidth:0 lets the flex child actually wrap. */}
                            <span
                              style={{
                                flex: 1,
                                minWidth: 0,
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                lineHeight: 1.35,
                              }}
                            >
                              {it.label}
                            </span>
                            {/* Real distinct-transcript count for this item
                                (from /api/browse/top-items). Shown for every
                                category including causes — causes are genuinely
                                0 (no transcript linkage), an honest real value. */}
                            <span
                              className="font-mono-x"
                              title={`${it.transcripts.toLocaleString('en-US')} transcripts`}
                              style={{ flexShrink: 0, display: 'inline-flex', alignItems: 'baseline', gap: 3, fontSize: 11, fontWeight: 600, color: '#a8a29e' }}
                            >
                              {it.transcripts.toLocaleString('en-US')}
                              <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>tx</span>
                            </span>
                          </button>
                        ))}
                        <button
                          onClick={() => {
                            setBrowseOpen(null)
                            navigate(b.to, { state: { fromHome: true } })
                          }}
                          style={{ display: 'block', width: '100%', textAlign: 'left', background: '#fafaf9', border: 'none', borderTop: '1px solid #e7e5e4', padding: '10px 16px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 12.5, fontWeight: 600, color: TEAL_DARK }}
                        >
                          {/* The badge count is a transcript count, not an
                              entity count, so it is intentionally omitted from
                              this "Browse all {entity}" label to avoid
                              mislabeling transcripts as the entity. */}
                          Browse all {b.seeAllLabel} →
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>

        </section>

        {/* ── Contested + Raised Eyebrows — two dedicated lens sections (REAL
            lens cards). The Contested header carries the single shared
            time-window selector, which drives both the lenses query and Money
            Moves below.

            Fallback: when this place HAS recent (analyzed) meetings but BOTH
            lenses come back empty — i.e. no analysis has surfaced a contested
            vote or a flagged pattern yet — we hide the two "No activity" cards
            and instead show the most recent meetings. That's a real, useful
            signal for the user rather than a pair of dead-end empty states.
            The shared time-window selector moves into that fallback header so
            Money Moves below always keeps its control. ── */}
        {(() => {
          const contestedLens = lensById['contested']
          const flagsLens = lensById['flags']
          const contestedCards =
            contestedLens && !contestedLens.placeholder ? contestedLens.cards.slice(0, 6) : []
          const flagsCards = flagsLens && !flagsLens.placeholder ? flagsLens.cards.slice(0, 6) : []
          // Only treat "empty" as real once the lenses query has resolved, so we
          // don't flash the meetings fallback while the lenses are still loading.
          const lensesEmpty = !!lensesData && contestedCards.length === 0 && flagsCards.length === 0
          const showRecentFallback = lensesEmpty && recentMeetings.length > 0

          // The single shared time-window selector — rendered in whichever
          // section heads the block so Money Moves below always has its control.
          const whenSelector = (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginLeft: 'auto' }}>
              {WHEN.map((w) => (
                <Chip key={w.label} active={when.label === w.label} onClick={() => setWhen(w)}>
                  {w.label}
                </Chip>
              ))}
            </div>
          )

          if (showRecentFallback) {
            const fmtMeetingDate = (iso: string | null): string => {
              if (!iso) return ''
              const d = new Date(`${iso}T00:00:00`)
              return Number.isNaN(d.getTime())
                ? ''
                : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
            }
            return (
              <section style={{ marginTop: 30 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: '#eff6ff', display: 'grid', placeItems: 'center', fontSize: 21 }}>
                    🗓️
                  </div>
                  <div style={{ flex: 1, minWidth: 200 }}>
                    <h2 className="font-display" style={{ fontSize: 22, fontWeight: 700, margin: 0, color: '#2563eb' }}>
                      Recent meetings
                    </h2>
                    <div style={{ fontSize: 14, color: '#78716c' }}>The latest analyzed meetings · 📍 {placeLabel}</div>
                  </div>
                  {whenSelector}
                </div>

                <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
                  {recentMeetings.map((m) => {
                    const place = [m.city || m.jurisdiction || '', m.state_code].filter(Boolean).join(', ')
                    const date = fmtMeetingDate(m.date)
                    return (
                      <button
                        key={m.meeting_id}
                        onClick={() => navigate(`/meetings/${m.meeting_id}`, { state: { fromHome: true } })}
                        style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', background: '#fff', border: '1px solid #e7e5e4', borderRadius: 14, padding: 0, overflow: 'hidden', cursor: 'pointer', fontFamily: 'inherit' }}
                      >
                        {m.video_id && <MeetingThumbnail videoId={m.video_id} alt={m.title ?? undefined} />}
                        <div style={{ padding: '14px 16px' }}>
                          <div className="clamp2" style={{ fontSize: 15, fontWeight: 700, color: INK, lineHeight: 1.3 }}>
                            {m.title || 'Untitled meeting'}
                          </div>
                          <div style={{ marginTop: 6, fontSize: 12.5, color: '#78716c', display: 'flex', flexWrap: 'wrap', gap: '2px 10px' }}>
                            {place && <span>📍 {place}</span>}
                            {date && <span>{date}</span>}
                          </div>
                          {m.decision_count > 0 && (
                            <div style={{ marginTop: 8 }}>
                              <span style={{ display: 'inline-block', fontSize: 11.5, fontWeight: 600, color: TEAL_DARK, background: '#ecfdf5', borderRadius: 999, padding: '2px 9px' }}>
                                {m.decision_count} {m.decision_count === 1 ? 'decision' : 'decisions'}
                              </span>
                            </div>
                          )}
                        </div>
                      </button>
                    )
                  })}
                </div>
              </section>
            )
          }

          const renderLens = (id: 'contested' | 'flags', withSelector: boolean) => {
            const meta = SIGNAL_META[id]
            const cards = id === 'contested' ? contestedCards : flagsCards
            return (
              <section style={{ marginTop: 30 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: meta.bg, display: 'grid', placeItems: 'center', fontSize: 21 }}>
                    {meta.icon}
                  </div>
                  <div style={{ flex: 1, minWidth: 200 }}>
                    <h2 className="font-display" style={{ fontSize: 22, fontWeight: 700, margin: 0, color: meta.color }}>
                      {meta.name}
                    </h2>
                    <div style={{ fontSize: 14, color: '#78716c' }}>{meta.desc} · 📍 {placeLabel}</div>
                  </div>
                  {withSelector && whenSelector}
                </div>

                <div style={{ marginTop: 16 }}>
                  {cards.length > 0 ? (
                    <LensCarousel
                      cards={cards}
                      lens={{ id, em: meta.icon, label: meta.name, clr: meta.color }}
                      unscoped={national}
                    />
                  ) : (
                    <div style={{ background: '#fff', border: '1px solid #e7e5e4', borderRadius: 14, padding: '28px 16px', textAlign: 'center', color: '#78716c', fontSize: 14 }}>
                      No {meta.name} activity in {placeLabel} for {when.label.toLowerCase()}.
                    </div>
                  )}
                </div>
              </section>
            )
          }

          // "What's New" — the most recent meetings in this place, rendered in
          // the same tiles the topic lenses use, regardless of whether each
          // meeting produced a decision. Sits at the top of the block in the
          // normal case; in the empty-lenses fallback the "Recent meetings" grid
          // above already covers these, so we don't double up.
          const whatsNewCards = recentMeetings.map(meetingToCard)
          const whatsNewSection =
            whatsNewCards.length > 0 ? (
              <section style={{ marginTop: 30 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: '#eff6ff', display: 'grid', placeItems: 'center', fontSize: 21 }}>
                    🗓️
                  </div>
                  <div style={{ flex: 1, minWidth: 200 }}>
                    <h2 className="font-display" style={{ fontSize: 22, fontWeight: 700, margin: 0, color: '#2563eb' }}>
                      What&rsquo;s New
                    </h2>
                    <div style={{ fontSize: 14, color: '#78716c' }}>
                      The most recent meetings, whatever the outcome · 📍 {placeLabel}
                    </div>
                  </div>
                </div>
                <div style={{ marginTop: 16 }}>
                  <LensCarousel
                    cards={whatsNewCards}
                    lens={{ id: 'whats-new', em: '🗓️', label: "What's New", clr: '#2563eb' }}
                    unscoped={national}
                  />
                </div>
              </section>
            ) : null

          return (
            <>
              {whatsNewSection}
              {renderLens('contested', true)}
              {renderLens('flags', false)}
            </>
          )
        })()}

        {/* ── Money Moves — compact one-line summary (REAL /api/money-flow
            headline figure) that drills down into the full tabbed Sankey in a
            modal, so it no longer dominates the page. ── */}
        <section style={{ marginTop: 30, paddingBottom: 44 }}>
          <MoneyMovesTeaser
            national={national}
            stateCode={stateCode}
            city={city}
            county={location?.county || undefined}
            window={when.window}
            placeLabel={placeLabel}
          />
        </section>
      </main>

      {/* ── How It Works (ported from the original home page, restyled for v9).
          Header format matches the sibling "Our Impact" section: section name as
          the centered <h2>, no mono eyebrow. ── */}
      <section id="how-it-works" style={{ background: '#fff', borderTop: '1px solid #e7e5e4', padding: '40px 24px', scrollMarginTop: 72 }}>
        <div style={{ maxWidth: 1180, margin: '0 auto' }}>
          <div style={{ textAlign: 'center', maxWidth: 720, margin: '0 auto 18px' }}>
            <h2 className="font-display" style={{ fontSize: 'clamp(26px, 3.6vw, 34px)', fontWeight: 800, margin: 0, color: INK }}>
              How it works
            </h2>
            <p style={{ fontSize: 15, color: '#57534e', lineHeight: 1.45, marginTop: 8 }}>
              Take real action on local issues — starting with your personal impact. Choose a cause, make a plan,
              find help when someone needs direct support, track the decisions that matter, and build on open data.
            </p>
          </div>

          <StepZeroImpact />

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, alignItems: 'stretch' }}>
            {([
              {
                icon: '📍', title: 'Choose a cause, topic, place or question', hash: 'explore-causes',
                items: [
                  { kind: 'check', label: 'School Quality' },
                  { kind: 'check', label: 'Property Taxes' },
                  { kind: 'check', label: 'Northport Schools' },
                  { kind: 'check', label: 'Traffic & Roads' },
                  { kind: 'arrow', label: 'Why are my taxes rising?' },
                ],
              },
              {
                icon: '💚', title: 'Find help & allies', hash: 'explore-find-help',
                items: [
                  { kind: 'check', label: 'Find Allies on Issues' },
                  { kind: 'check', label: 'Neighborhood Groups' },
                  { kind: 'check', label: 'Advocacy Support' },
                  { kind: 'check', label: 'Local Networks' },
                  { kind: 'arrow', label: 'Family Resources' },
                ],
              },
              {
                icon: '📊', title: 'Track decisions', hash: 'explore-track-decisions',
                items: [
                  { kind: 'check', label: 'School Board Votes' },
                  { kind: 'check', label: 'Neighborhood Changes' },
                  { kind: 'check', label: 'Public Safety' },
                  { kind: 'check', label: 'New Developments Near Me' },
                ],
              },
              {
                icon: '🧩', title: 'Build with data', hash: 'explore-build',
                items: [
                  { kind: 'check', label: 'Local Trends' },
                  { kind: 'check', label: 'Impact Maps' },
                  { kind: 'arrow', label: 'Easy Tools' },
                ],
              },
            ] as { icon: string; title: string; hash: string; items: { kind: 'check' | 'arrow' | 'note'; label: string }[] }[]).map((step) => (
              <button
                key={step.title}
                onClick={() => navigate(`/explore#${step.hash}`)}
                style={{ textAlign: 'left', background: '#fff', border: '1px solid #e7e5e4', borderRadius: 14, padding: 15, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', flexDirection: 'column', gap: 0, boxShadow: '0 1px 2px rgba(28,25,23,0.04)' }}
              >
                <span style={{ width: 36, height: 36, borderRadius: 10, background: '#f0fdfa', display: 'grid', placeItems: 'center', fontSize: 18, marginBottom: 9 }}>
                  {step.icon}
                </span>
                <span className="font-display" style={{ fontSize: 16, fontWeight: 700, color: INK, lineHeight: 1.25 }}>{step.title}</span>
                <ul style={{ listStyle: 'none', margin: '9px 0 0', padding: 0, display: 'flex', flexDirection: 'column', gap: 5 }}>
                  {step.items.map((it) => (
                    <li
                      key={it.label}
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 7,
                        fontSize: 13,
                        lineHeight: 1.4,
                        color: it.kind === 'arrow' ? TEAL_DARK : it.kind === 'note' ? '#78716c' : '#44403c',
                        fontWeight: it.kind === 'arrow' ? 700 : it.kind === 'note' ? 600 : 400,
                      }}
                    >
                      <span aria-hidden style={{ flexShrink: 0, color: it.kind === 'arrow' ? TEAL_DARK : it.kind === 'note' ? '#a8a29e' : '#059669', fontWeight: 700 }}>
                        {it.kind === 'arrow' ? '→' : it.kind === 'note' ? '•' : '✓'}
                      </span>
                      <span>{it.label}</span>
                    </li>
                  ))}
                </ul>
              </button>
            ))}
          </div>

          <div style={{ textAlign: 'center', marginTop: 18, fontSize: 15, color: '#57534e' }}>
            <span style={{ fontWeight: 700, color: INK }}>Ready to act?</span>{' '}
            Show up at meetings · Write letters · Change the process
          </div>
        </div>
      </section>

      {/* ── Our Impact / Our Mission (ported from the original home page) ── */}
      <section id="impact" style={{ background: '#fafaf9', borderTop: '1px solid #e7e5e4', padding: '56px 24px', scrollMarginTop: 72 }}>
        <div style={{ maxWidth: 1180, margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <h2 className="font-display" style={{ fontSize: 'clamp(26px, 3.6vw, 34px)', fontWeight: 800, margin: 0, color: INK }}>
              Our Impact
            </h2>
            <p style={{ fontSize: 16, color: '#57534e', margin: '12px auto 18px', maxWidth: 640 }}>
              One platform connecting residents, leaders, and funders to what&apos;s really happening on the ground.
            </p>
            <button
              onClick={() => setShowStrategicPlan(true)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: TEAL, color: '#fff', border: 'none', borderRadius: 999, padding: '11px 22px', fontSize: 14.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
            >
              📄 View Our Strategic Plan
            </button>
          </div>

          <div style={{ maxWidth: 720, margin: '0 auto', textAlign: 'center', background: '#fff', border: '1px solid #e7e5e4', borderRadius: 18, padding: '36px 28px' }}>
            <h3 className="font-display" style={{ fontSize: 'clamp(22px, 3vw, 28px)', fontWeight: 800, margin: 0, color: INK }}>
              Our Mission
            </h3>
            <p style={{ fontSize: 15, color: '#57534e', margin: '10px 0 14px', fontWeight: 600 }}>
              CommunityOne: One Map for Every Community
            </p>
            <p style={{ fontSize: 15.5, color: '#44403c', lineHeight: 1.6, marginBottom: 12 }}>
              Every person deserves to find the help they need and have a voice in the decisions that shape their lives.
              But public resources are scattered, gaps go unseen, and communities are left navigating alone.
            </p>
            <p style={{ fontSize: 15.5, color: '#44403c', lineHeight: 1.6, marginBottom: 22 }}>
              CommunityOne changes that. One platform connects residents, leaders, and funders to what&apos;s really
              happening on the ground — so no community has to fight just to be seen.
            </p>
            <button
              onClick={() => navigate('/explore')}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: INK, color: '#fff', border: 'none', borderRadius: 10, padding: '11px 20px', fontSize: 14.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
            >
              Start Exploring →
            </button>
          </div>
        </div>
      </section>

      {/* Strategic Plan PDF — lightweight modal (real PDF in public/pdf). */}
      {showStrategicPlan && (
        <div
          onClick={() => setShowStrategicPlan(false)}
          style={{ position: 'fixed', inset: 0, zIndex: 70, background: 'rgba(15,43,43,0.5)', backdropFilter: 'blur(2px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ width: '100%', maxWidth: 980, height: '85vh', background: '#fff', borderRadius: 18, overflow: 'hidden', display: 'flex', flexDirection: 'column', boxShadow: '0 20px 50px rgba(0,0,0,0.3)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: '1px solid #e7e5e4' }}>
              <span className="font-display" style={{ fontSize: 16, fontWeight: 700, color: INK }}>
                📄 CommunityOne Strategic Plan
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <a href="/pdf/c1_strategic_plan.PDF" target="_blank" rel="noopener noreferrer" style={{ fontSize: 13, fontWeight: 600, color: TEAL_DARK }}>
                  Open in new tab
                </a>
                <button onClick={() => setShowStrategicPlan(false)} aria-label="Close" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: '#78716c', lineHeight: 1 }}>
                  ✕
                </button>
              </div>
            </div>
            <iframe src="/pdf/c1_strategic_plan.PDF" title="CommunityOne Strategic Plan" style={{ flex: 1, width: '100%', border: 'none' }} />
          </div>
        </div>
      )}

      {/* ── Why people use it (footer) ── */}
      <footer style={{ background: '#fff', borderTop: '1px solid #e7e5e4' }}>
        <div style={{ maxWidth: 1180, margin: '0 auto', padding: '9px 24px', display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12.5, color: '#a8a29e' }}>CommunityOne · a 501(c)(3) nonprofit · Tuscaloosa, Alabama</span>
        </div>
      </footer>
    </div>
  )
}
