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
import { useMemo, useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import MoneyGameModal from '../components/MoneyGameModal'
import FollowTheMoney from '../components/FollowTheMoney'
import { fetchPolicyQuestions } from '../api/policyQuestions'
import { useLocation as useLocationContext, type LocationData } from '../contexts/LocationContext'
import { nominatimUsStateCode } from '../utils/stateMapping'

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

// Build a real LocationData from a Nominatim geocode result (same parsing as
// AddressLookup.processResult). Returns null when no US state resolves — we
// never fabricate a location.
function locationFromGeocode(result: any): LocationData | null {
  if (!result) return null
  const addr = result.address || {}
  const stateCode = nominatimUsStateCode(addr) || ''
  if (!stateCode) return null
  const county = (addr.county as string) || ''
  const city =
    (addr.city as string) ||
    (addr.town as string) ||
    (addr.village as string) ||
    (addr.municipality as string) ||
    (addr.hamlet as string) ||
    (addr.suburb as string) ||
    ''
  if (!city && !county) return null
  return {
    address: result.display_name,
    state: stateCode,
    county,
    city,
    granularity: !city ? 'county' : undefined,
    latitude: parseFloat(result.lat),
    longitude: parseFloat(result.lon),
  }
}

// Build the disambiguation choices for a ZIP from its geocode results. A ZIP can
// span cities and/or land inside vs. outside city limits — and city rates STACK
// on county rates, so the choice changes the real bill. We surface one chip per
// distinct city ("inside {city}") plus an "outside city limits" (county-only)
// option per distinct county. Real geography only — no invented ZIP table.
function buildZipChoices(results: any[]): { label: string; loc: LocationData }[] {
  const locs = (Array.isArray(results) ? results : [results])
    .map(locationFromGeocode)
    .filter(Boolean) as LocationData[]
  const cities = new Map<string, LocationData>()
  const counties = new Map<string, LocationData>()
  for (const l of locs) {
    if (l.city) {
      const k = `${l.city}|${l.county}`
      if (!cities.has(k)) cities.set(k, l)
    }
    if (l.county) {
      if (!counties.has(l.county)) counties.set(l.county, { ...l, city: '', granularity: 'county' })
    }
  }
  const multiCounty = counties.size > 1
  const choices: { label: string; loc: LocationData }[] = []
  for (const l of cities.values()) choices.push({ label: `📍 ${l.city}`, loc: l })
  for (const l of counties.values()) {
    choices.push({
      label: multiCounty ? `🌾 Outside city limits (${l.county})` : '🌾 Outside city limits',
      loc: l,
    })
  }
  return choices
}

// ── Money hook (compact banner; REAL geocode + REAL modal) ──────────────────
// The "How much of your money is on the line?" teal banner. The CTA opens the
// real <MoneyGameModal> (Census finances + the ACS property-tax estimate +
// Opportunity Atlas) scoped to the user's place. When we don't yet know where
// they are, the banner expands to a ZIP entry resolved via the /api/geocode
// proxy — we never fabricate a location.
function MoneyHookBanner() {
  const { location, setLocation } = useLocationContext()
  const [zip, setZip] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [locating, setLocating] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // The place the modal is scoped to — the just-resolved ZIP, else any
  // already-set community.
  const [resolved, setResolved] = useState<LocationData | null>(location ?? null)
  // When a ZIP is ambiguous (spans cities / inside-vs-outside city limits), the
  // user picks here before the modal opens.
  const [choices, setChoices] = useState<{ label: string; loc: LocationData }[] | null>(null)

  const zipValid = /^\d{5}$/.test(zip)
  const scope = resolved ?? location ?? null
  const needsChoice = !!choices && choices.length > 1

  const openFor = (loc: LocationData) => {
    setChoices(null)
    setResolved(loc)
    setLocation(loc)
    setModalOpen(true)
  }

  const resolveZip = async () => {
    setError(null)
    setChoices(null)
    setBusy(true)
    try {
      const fwd = await api.get(`/geocode/search`, { params: { q: zip, limit: 10 } })
      const fwdResults = Array.isArray(fwd.data) ? fwd.data : [fwd.data]
      // Nominatim's forward ZIP lookup often omits the city — but reverse-geocoding
      // the ZIP centroid reliably returns it. Merge both so we recover every real
      // city the ZIP touches (e.g. 35406 → Tuscaloosa), then dedupe in buildZipChoices.
      let revResults: any[] = []
      const first = fwdResults.find((r) => r?.lat && r?.lon)
      if (first) {
        try {
          const rev = await api.get(`/geocode/reverse`, { params: { lat: first.lat, lon: first.lon } })
          revResults = Array.isArray(rev.data) ? rev.data : [rev.data]
        } catch {
          /* reverse is best-effort */
        }
      }
      const opts = buildZipChoices([...revResults, ...fwdResults])
      if (opts.length === 0) {
        setError("We couldn't find that ZIP. Try another, or use your location.")
        return
      }
      if (opts.length === 1) {
        openFor(opts[0].loc) // unambiguous → straight to the bill
      } else {
        setChoices(opts) // spans cities / city-vs-county → ask first
      }
    } catch {
      setError("We couldn't look up that ZIP right now. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  // The button only works with a valid 5-digit ZIP (or "use my location").
  const handleShow = () => {
    if (needsChoice || busy) return // waiting on a pick or a lookup
    if (zipValid) void resolveZip()
  }

  const useMyLocation = () => {
    setError(null)
    if (!navigator.geolocation) {
      setError('Location services are unavailable. Enter your ZIP instead.')
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const res = await api.get(`/geocode/reverse`, {
            params: { lat: coords.latitude, lon: coords.longitude },
          })
          const first = Array.isArray(res.data) ? res.data[0] : res.data
          const loc = locationFromGeocode(first)
          if (!loc) {
            setError("We couldn't pin your location. Enter your ZIP instead.")
            return
          }
          openFor(loc)
        } catch {
          setError("We couldn't pin your location. Enter your ZIP instead.")
        } finally {
          setLocating(false)
        }
      },
      () => {
        setLocating(false)
        setError("We couldn't access your location. Enter your ZIP instead.")
      },
      { timeout: 8000 },
    )
  }

  // Primary CTA: if we already know the user's place, go straight to the real
  // bill; otherwise reveal the ZIP entry (we never fabricate a location).
  const handleCta = () => {
    if (busy || needsChoice) return
    if (scope?.state) {
      setModalOpen(true)
      return
    }
    setExpanded(true)
  }

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
          onClick={handleCta}
          style={{ background: TEAL, color: '#fff', border: 'none', borderRadius: 999, padding: '12px 24px', fontSize: 15, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap', flexShrink: 0 }}
        >
          {busy ? 'Finding…' : 'Show me my money →'}
        </button>
      </div>

      {/* ZIP fallback — only when we don't know the user's place yet. Every town
          reaches into your pocket differently, so we resolve a real ZIP rather
          than assume one. */}
      {expanded && !scope?.state && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, marginTop: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#44403c' }}>
            What&apos;s your ZIP?
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
            <input
              value={zip}
              onChange={(e) => {
                setZip(e.target.value.replace(/\D/g, '').slice(0, 5))
                setError(null)
                setChoices(null)
              }}
              onKeyDown={(e) => e.key === 'Enter' && handleShow()}
              placeholder="e.g. 35401"
              inputMode="numeric"
              autoFocus
              className="font-mono-x"
              style={{ width: 150, padding: '12px 14px', fontSize: 16, borderRadius: 999, border: `1.5px solid ${zipValid ? TEAL : '#d6d3d1'}`, outline: 'none', textAlign: 'center', letterSpacing: '0.12em', transition: 'border-color 150ms ease' }}
            />
            <button
              onClick={handleShow}
              disabled={busy || needsChoice || !zipValid}
              title={!zipValid ? 'Enter your 5-digit ZIP first' : undefined}
              style={{ background: zipValid && !needsChoice ? TEAL : '#e7e5e4', color: zipValid && !needsChoice ? '#fff' : '#a8a29e', border: 'none', borderRadius: 999, padding: '12px 24px', fontSize: 15.5, fontWeight: 700, cursor: zipValid && !needsChoice && !busy ? 'pointer' : 'default', fontFamily: 'inherit', transition: 'background 200ms ease, color 200ms ease' }}
            >
              {busy ? 'Finding…' : needsChoice ? 'Pick your area first' : 'Show me my money'}
            </button>
          </div>

          {/* ZIP disambiguation — real geography: this ZIP spans places / city
              limits, and city rates stack on the county's, so the choice changes
              the bill. Picking one opens the modal scoped to it. */}
          {needsChoice && choices && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 7 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#57534e' }}>
                {zip} crosses jurisdiction lines — where&apos;s home? (City taxes stack on the county&apos;s.)
              </span>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
                {choices.map((c, i) => (
                  <Chip key={c.label + i} onClick={() => openFor(c.loc)} style={{ fontSize: 13.5 }}>
                    {c.label}
                  </Chip>
                ))}
              </div>
            </div>
          )}

          {error && <div style={{ fontSize: 12.5, color: '#b45309', fontWeight: 600 }}>{error}</div>}

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
            <button
              onClick={useMyLocation}
              style={{ background: 'none', border: 'none', color: TEAL_DARK, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', padding: 0 }}
            >
              {locating ? 'Locating…' : '📍 use my location'}
            </button>
            <span className="font-mono-x" style={{ fontSize: 10, letterSpacing: '0.05em', color: '#a8a29e', textTransform: 'uppercase' }}>
              just the ZIP · nothing stored · 15 seconds
            </span>
          </div>
        </div>
      )}

      {scope?.state && (
        <MoneyGameModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          stateCode={scope.state}
          city={scope.city || undefined}
          county={scope.county || undefined}
          requestedLabel={scope.city || scope.county || scope.state}
        />
      )}
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
  const stateCode = location?.state || undefined
  const city = location?.city || undefined
  const national = !stateCode
  const placeLabel = location?.city || location?.county || (stateCode ? stateCode : 'the U.S.')

  const [menuOpen, setMenuOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [when, setWhen] = useState(WHEN[0])
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [activeTopics, setActiveTopics] = useState<string[]>([TOPICS[0]])
  const [activeSignals, setActiveSignals] = useState<string[]>(['contested'])
  const trendRef = useRef<HTMLDivElement>(null)

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

  const { data: trending } = useQuery({
    queryKey: ['home-v9-trending'],
    queryFn: () => fetchPolicyQuestions({ limit: 10 }),
    staleTime: 30 * 60 * 1000,
  })
  const trendingChips = (trending ?? []).filter((q) => !!q.canonical_text).slice(0, 6)

  // ── Derived (all real) ──
  const lenses = lensesData?.lenses ?? []
  const activity = lensesData?.activity ?? []
  const lensById = useMemo(() => {
    const m: Record<string, LensBlock> = {}
    for (const l of lenses) m[l.id] = l
    return m
  }, [lenses])

  // "This week": the first real card from each populated headline lens.
  const thisWeek = useMemo(() => {
    const out: { lensId: string; card: LensCard }[] = []
    for (const id of ['contested', 'money', 'flags']) {
      const l = lensById[id]
      if (l && !l.placeholder && l.cards.length > 0) out.push({ lensId: id, card: l.cards[0] })
    }
    return out
  }, [lensById])

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
    const params = new URLSearchParams()
    if (term) params.set('q', term)
    if (!national && stateCode) params.set('state', stateCode)
    // Carry the city through so a drill-down from e.g. Tuscaloosa reads
    // "City: Tuscaloosa" rather than just "State: AL" (UnifiedSearch reads ?city=).
    if (!national && city) params.set('city', city)
    navigate(`/search?${params.toString()}`, { state: { fromHome: true } })
  }

  const trendScrollBy = (dx: number) => trendRef.current?.scrollBy({ left: dx, behavior: 'smooth' })

  return (
    <div className="v9 font-body" style={{ background: '#fafaf9', minHeight: '100vh', color: INK }}>
      <style>{FONTS}</style>

      {/* ── Header ── */}
      <header style={{ position: 'sticky', top: 0, zIndex: 50, background: '#fff', borderBottom: '1px solid #e7e5e4' }}>
        <div style={{ maxWidth: 1180, margin: '0 auto', padding: '12px 24px', display: 'flex', alignItems: 'center', gap: 24, position: 'relative' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
            <div
              className="font-mono-x"
              style={{ width: 38, height: 38, borderRadius: '50%', border: `2.5px solid ${TEAL}`, display: 'grid', placeItems: 'center', fontWeight: 800, color: TEAL, fontSize: 15 }}
            >
              C1
            </div>
            <div>
              <div className="font-display" style={{ fontSize: 19, fontWeight: 700, lineHeight: 1.1 }}>
                Open Navigator
              </div>
              <div className="v9-brand-sub" style={{ fontSize: 11.5, color: '#78716c' }}>
                by CommunityOne
              </div>
            </div>
          </div>

          <button
            className="v9-burger"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            onClick={() => setMenuOpen(!menuOpen)}
            style={{ width: 40, height: 40, border: '1px solid #e7e5e4', borderRadius: 10, background: '#fff', cursor: 'pointer', placeItems: 'center', fontSize: 18, color: INK }}
          >
            {menuOpen ? '✕' : '☰'}
          </button>

          <nav className={'v9-nav' + (menuOpen ? ' open' : '')} style={{ display: 'flex', gap: 22, marginLeft: 'auto', alignItems: 'center' }}>
            {[
              ['Search', () => runSearch('')],
              ['How It Works', () => navigate('/explore')],
              ['Impact', () => navigate('/explore')],
              ['Contact', () => navigate('/support')],
            ].map(([label, fn]) => (
              <button
                key={label as string}
                onClick={() => {
                  setMenuOpen(false)
                  ;(fn as () => void)()
                }}
                style={{ background: 'none', border: 'none', fontSize: 14.5, fontWeight: 600, color: '#44403c', cursor: 'pointer', fontFamily: 'inherit' }}
              >
                {label as string}
              </button>
            ))}
            <button
              onClick={() => navigate('/explore')}
              style={{ background: INK, color: '#fff', border: 'none', borderRadius: 10, padding: '10px 18px', fontSize: 14.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
            >
              Explore now
            </button>
          </nav>
        </div>
      </header>

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

          <div
            style={{
              maxWidth: 760,
              margin: '24px auto 0',
              display: 'flex',
              background: '#fff',
              border: '1px solid #e7e5e4',
              borderRadius: 14,
              boxShadow: '0 4px 16px rgba(28,25,23,0.06)',
              overflow: 'hidden',
            }}
          >
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && runSearch()}
              placeholder="Search topics, people, organizations, or causes"
              style={{ flex: 1, border: 'none', outline: 'none', padding: '16px 18px', fontSize: 16, fontFamily: 'inherit', minWidth: 0 }}
            />
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 14px', borderLeft: '1px solid #e7e5e4', color: '#44403c', fontSize: 14.5, fontWeight: 600, whiteSpace: 'nowrap' }}
            >
              📍 {placeLabel}
            </div>
            <button
              aria-label="Search"
              onClick={() => runSearch()}
              style={{ background: TEAL, color: '#fff', border: 'none', padding: '0 24px', fontSize: 18, cursor: 'pointer' }}
            >
              🔍
            </button>
          </div>

          {/* Trending questions — REAL policy-question registry. */}
          {trendingChips.length > 0 && (
            <div style={{ position: 'relative', maxWidth: 860, margin: '10px auto 0' }}>
              <div
                ref={trendRef}
                className="hide-scroll"
                style={{ display: 'flex', gap: 8, alignItems: 'center', overflowX: 'auto', padding: '2px 34px' }}
              >
                <MonoLabel style={{ color: '#57534e', flexShrink: 0 }}>Trending</MonoLabel>
                {trendingChips.map((q) => (
                  <Chip key={q.question_id} onClick={() => navigate(`/policy-question/${q.question_id}`)} style={{ flexShrink: 0 }}>
                    {q.canonical_text}
                  </Chip>
                ))}
              </div>
              <button
                onClick={() => trendScrollBy(240)}
                aria-label="Scroll trending questions right"
                style={{ position: 'absolute', right: 0, top: '50%', transform: 'translateY(-50%)', zIndex: 2, width: 28, height: 28, borderRadius: '50%', border: '1px solid #d6d3d1', background: '#fff', boxShadow: '0 2px 8px rgba(28,25,23,0.12)', cursor: 'pointer', display: 'grid', placeItems: 'center', fontSize: 14, color: '#44403c', lineHeight: 1 }}
              >
                ›
              </button>
            </div>
          )}
        </section>

        {/* ── Money hook (compact teal banner; REAL geocode + REAL modal) ── */}
        <MoneyHookBanner />

        {/* ── Big questions in your community (REAL featured policy questions) ── */}
        <BigQuestions />

        {/* ── City snapshot strip (REAL: /api/lenses activity) ── */}
        {activity.length > 0 && (
          <section style={{ marginTop: 26 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
              <h2 className="font-display" style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>
                {placeLabel} at a glance
              </h2>
              <span
                className="font-mono-x"
                style={{ fontSize: 10, color: TEAL_DARK, background: '#f0fdfa', border: '1px solid #ccfbf1', borderRadius: 999, padding: '2px 9px', fontWeight: 600 }}
              >
                ● LIVE
              </span>
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap' }}>
              {activity.slice(0, 4).map((a) => (
                <button
                  key={a.label}
                  onClick={() => a.query && runSearch(a.query)}
                  title={a.label}
                  style={{ flex: '1 1 200px', textAlign: 'left', background: '#fff', border: '1px solid #e7e5e4', borderRadius: 12, padding: '10px 14px', cursor: a.query ? 'pointer' : 'default', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 10 }}
                >
                  <span style={{ width: 32, height: 32, borderRadius: 9, background: '#f0fdfa', display: 'grid', placeItems: 'center', fontSize: 15, flexShrink: 0 }}>
                    {a.icon}
                  </span>
                  <span>
                    <span className="font-display" style={{ fontSize: 19, fontWeight: 700, lineHeight: 1, display: 'block' }}>
                      {a.value}
                    </span>
                    <span style={{ fontSize: 12, color: '#57534e' }}>{a.label}</span>
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* ── What's happening this week (REAL lens cards) ── */}
        {thisWeek.length > 0 && (
          <section style={{ marginTop: 30 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
              <h2 className="font-display" style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>
                What&apos;s happening this week
              </h2>
              <button onClick={() => runSearch('')} style={{ background: 'none', border: 'none', color: TEAL_DARK, fontWeight: 700, fontSize: 14.5, cursor: 'pointer', fontFamily: 'inherit' }}>
                See all →
              </button>
            </div>
            <div style={{ background: '#fff', border: '1px solid #e7e5e4', borderRadius: 14, marginTop: 12, overflow: 'hidden' }}>
              {thisWeek.map((row, i) => (
                <StoryRow key={row.lensId + i} card={row.card} lensId={row.lensId} first={i === 0} />
              ))}
            </div>
          </section>
        )}

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
                No matching activity in {placeLabel} for {when.label.toLowerCase()}. Try a wider window or different signals.
              </div>
            )}
          </div>
        </section>
      </main>

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
