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
import MoneyGameModal from '../components/MoneyGameModal'
import FollowTheMoney from '../components/FollowTheMoney'
import { fetchPolicyQuestions } from '../api/policyQuestions'
import { useLocation as useLocationContext } from '../contexts/LocationContext'
import SiteHeader from '../components/SiteHeader'

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
// Display order for the "Explore by signal" rail.
const SIGNAL_ORDER = ['contested', 'money', 'flags', 'soon', 'next']

const TOPICS = [
  '👨‍👩‍👧 Family First',
  '⛪ Faith & Community',
  '🏛️ Charitable Impact',
  '🏘️ Neighborhood Life',
  '🎓 Education',
  '💼 Local Economy',
]

const WHEN: { label: string; window: string }[] = [
  { label: 'Past month', window: 'month' },
  { label: 'Past 3 months', window: 'quarter' },
  { label: 'Past year', window: 'year' },
  { label: 'All time', window: 'all' },
]

// Left-side search scope. `types` is the comma list handed to /search (UnifiedSearch
// reads ?types=); 'all' sends no types param so the search spans everything.
const SEARCH_CATEGORIES: { id: string; label: string; types: string }[] = [
  { id: 'all', label: 'All', types: '' },
  { id: 'meetings', label: 'Meetings', types: 'meetings' },
  { id: 'transcripts', label: 'Transcripts', types: 'documents' },
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
function MonoLabel({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <span
      className="font-mono-x"
      style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#78716c', fontWeight: 500, ...style }}
    >
      {children}
    </span>
  )
}

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

// A single story row (real lens card), prototype-styled.
function StoryRow({ card, lensId, first }: { card: LensCard; lensId: string; first: boolean }) {
  const meta = SIGNAL_META[lensId]
  const navigate = useNavigate()
  const go = () => card.url && navigate(card.url)
  return (
    <article
      onClick={go}
      style={{
        padding: '11px 16px',
        borderTop: first ? 'none' : '1px solid #f5f5f4',
        cursor: card.url ? 'pointer' : 'default',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, flexWrap: 'wrap' }}>
        {meta && (
          <span
            className="font-mono-x"
            style={{
              fontSize: 9.5,
              fontWeight: 600,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: meta.color,
              background: meta.bg,
              borderRadius: 999,
              padding: '2px 8px',
              flexShrink: 0,
            }}
          >
            {meta.icon} {meta.name}
          </span>
        )}
        <h3 className="font-display" style={{ fontSize: 16, fontWeight: 700, margin: 0, lineHeight: 1.25, flex: 1, minWidth: 180 }}>
          {card.headline}
        </h3>
      </div>
      <div className="font-mono-x" style={{ fontSize: 10.5, color: '#78716c', marginTop: 3 }}>
        {[card.jurisdiction, card.date].filter(Boolean).join(' · ')}
      </div>
    </article>
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

// Humanize a primary_theme code (e.g. "public_safety") into display text. UI
// formatting only — no data is invented.
function humanizeTheme(theme: string | null | undefined): string {
  if (!theme || theme === '__unthemed__') return ''
  return theme
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// ── Big questions in your community (REAL curated policy-question registry) ──
// The four featured cross-jurisdiction policy questions. Each links to its real
// detail page. These curated rows carry no reach rollups (instances/jurisdiction
// totals are 0), so we deliberately show NO "N jurisdictions" hint — just the
// question and its theme. Empty/error → render nothing (never a placeholder).
function BigQuestions() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['home-v9-featured-questions'],
    queryFn: () => fetchPolicyQuestions({ featured: true }),
    staleTime: 30 * 60 * 1000,
  })

  const questions = (data ?? []).filter((q) => !!q.canonical_text)
  if (isLoading || isError || questions.length === 0) return null

  return (
    <section style={{ marginTop: 30 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 20 }}>⚖️</span>
        <h2 className="font-display" style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>
          Big questions in your community
        </h2>
        <span style={{ fontSize: 14, color: '#78716c' }}>
          The debates playing out in town halls across the country.
        </span>
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 12,
          marginTop: 12,
        }}
      >
        {questions.map((q) => {
          const theme = humanizeTheme(q.primary_theme)
          return (
            <Link
              key={q.question_id}
              to={`/policy-question/${q.question_id}`}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
                textDecoration: 'none',
                background: '#fff',
                border: '1px solid #e7e5e4',
                borderRadius: 14,
                padding: '16px 18px',
                boxShadow: '0 1px 2px rgba(28,25,23,0.05)',
              }}
            >
              {theme && (
                <span
                  className="font-mono-x"
                  style={{
                    alignSelf: 'flex-start',
                    fontSize: 10,
                    fontWeight: 600,
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    color: TEAL_DARK,
                    background: '#f0fdfa',
                    border: '1px solid #ccfbf1',
                    borderRadius: 999,
                    padding: '2px 9px',
                  }}
                >
                  {theme}
                </span>
              )}
              <span
                className="font-display"
                style={{ fontSize: 17, fontWeight: 700, lineHeight: 1.3, color: INK }}
              >
                {q.canonical_text}
              </span>
              <span style={{ color: TEAL_DARK, fontWeight: 700, fontSize: 14, marginTop: 'auto' }}>
                See both sides →
              </span>
            </Link>
          )
        })}
      </div>
    </section>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function HomeV9() {
  const navigate = useNavigate()
  const { location } = useLocationContext()
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

  // Next-broader level for the "expand search area" affordance shown when a
  // scoped feed comes back empty. `null` once already nationwide.
  const broaderLevel: { value: Level; label: string } | null =
    level === 'city'
      ? locState
        ? { value: 'state', label: `all of ${locState}` }
        : { value: 'national', label: 'nationwide' }
      : level === 'state'
        ? { value: 'national', label: 'nationwide' }
        : null
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
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [activeTopics, setActiveTopics] = useState<string[]>([TOPICS[0]])
  const [activeSignals, setActiveSignals] = useState<string[]>(['contested'])
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

  const toggle = (list: string[], setList: (v: string[]) => void, item: string) =>
    setList(list.includes(item) ? list.filter((x) => x !== item) : [...list, item])

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

  const { data: directoryCounts } = useQuery<{ topics: number | null; causes: number | null; questions: number | null }>({
    queryKey: ['home-v9-directory-counts', stateCode, national],
    queryFn: async () => {
      const params: Record<string, string> = { types: 'topics,causes', limit: '1' }
      if (!national && stateCode) params.state = stateCode
      const [searchRes, questions] = await Promise.all([
        api.get('/search/', { params }).then((r) => r.data).catch(() => null),
        fetchPolicyQuestions().catch(() => [] as unknown[]),
      ])
      const tt = (searchRes?.type_totals ?? {}) as Record<string, number | undefined>
      return {
        topics: tt.topics ?? null,
        causes: tt.causes ?? null,
        questions: Array.isArray(questions) ? questions.length : null,
      }
    },
    staleTime: 5 * 60 * 1000,
  })

  // ── "Search in" category counts (real /api/search type_totals) ──
  // Per-category match counts for the category dropdown, DYNAMIC on the search
  // text: re-runs as the (debounced) query / place changes so each row shows how
  // many real results that scope would return. Fetched lazily (only while the
  // menu is open) with limit=1 — we want `type_totals`, not rows — so it never
  // slows the hero. No fabricated numbers: a type the API doesn't count is blank.
  const { data: catCountsData } = useQuery<Record<string, number>>({
    queryKey: ['home-v9-cat-counts', debouncedQuery, national, stateCode, city],
    queryFn: async () => {
      const params: Record<string, string> = {
        types: 'meetings,documents,decisions,leaders,organizations,causes,questions,topics,bills,grants',
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
  // 'All' sums every counted type; the rest map 1:1 to their type_totals key
  // (c.types). Returns undefined when the API didn't count that type (→ no badge).
  const countForCat = (c: { id: string; types: string }): number | undefined =>
    c.id === 'all'
      ? Object.values(catCounts).reduce<number>((s, n) => s + (n || 0), 0)
      : catCounts[c.types]

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

  // Close-to-Home feed: a flat mix of real cards across lenses, filtered to the
  // active signal selection when the user picks any.
  const feed = useMemo(() => {
    const picked = activeSignals.length > 0 ? activeSignals : SIGNAL_ORDER
    const out: { lensId: string; card: LensCard }[] = []
    for (const id of picked) {
      const l = lensById[id]
      if (l && !l.placeholder) for (const c of l.cards.slice(0, 2)) out.push({ lensId: id, card: c })
    }
    return out.slice(0, 6)
  }, [lensById, activeSignals])

  const activeCount = activeTopics.length + activeSignals.length

  const runSearch = (q?: string) => {
    const term = (q ?? query).trim()
    setSuggestOpen(false)
    const params = new URLSearchParams()
    if (term) params.set('q', term)
    if (cat.types) params.set('types', cat.types)
    if (!national && stateCode) params.set('state', stateCode)
    // Carry the city through so a drill-down from e.g. Tuscaloosa reads
    // "City: Tuscaloosa" rather than just "State: AL" (UnifiedSearch reads ?city=).
    if (!national && city) params.set('city', city)
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
        {/* ── Hero: thesis + search + trending ── */}
        <section style={{ padding: '44px 0 6px', textAlign: 'center' }}>
          <h1
            className="font-display"
            style={{ fontSize: 'clamp(38px, 6.4vw, 60px)', fontWeight: 900, margin: 0, lineHeight: 1.05, letterSpacing: '-0.02em', color: INK }}
          >
            Every local decision, in one place.
          </h1>
          <div style={{ fontSize: 'clamp(16px, 2vw, 19px)', fontWeight: 500, color: '#57534e', maxWidth: 600, margin: '16px auto 0', lineHeight: 1.5 }}>
            Search the meetings, votes, spending, and debates shaping your community.
            <br />
            Free, forever.
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
                        {n != null && (
                          <span
                            className="font-mono-x"
                            style={{ fontSize: 11.5, fontWeight: 600, color: selected ? TEAL : '#a8a29e', fontVariantNumeric: 'tabular-nums' }}
                          >
                            {n.toLocaleString('en-US')}
                          </span>
                        )}
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
                {!locState && (
                  <div style={{ borderTop: '1px solid #f5f5f4', marginTop: 4, paddingTop: 4 }}>
                    <button
                      type="button"
                      onClick={() => {
                        setLevelOpen(false)
                        navigate('/feed-setup')
                      }}
                      style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left', background: 'none', border: 'none', borderRadius: 9, padding: '9px 12px', fontSize: 13.5, fontWeight: 600, color: TEAL_DARK, cursor: 'pointer', fontFamily: 'inherit' }}
                    >
                      📍 Set your location
                    </button>
                  </div>
                )}
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

        </section>

        {/* ── Money hook (compact teal banner; REAL geocode + REAL modal) ── */}
        <MoneyHookBanner />

        {/* ── Big questions in your community (REAL featured policy questions) ── */}
        <BigQuestions />

        {/* ── Money Moves — the "follow the money" flowing Sankey (REAL
            /api/money-flow: public spending / grants / nonprofit economy) ── */}
        <section style={{ marginTop: 30 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 20 }}>💵</span>
            <h2 className="font-display" style={{ fontSize: 22, fontWeight: 700, margin: 0, color: '#059669' }}>
              Money Moves
            </h2>
            <span style={{ fontSize: 14, color: '#78716c' }}>
              Follow the dollars — every flow traced to the record · 📍 {placeLabel}
            </span>
          </div>
          <div style={{ marginTop: 12 }}>
            <FollowTheMoney
              embedded
              national={national}
              stateCode={stateCode}
              city={city}
              county={location?.county || undefined}
              window={when.window}
            />
          </div>
        </section>

        {/* ── Explore by signal + Browse the directory ── */}
        <section style={{ marginTop: 30 }}>
          <h2 className="font-display" style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>
            Explore by signal
          </h2>
          <p style={{ fontSize: 14, color: '#78716c', margin: '5px 0 0', maxWidth: 640 }}>
            Every decision we analyze gets tagged with signals — patterns detected in the public record, so you can follow what matters without reading every agenda.
          </p>

          <div className="hide-scroll" style={{ display: 'flex', gap: 14, overflowX: 'auto', padding: '14px 2px 6px' }}>
            {SIGNAL_ORDER.map((id) => {
              const s = SIGNAL_META[id]
              const lens = lensById[id]
              // Honest empty marker when this signal has no analyzed activity in
              // the current window (e.g. "Moving Fast" is a placeholder lens).
              const empty = !lens || lens.placeholder || lens.cards.length === 0
              return (
                <button
                  key={id}
                  onClick={() => {
                    setActiveSignals([id])
                    document.getElementById('close-to-home')?.scrollIntoView({ behavior: 'smooth' })
                  }}
                  style={{ flex: '0 0 215px', textAlign: 'left', background: '#fff', border: '1px solid #e7e5e4', borderRadius: 14, padding: 16, cursor: 'pointer', fontFamily: 'inherit', opacity: empty ? 0.6 : 1 }}
                >
                  <div style={{ width: 42, height: 42, borderRadius: 11, background: s.bg, display: 'grid', placeItems: 'center', fontSize: 20 }}>
                    {s.icon}
                  </div>
                  <div style={{ fontSize: 16.5, fontWeight: 700, color: s.color, marginTop: 10 }}>{s.name}</div>
                  <div style={{ fontSize: 13, color: '#57534e', marginTop: 4, lineHeight: 1.45 }}>{s.desc}</div>
                  {empty && (
                    <div className="font-mono-x" style={{ fontSize: 10, color: '#a8a29e', marginTop: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      None flagged yet
                    </div>
                  )}
                </button>
              )
            })}
          </div>

          {/* Browse the directory — REAL counts. */}
          <div style={{ marginTop: 14 }}>
            <MonoLabel style={{ color: '#57534e' }}>Or browse the directory</MonoLabel>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 8 }}>
              {[
                { name: 'Topics', icon: '🗂️', count: directoryCounts?.topics, to: '/browse-topics', desc: 'Everything discussed in public meetings.' },
                { name: 'Causes', icon: '💚', count: directoryCounts?.causes, to: '/search?types=causes', desc: 'Local nonprofits, grants & charitable work.' },
                { name: 'Questions', icon: '⚖️', count: directoryCounts?.questions, to: '/policy-questions', desc: 'Open policy questions across jurisdictions.' },
              ].map((b) => (
                <button
                  key={b.name}
                  title={b.desc}
                  onClick={() => navigate(b.to, { state: { fromHome: true } })}
                  style={{ textAlign: 'left', background: '#fff', border: '1px solid #e7e5e4', borderRadius: 14, padding: '10px 16px 10px 12px', cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 10 }}
                >
                  <span style={{ width: 30, height: 30, borderRadius: 8, background: '#f0fdfa', border: '1px solid #ccfbf1', display: 'grid', placeItems: 'center', fontSize: 15, flexShrink: 0 }}>
                    {b.icon}
                  </span>
                  <span style={{ minWidth: 0 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="font-display" style={{ fontSize: 16.5, fontWeight: 700, color: INK }}>
                        {b.name}
                      </span>
                      {b.count != null && b.count > 0 && (
                        <span
                          className="font-mono-x"
                          style={{ fontSize: 11, fontWeight: 600, background: '#f5f5f4', border: '1px solid #e7e5e4', borderRadius: 999, padding: '1px 8px', color: '#57534e' }}
                        >
                          {b.count.toLocaleString('en-US')}
                        </span>
                      )}
                    </span>
                    <span style={{ display: 'block', fontSize: 11.5, color: '#78716c', marginTop: 1 }}>{b.desc}</span>
                  </span>
                  <span style={{ color: TEAL_DARK, fontWeight: 700, marginLeft: 'auto', paddingLeft: 8 }}>→</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* ── Close to Home feed (REAL lens cards) ── */}
        <section id="close-to-home" style={{ marginTop: 30, paddingBottom: 44 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ width: 44, height: 44, borderRadius: 12, background: '#f0fdfa', display: 'grid', placeItems: 'center', fontSize: 21 }}>
              🏠
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <h2 className="font-display" style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>
                Close to Home
              </h2>
              <div style={{ fontSize: 14, color: '#78716c' }}>Near you, on what you care about · 📍 {placeLabel}</div>
            </div>
          </div>

          {/* Control row */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 16 }}>
            {WHEN.map((w) => (
              <Chip key={w.label} active={when.label === w.label} onClick={() => setWhen(w)}>
                {w.label}
              </Chip>
            ))}
            <button
              onClick={() => setFiltersOpen(!filtersOpen)}
              className="font-body"
              style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, padding: '7px 14px', borderRadius: 999, border: `1px solid ${filtersOpen || activeCount ? TEAL : '#e7e5e4'}`, background: '#fff', color: '#44403c', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
            >
              ⚙ Refine feed
              {activeCount > 0 && (
                <span className="font-mono-x" style={{ background: TEAL, color: '#fff', borderRadius: 999, fontSize: 11, fontWeight: 600, padding: '1px 7px' }}>
                  {activeCount}
                </span>
              )}
              <span style={{ fontSize: 11 }}>{filtersOpen ? '▲' : '▼'}</span>
            </button>
          </div>

          {/* Expander */}
          {filtersOpen && (
            <div style={{ marginTop: 12, background: '#fff', border: '1px solid #e7e5e4', borderRadius: 14, padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <MonoLabel>Topics — what you care about</MonoLabel>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                  {TOPICS.map((t) => (
                    <Chip key={t} active={activeTopics.includes(t)} onClick={() => toggle(activeTopics, setActiveTopics, t)}>
                      {t}
                    </Chip>
                  ))}
                </div>
              </div>
              <div>
                <MonoLabel>Signals — why it matters</MonoLabel>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                  {SIGNAL_ORDER.map((id) => (
                    <Chip key={id} active={activeSignals.includes(id)} onClick={() => toggle(activeSignals, setActiveSignals, id)}>
                      {SIGNAL_META[id].icon} {SIGNAL_META[id].name}
                    </Chip>
                  ))}
                </div>
              </div>
              <div style={{ fontSize: 13, color: '#78716c' }}>
                These choices follow you across the site. Change them anytime in{' '}
                <button onClick={() => navigate('/feed-setup')} style={{ background: 'none', border: 'none', padding: 0, color: TEAL_DARK, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>
                  feed settings
                </button>
                .
              </div>
            </div>
          )}

          {/* Feed (real) */}
          <div style={{ background: '#fff', border: '1px solid #e7e5e4', borderRadius: 14, marginTop: 14, overflow: 'hidden' }}>
            {feed.length > 0 ? (
              feed.map((row, i) => <StoryRow key={row.lensId + i} card={row.card} lensId={row.lensId} first={i === 0} />)
            ) : (
              <div style={{ padding: '28px 16px', textAlign: 'center', color: '#78716c', fontSize: 14 }}>
                No matching activity in {placeLabel} for {when.label.toLowerCase()}.
                {broaderLevel ? (
                  <>
                    {' '}Nothing here yet — try a wider area.
                    <div style={{ marginTop: 14 }}>
                      <button
                        type="button"
                        onClick={() => pickLevel(broaderLevel.value)}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 7, background: TEAL, color: '#fff', border: 'none', borderRadius: 999, padding: '9px 18px', fontSize: 13.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = TEAL_DARK)}
                        onMouseLeave={(e) => (e.currentTarget.style.background = TEAL)}
                      >
                        📍 Expand to {broaderLevel.label}
                      </button>
                    </div>
                  </>
                ) : (
                  ' Try a wider window or different signals.'
                )}
              </div>
            )}
          </div>
        </section>
      </main>

      {/* ── How It Works (ported from the original home page, restyled for v9).
          Header format matches the sibling "Our Impact" section: section name as
          the centered <h2>, no mono eyebrow. ── */}
      <section id="how-it-works" style={{ background: '#fff', borderTop: '1px solid #e7e5e4', padding: '56px 24px' }}>
        <div style={{ maxWidth: 1180, margin: '0 auto' }}>
          <div style={{ textAlign: 'center', maxWidth: 720, margin: '0 auto 36px' }}>
            <h2 className="font-display" style={{ fontSize: 'clamp(26px, 3.6vw, 34px)', fontWeight: 800, margin: 0, color: INK }}>
              How it works
            </h2>
            <p style={{ fontSize: 16, color: '#57534e', lineHeight: 1.55, marginTop: 12 }}>
              Start by choosing a cause, make a plan (learn the record, decide who to work with, then show up), find help
              when someone needs direct support, track the decisions that matter, and build on open data.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 14 }}>
            {[
              { icon: '📍', title: 'Choose a cause', blurb: 'Roads, schools, safety, family, health, or something else.', hash: 'explore-causes' },
              { icon: '🗺️', title: 'Make a plan', blurb: 'Personal and community paths, allies, and outcomes.', hash: 'explore-plan' },
              { icon: '💚', title: 'Find help', blurb: 'Nonprofits, programs, and family supports.', hash: 'explore-find-help' },
              { icon: '📊', title: 'Track decisions', blurb: 'Meetings, budgets, maps, and verification.', hash: 'explore-track-decisions' },
              { icon: '🧩', title: 'Build with data', blurb: 'Open datasets, APIs, and civic tooling.', hash: 'explore-build' },
            ].map((step) => (
              <button
                key={step.title}
                onClick={() => navigate(`/explore#${step.hash}`)}
                style={{ textAlign: 'left', background: '#fff', border: '1px solid #e7e5e4', borderRadius: 14, padding: 18, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', flexDirection: 'column', gap: 0, boxShadow: '0 1px 2px rgba(28,25,23,0.04)' }}
              >
                <span style={{ width: 42, height: 42, borderRadius: 11, background: '#f0fdfa', display: 'grid', placeItems: 'center', fontSize: 20, marginBottom: 12 }}>
                  {step.icon}
                </span>
                <span className="font-display" style={{ fontSize: 16.5, fontWeight: 700, color: INK }}>{step.title}</span>
                <span style={{ fontSize: 13, color: '#57534e', lineHeight: 1.45, marginTop: 6 }}>{step.blurb}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ── Our Impact / Our Mission (ported from the original home page) ── */}
      <section id="impact" style={{ background: '#fafaf9', borderTop: '1px solid #e7e5e4', padding: '56px 24px' }}>
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
        <div style={{ maxWidth: 1180, margin: '0 auto', padding: '14px 24px', display: 'flex', flexWrap: 'wrap', gap: 18, alignItems: 'center' }}>
          {[
            ['💵', 'Follow local spending'],
            ['🗳️', 'Understand decisions'],
            ['🔁', 'Track outcomes'],
            ['🔭', 'Discover issues early'],
          ].map(([icon, title]) => (
            <div key={title} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <span style={{ fontSize: 16 }}>{icon}</span>
              <span className="font-display" style={{ fontSize: 14, fontWeight: 700 }}>
                {title}
              </span>
            </div>
          ))}
        </div>
        <div style={{ borderTop: '1px solid #f5f5f4', maxWidth: 1180, margin: '0 auto', padding: '9px 24px', display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12.5, color: '#a8a29e' }}>CommunityOne · a 501(c)(3) nonprofit · Tuscaloosa, Alabama</span>
        </div>
      </footer>
    </div>
  )
}
