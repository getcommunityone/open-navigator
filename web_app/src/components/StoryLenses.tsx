import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronRightIcon, ChevronLeftIcon, BookmarkIcon, ArrowRightIcon } from '@heroicons/react/24/outline'
import { BookmarkIcon as BookmarkSolidIcon } from '@heroicons/react/24/solid'
import api from '../lib/api'
import FollowTheMoney from './FollowTheMoney'

/**
 * StoryLenses — the homepage "What's happening near you" section.
 *
 * Re-ranks civic activity by editorial *lenses* (Contested, Money Moves,
 * Raised Eyebrows, Moving Fast, Watch Next) rather than by topic, with a live
 * activity strip, a time-frame control, and a story-card grid.
 *
 * Live data ONLY, from `GET /api/lenses` (state/city/window scoped). There is
 * no demo/hardcoded fallback: on a hard failure we show an honest error state,
 * while loading we show skeletons, and lenses the API marks `placeholder: true`
 * (e.g. flags, soon — signals not yet extracted) render an honest empty state.
 * We never fabricate stories.
 */

const FONT = { fontFamily: "'DM Sans', sans-serif" } as const
const SERIF = { fontFamily: "'Newsreader', Georgia, 'Times New Roman', serif" } as const

type Tone = 'plain' | 'green' | 'amber' | 'red' | 'blue' | 'purple'
const TONES: Record<Tone, { bg: string; fg: string }> = {
  plain: { bg: '#f3f7f6', fg: '#56635e' },
  green: { bg: '#e7f2ef', fg: '#1d6b5f' },
  amber: { bg: '#fbf3e2', fg: '#9a6b12' },
  red: { bg: '#fdeeeb', fg: '#c0432a' },
  blue: { bg: '#eaf1f8', fg: '#2f6fb0' },
  purple: { bg: '#efebfb', fg: '#6b5bd2' },
}

interface Lens {
  id: string
  em: string
  label: string
  desc: string
  clr: string
  /** Advisory shown above the grid (Raised Eyebrows). */
  note?: string
}

const LENSES: Lens[] = [
  { id: 'contested', em: '\u{1F525}', label: 'Contested', desc: 'Split votes and heated debates', clr: '#e0603a' },
  { id: 'money', em: '\u{1F4B2}', label: 'Money Moves', desc: 'Contracts, spending, and big budgets', clr: '#2a8576' },
  {
    id: 'flags',
    em: '\u{1F441}\u{FE0F}',
    label: 'Raised Eyebrows',
    desc: 'Decisions that make you go hmm…',
    clr: '#7a5cd0',
    note:
      '⚠ Flags are unverified anomalies pulled from public records — a prompt to look closer, not a finding of wrongdoing. Every card links to the underlying record so you can judge for yourself.',
  },
  { id: 'soon', em: '⚡', label: 'Moving Fast', desc: 'Urgent items and rushed decisions', clr: '#d57a1e' },
  { id: 'next', em: '\u{1F4C5}', label: 'Watch Next', desc: 'Upcoming votes to keep on your radar', clr: '#2f6fb0' },
]

interface Stat {
  v: string
  l: string
  tone?: Tone
}
const TIME_OPTIONS: { d: number; label: string }[] = [
  { d: 31, label: 'Past month' },
  { d: 92, label: 'Past 3 months' },
  { d: 366, label: 'Past year' },
  { d: 1830, label: 'Past 5 years' },
  { d: 999999, label: 'All time' },
]

const POPULAR_TOPICS = ['budget', 'zoning', 'police', 'schools', 'infrastructure', 'taxes']

function rel(d: number): string {
  if (d === 0) return 'today'
  const fut = d > 0
  const a = Math.abs(d)
  let t: string
  if (a < 1) {
    t = 'today'
    return t
  } else if (a < 2) {
    t = '1 day'
  } else if (a < 7) {
    t = `${a} days`
  } else if (a < 31) {
    const w = Math.round(a / 7)
    t = `${w} ${w === 1 ? 'week' : 'weeks'}`
  } else if (a < 365) {
    const m = Math.round(a / 30)
    t = `${m} ${m === 1 ? 'month' : 'months'}`
  } else {
    const y = Math.round(a / 365)
    t = `${y} ${y === 1 ? 'year' : 'years'}`
  }
  return fut ? `in ${t}` : `${t} ago`
}

// windowDays (segmented-control value) -> API `window` param, and back.
const WINDOW_BY_DAYS: Record<number, string> = { 31: 'month', 92: 'quarter', 366: 'year', 1830: 'fiveyear', 999999: 'all' }
// API window string -> segmented-control day value (reverse of WINDOW_BY_DAYS).
// Used to highlight the grain that 'auto' resolved to, instead of a separate chip.
const DAYS_BY_WINDOW: Record<string, number> = { month: 31, quarter: 92, year: 366, fiveyear: 1830, all: 999999 }
// accent backgrounds for the live activity tiles, by position
const ACTIVITY_BG = ['#fdeeeb', '#e7f2ef', '#efebfb', '#fbf3e2']

// ---- /api/lenses response shape ----
interface ApiStat {
  value: string
  label: string
  tone?: Tone
}
interface ApiCard {
  headline: string
  stats: ApiStat[]
  jurisdiction: string
  date?: string
  badge?: string
  url?: string
  state_code?: string
  state?: string
}
interface ApiLens {
  id: string
  label: string
  placeholder: boolean
  cards: ApiCard[]
}
interface ApiActivity {
  icon: string
  value: string
  label: string
  /** Search term the tile drills into; falls back to one derived from the label. */
  query?: string
}
interface LensesResponse {
  lenses: ApiLens[]
  activity: ApiActivity[]
  window: string
  location_label?: string
}

// Normalized card the grid renders, from either live API or demo fallback.
interface RenderCard {
  h: string
  stats: Stat[]
  juris: string
  when: string
  url?: string
  stateCode?: string
}

// Census place names carry a *lowercase* generic type suffix ("Douglas city",
// "Winthrop Town city", "Garden City city"). Strip a trailing lowercase type
// word so cards read "Winthrop Town" / "Garden City", while leaving a
// capitalized proper noun that is part of the name intact ("Phenix City",
// "Kansas City" — the "City" there is uppercase, so it never matches).
const PLACE_TYPE_SUFFIX = /\s+(city|town|village|borough|township|municipality|cdp)\s*$/
function cleanJuris(name: string): string {
  return name.replace(PLACE_TYPE_SUFFIX, '').trim() || name
}

// Relative-time label from an ISO yyyy-mm-dd date (reuses rel()'s wording).
function relFromDate(dateStr?: string): string {
  if (!dateStr) return ''
  const then = new Date(`${dateStr}T00:00:00`)
  if (Number.isNaN(then.getTime())) return ''
  const days = Math.round((then.getTime() - Date.now()) / 86_400_000)
  return rel(days)
}

// Map an activity-tile label to a search term when the API doesn't supply one.
function activitySearchQuery(label: string): string {
  const l = label.toLowerCase()
  if (l.includes('contested')) return 'contested'
  if (l.includes('spending') || l.includes('budget')) return 'budget'
  if (l.includes('comment')) return 'public comment'
  if (l.includes('project')) return 'projects'
  if (l.includes('vote') || l.includes('upcoming')) return 'upcoming vote'
  if (l.includes('decision')) return 'decisions'
  return label.replace(/^in\s+/i, '').trim()
}

// Map an activity-tile label to the lens it should reveal on the homepage (so a
// tile shows the real, location-scoped stories instead of a keyword search).
function activityToLens(label: string): string | null {
  const l = label.toLowerCase()
  if (l.includes('contest')) return 'contested'
  if (l.includes('spend') || l.includes('money') || l.includes('budget') || l.includes('dollar')) return 'money'
  if (l.includes('coming back') || l.includes('upcoming') || l.includes('vote')) return 'next'
  if (l.includes('flag') || l.includes('eyebrow') || l.includes('anomal')) return 'flags'
  return null
}

interface StoryLensesProps {
  /** Short place label for headings, e.g. "Northport". */
  locationLabel?: string
  /** 2-letter state code for scoping the lenses query. */
  stateCode?: string
  /** City for scoping the lenses query. */
  city?: string
  /** When true, ignore stateCode/city and show a national view. */
  national?: boolean
  /** Invoked when a card or popular-topic is activated. */
  onSearch?: (query: string) => void
  /** Invoked by "View all" / "See all activity" / Browse topics. */
  onBrowseTopics?: () => void
}

// ---------------------------------------------------------------------------
// Story card — shared by the desktop reflow grid and the mobile swipe carousel.
// ---------------------------------------------------------------------------
interface StoryCardProps {
  card: RenderCard
  lens: Lens
  saved: boolean
  onToggleSave: () => void
  onOpen: () => void
}

function StoryCard({ card: c, lens, saved, onToggleSave, onOpen }: StoryCardProps) {
  const clickable = !!c.url
  return (
    <article
      {...(clickable
        ? {
            role: 'link',
            tabIndex: 0,
            onClick: onOpen,
            onKeyDown: (e: React.KeyboardEvent) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onOpen()
              }
            },
          }
        : {})}
      className={`group relative flex h-full flex-col overflow-hidden rounded-2xl border bg-white transition-all ${
        saved
          ? 'border-[#1d6b5f] shadow-[0_0_0_1.5px_#1d6b5f,0_8px_24px_rgba(20,40,35,.08)]'
          : 'border-[#e1ebe7] shadow-[0_1px_2px_rgba(20,40,35,.04),0_8px_24px_rgba(20,40,35,.06)]'
      } ${
        clickable
          ? 'cursor-pointer hover:-translate-y-0.5 hover:border-[#cfe0db] hover:shadow-[0_2px_4px_rgba(20,40,35,.06),0_14px_32px_rgba(20,40,35,.10)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a6b6b]/40'
          : ''
      }`}
    >
      <span className="h-1 w-full" style={{ background: lens.clr }} aria-hidden />
      <div className="flex flex-1 flex-col p-[18px]">
        <div className="mb-2.5 flex items-center justify-between gap-2">
          <span
            className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-bold tracking-wide"
            style={{ color: lens.clr, background: `color-mix(in srgb, ${lens.clr} 12%, #fff)` }}
          >
            <span className="text-[12px] leading-none">{lens.em}</span>
            {lens.label}
          </span>
          <span className="shrink-0 text-[12px] text-[#8a958f]">{c.when}</span>
        </div>

        <h3
          className="mb-3 text-[19px] font-semibold leading-tight tracking-tight text-[#0f2b2b] group-hover:underline"
          style={SERIF}
        >
          {c.h}
        </h3>

        <div className="mb-3 flex flex-wrap gap-2">
          {c.stats.map((s) => {
            const tone = TONES[s.tone || 'plain']
            return (
              <div key={s.l} className="rounded-lg px-2.5 py-1.5" style={{ background: tone.bg }}>
                <div className="text-[13.5px] font-bold leading-none" style={{ color: tone.fg }}>
                  {s.v}
                </div>
                <div className="mt-1 text-[10.5px] font-medium leading-none text-[#8a958f]">{s.l}</div>
              </div>
            )
          })}
        </div>

        <div className="mt-auto flex items-center gap-2 border-t border-[#e1ebe7] pt-2.5 text-[12px] text-[#8a958f]">
          <span className="font-semibold text-[#56635e]">{c.juris}</span>
          <span className="opacity-50">&middot;</span>
          <span>{c.when}</span>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onToggleSave()
            }}
            className={`ml-auto transition-colors ${saved ? 'text-[#1d6b5f]' : 'text-[#9bb8b8] hover:text-[#1a6b6b]'}`}
            aria-pressed={saved}
            aria-label={saved ? 'Saved — tap to remove' : 'Save story'}
            title={saved ? 'Saved to Following' : 'Save story'}
          >
            {saved ? <BookmarkSolidIcon className="h-4 w-4" aria-hidden /> : <BookmarkIcon className="h-4 w-4" aria-hidden />}
          </button>
        </div>
      </div>
    </article>
  )
}

// ---------------------------------------------------------------------------
// Swipe carousel (mobile) — pattern #1 from the responsive-tiles demo.
// A scroll-snap flex rail whose cards sit at 84% width so the next one peeks,
// inviting a thumb-swipe. An IntersectionObserver drives the position dots and
// the (desktop/keyboard) prev/next arrows.
// ---------------------------------------------------------------------------
interface StoryCarouselProps {
  cards: RenderCard[]
  lens: Lens
  savedKeys: Set<string>
  onToggleSave: (key: string) => void
  onOpen: (card: RenderCard) => void
  cardKey: (card: RenderCard, i: number) => string
}

function StoryCarousel({ cards, lens, savedKeys, onToggleSave, onOpen, cardKey }: StoryCarouselProps) {
  const railRef = useRef<HTMLDivElement>(null)
  const [activeIdx, setActiveIdx] = useState(0)

  useEffect(() => {
    const rail = railRef.current
    if (!rail) return
    const items = Array.from(rail.children) as HTMLElement[]
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const i = items.indexOf(e.target as HTMLElement)
            if (i >= 0) setActiveIdx(i)
          }
        })
      },
      { root: rail, threshold: 0.6 },
    )
    items.forEach((it) => io.observe(it))
    return () => io.disconnect()
    // Re-observe whenever the card set changes (lens/window switch).
  }, [cards])

  const scrollTo = (i: number) => {
    const rail = railRef.current
    if (!rail) return
    const clamped = Math.max(0, Math.min(cards.length - 1, i))
    const target = rail.children[clamped] as HTMLElement | undefined
    target?.scrollIntoView({ behavior: 'smooth', inline: 'start', block: 'nearest' })
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => scrollTo(activeIdx - 1)}
        disabled={activeIdx === 0}
        aria-label="Previous story"
        className="absolute -left-2 top-[42%] z-10 hidden h-9 w-9 items-center justify-center rounded-full border border-[#e1ebe7] bg-white text-[#56635e] shadow-[0_1px_2px_rgba(20,40,35,.05),0_10px_26px_rgba(20,40,35,.07)] transition-colors hover:border-[#1a6b6b] hover:text-[#1a6b6b] disabled:pointer-events-none disabled:opacity-30 sm:flex"
      >
        <ChevronLeftIcon className="h-5 w-5" aria-hidden />
      </button>
      <button
        type="button"
        onClick={() => scrollTo(activeIdx + 1)}
        disabled={activeIdx === cards.length - 1}
        aria-label="Next story"
        className="absolute -right-2 top-[42%] z-10 hidden h-9 w-9 items-center justify-center rounded-full border border-[#e1ebe7] bg-white text-[#56635e] shadow-[0_1px_2px_rgba(20,40,35,.05),0_10px_26px_rgba(20,40,35,.07)] transition-colors hover:border-[#1a6b6b] hover:text-[#1a6b6b] disabled:pointer-events-none disabled:opacity-30 sm:flex"
      >
        <ChevronRightIcon className="h-5 w-5" aria-hidden />
      </button>

      <div
        ref={railRef}
        className="-mx-1 flex snap-x snap-mandatory gap-4 overflow-x-auto px-1 pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {cards.map((c, i) => {
          const key = cardKey(c, i)
          return (
            <div key={key} className="w-[84%] max-w-[340px] shrink-0 snap-start sm:w-[300px]">
              <StoryCard
                card={c}
                lens={lens}
                saved={savedKeys.has(key)}
                onToggleSave={() => onToggleSave(key)}
                onOpen={() => onOpen(c)}
              />
            </div>
          )
        })}
      </div>

      {cards.length > 1 && (
        <div className="mt-1 flex justify-center gap-[7px]">
          {cards.map((c, i) => (
            <button
              key={cardKey(c, i)}
              type="button"
              onClick={() => scrollTo(i)}
              aria-label={`Go to story ${i + 1}`}
              className={`h-[7px] rounded-full transition-all ${
                i === activeIdx ? 'w-5 bg-[#1d6b5f]' : 'w-[7px] bg-[#d6e4e0]'
              }`}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// Normalize an API lens's cards into the grid's RenderCard shape, appending a
// ", ST" suffix to the jurisdiction only when the set spans >1 state or the view
// is unscoped (so a single-state local view stays clean). Computed per-lens so
// each stacked section disambiguates independently.
function toRenderCards(apiCards: ApiCard[], unscoped: boolean): RenderCard[] {
  const base = apiCards.map((c) => ({
    h: c.headline,
    stats: c.stats.map((s) => ({ v: s.value, l: s.label, tone: s.tone })),
    juris: cleanJuris(c.jurisdiction),
    when: relFromDate(c.date),
    url: c.url,
    stateCode: c.state_code || undefined,
  }))
  const distinctStates = new Set(base.map((c) => c.stateCode).filter(Boolean))
  const showState = unscoped || distinctStates.size > 1
  return base.map((c) =>
    showState && c.stateCode && !new RegExp(`,\\s*${c.stateCode}$`).test(c.juris)
      ? { ...c, juris: `${c.juris}, ${c.stateCode}` }
      : c,
  )
}

// ---------------------------------------------------------------------------
// LensSection — one stacked lens "lane" in the lens-organized homepage feed:
// a colored header (icon + label + desc + "See all") over a horizontal card
// rail. Honest loading / placeholder / empty states; never fabricates stories.
// The Money lens overrides the body with the Follow-the-money drilldown via
// the `body` prop.
// ---------------------------------------------------------------------------
interface LensSectionProps {
  lens: Lens
  cards: RenderCard[]
  placeholder: boolean
  loading: boolean
  savedKeys: Set<string>
  onToggleSave: (key: string) => void
  onOpen: (card: RenderCard) => void
  cardKey: (card: RenderCard, i: number) => string
  onSeeAll: () => void
  sectionRef: (el: HTMLElement | null) => void
  /** Overrides the card rail (used by Money Moves → Follow the money). */
  body?: React.ReactNode
}

function LensSection({
  lens,
  cards,
  placeholder,
  loading,
  savedKeys,
  onToggleSave,
  onOpen,
  cardKey,
  onSeeAll,
  sectionRef,
  body,
}: LensSectionProps) {
  return (
    <section ref={sectionRef} id={`lens-${lens.id}`} className="mb-10 scroll-mt-6">
      <div className="mb-3.5 flex items-center gap-3">
        <span
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-[19px]"
          style={{ background: `color-mix(in srgb, ${lens.clr} 12%, #fff)` }}
          aria-hidden
        >
          {lens.em}
        </span>
        <div className="min-w-0">
          <h2 className="text-[19px] font-semibold leading-tight tracking-tight" style={{ ...SERIF, color: lens.clr }}>
            {lens.label}
          </h2>
          <p className="text-[12.5px] leading-snug text-[#56635e]">{lens.desc}</p>
        </div>
        <button
          type="button"
          onClick={onSeeAll}
          className="ml-auto inline-flex shrink-0 items-center gap-1 text-[13px] font-medium text-[#1a6b6b] transition-colors hover:underline"
        >
          See all
          <ArrowRightIcon className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>

      {/* Advisory note (Raised Eyebrows) */}
      {lens.note && (
        <div className="mx-0.5 mb-4 flex gap-2 rounded-lg border border-[#e3dcf5] border-l-[3px] border-l-[#7a5cd0] bg-[#f4f0fc] px-3.5 py-2.5 text-[12.5px] leading-snug text-[#5b4a8a]">
          <span>{lens.note}</span>
        </div>
      )}

      {body !== undefined ? (
        body
      ) : loading ? (
        <div className="flex gap-4 overflow-hidden">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-44 w-[300px] shrink-0 animate-pulse rounded-2xl border border-[#e1ebe7] bg-[#f3f7f6]" />
          ))}
        </div>
      ) : placeholder ? (
        <div className="rounded-xl border border-dashed border-[#d4e8e8] bg-white px-6 py-8 text-center text-sm text-[#9bb8b8]">
          Coming soon — we&rsquo;re still extracting the signals for this lens.
        </div>
      ) : cards.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#d4e8e8] bg-white px-6 py-8 text-center text-sm text-[#9bb8b8]">
          Nothing in this window. <b className="text-[#56635e]">Try a wider time frame.</b>
        </div>
      ) : (
        <StoryCarousel
          cards={cards}
          lens={lens}
          savedKeys={savedKeys}
          onToggleSave={onToggleSave}
          onOpen={onOpen}
          cardKey={cardKey}
        />
      )}
    </section>
  )
}

export default function StoryLenses({ locationLabel, stateCode, city, national, onSearch, onBrowseTopics }: StoryLensesProps) {
  const navigate = useNavigate()
  // DOM refs to each stacked lens section, for activity-tile / quick-nav scroll.
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({})
  // Saved/"Following" stories, keyed by url||headline so the set survives
  // lens/window switches. Mirrors the demo's swipe-to-save outcome (#3).
  const [savedKeys, setSavedKeys] = useState<Set<string>>(() => new Set())
  const toggleSave = (key: string) =>
    setSavedKeys((prev) => {
      const nextSet = new Set(prev)
      if (nextSet.has(key)) nextSet.delete(key)
      else nextSet.add(key)
      return nextSet
    })
  // 'auto' (default) lets the API pick the narrowest window with enough items;
  // a number is an explicit user choice from the segmented control.
  const [windowSel, setWindowSel] = useState<number | 'auto'>('auto')
  const windowParam = windowSel === 'auto' ? 'auto' : WINDOW_BY_DAYS[windowSel] ?? 'month'

  // National scope ignores the (possibly stale) city/state and asks the API for
  // a country-wide view.
  const scopedState = national ? undefined : stateCode || undefined
  const scopedCity = national ? undefined : city || undefined
  // True whenever the query carries NO location filter — either an explicit
  // national view or simply no location selected. In both cases the results are
  // nationwide, so the UI must not claim they're local ("in your area").
  const unscoped = !scopedState && !scopedCity

  const { data, isLoading, isError } = useQuery({
    queryKey: ['lenses', national, scopedState, scopedCity, windowParam],
    queryFn: () =>
      api
        .get('/lenses', {
          params: { state: scopedState, city: scopedCity, window: windowParam, limit_per_lens: 6 },
        })
        .then((r) => r.data as LensesResponse),
    staleTime: 5 * 60 * 1000,
    // Keep the prior window's data on screen while a new window loads, so the
    // grid doesn't flash back to the demo fallback on every toggle.
    placeholderData: (prev) => prev,
  })

  // With no location filter, locationLabel may be a stale city — fall through to
  // the API's resolved label (or a country-wide default) so we never mislabel
  // nationwide data as local.
  const place = unscoped
    ? data?.location_label || 'the U.S.'
    : locationLabel || data?.location_label || 'your area'
  // Preposition that reads correctly for both scopes ("across the U.S." vs
  // "in Tuscaloosa").
  const happeningPrep = unscoped ? 'across' : 'in'

  // Default ('auto') has no chip of its own: we simply highlight whichever grain
  // the API resolved to, so it reads as a normal pre-selected option. An explicit
  // pick highlights its own segment and pins that window across location changes.
  const activeDay = windowSel === 'auto' ? DAYS_BY_WINDOW[data?.window ?? ''] ?? null : windowSel

  // 100% live data — no demo/hardcoded fallback. On a hard failure we show an
  // honest error state; we never fabricate stories.
  const loading = isLoading && !data
  const errored = isError && !data

  const activityTiles = (data?.activity ?? []).map((a, i) => ({
    em: a.icon,
    v: a.value,
    l: a.label,
    bg: ACTIVITY_BG[i % ACTIVITY_BG.length],
    q: a.query || activitySearchQuery(a.label),
  }))

  // Only a card with a real url is a drilldown; url-less cards (e.g. a flag whose
  // spend maps to no decision) are not faked into a link.
  const openCard = (c: RenderCard) => {
    if (c.url) navigate(c.url)
  }

  // Smooth-scroll a lens lane into view (quick-nav chips + activity tiles).
  const scrollToLens = (id: string) => sectionRefs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  const handleActivityClick = (label: string) => {
    // Tiles that map to a lens jump to it; generic tiles ("decisions analyzed")
    // have no single lens, so land on the first POPULATED lane rather than a
    // placeholder ("coming soon").
    const firstPopulated = data?.lenses.find((l) => !l.placeholder && l.cards.length > 0)?.id
    const lensId = activityToLens(label) ?? firstPopulated ?? 'contested'
    scrollToLens(lensId)
  }

  // Stable-ish key for save state & list rendering. Headline+jurisdiction is
  // unique enough for the handful of cards per lens; url wins when present.
  const cardKey = (lensId: string, c: RenderCard, i: number) => c.url || `${lensId}-${c.h}-${c.juris}-${i}`

  return (
    <div className="mt-5 text-left" style={FONT}>
      {/* Popular topics row (retained browse-topics affordance) */}
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-semibold text-[#9bb8b8]">Popular:</span>
        {POPULAR_TOPICS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => onSearch?.(t)}
            className="rounded-full border border-[#d4e8e8] bg-white px-3 py-1 text-[13.5px] font-medium text-[#4a6a6a] transition-colors hover:border-[#1a6b6b]/45 hover:text-[#0f2b2b]"
          >
            {t}
          </button>
        ))}
        <button
          type="button"
          onClick={onBrowseTopics}
          className="inline-flex items-center gap-1 text-[13.5px] font-medium text-[#1a6b6b] underline-offset-2 transition-colors hover:underline"
        >
          Browse topics
          <ChevronRightIcon className="h-4 w-4" aria-hidden />
        </button>
      </div>

      {/* Lens quick-nav + global time control. The lens row is now navigation
          (jump to a lane), not a one-at-a-time selector. */}
      <div className="mb-7 flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-semibold text-[#9bb8b8]">Lenses:</span>
        {LENSES.map((l) => (
          <button
            key={l.id}
            type="button"
            onClick={() => scrollToLens(l.id)}
            className="inline-flex items-center gap-1.5 rounded-full border border-[#e1ebe7] bg-white px-3 py-1.5 text-[13px] font-semibold transition-all hover:-translate-y-px hover:border-[#cfe0db]"
            style={{ color: l.clr }}
          >
            <span className="text-[13px] leading-none" aria-hidden>
              {l.em}
            </span>
            {l.label}
          </button>
        ))}
        <div className="ml-auto inline-flex rounded-full border-[1.5px] border-[#d4e8e8] bg-white p-[3px]">
          {TIME_OPTIONS.map((opt) => {
            const on = activeDay === opt.d
            return (
              <button
                key={opt.d}
                type="button"
                onClick={() => setWindowSel(opt.d)}
                className={`rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition-colors ${
                  on
                    ? 'bg-[#1a6b6b] text-white shadow-[0_2px_6px_rgba(26,107,107,0.30)]'
                    : 'text-[#4a6a6a] hover:text-[#0f2b2b]'
                }`}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* What's happening strip — hidden entirely on a hard failure (no fake data) */}
      {!errored && (
      <>
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 className="text-[20px] font-semibold tracking-tight text-[#0f2b2b]" style={SERIF}>
          What&rsquo;s happening {happeningPrep} {place}
        </h2>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#e7f2ef] px-2.5 py-0.5 text-[11px] font-semibold text-[#1d6b5f]">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#1d6b5f]" />
          Live update
        </span>
        <button
          type="button"
          onClick={onBrowseTopics}
          className="ml-auto inline-flex items-center gap-1 text-[13px] font-medium text-[#1a6b6b] transition-colors hover:underline"
        >
          See all activity
          <ArrowRightIcon className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
      <div className="mb-9 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {loading
          ? Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-[76px] animate-pulse rounded-2xl border border-[#e1ebe7] bg-[#f3f7f6]" />
            ))
          : activityTiles.map((s) => (
              <button
                key={s.l}
                type="button"
                onClick={() => handleActivityClick(s.l)}
                title={`Jump to ${s.l} ${happeningPrep} ${place}`}
                aria-label={`${s.v} ${s.l} — jump to this lens`}
                className="group flex items-center gap-3 rounded-2xl border border-[#e1ebe7] bg-white px-4 py-3.5 text-left transition-all hover:-translate-y-0.5 hover:border-[#cfe0db] hover:shadow-[0_2px_4px_rgba(20,40,35,.06),0_10px_24px_rgba(20,40,35,.08)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a6b6b]/40"
              >
                <span
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-[19px]"
                  style={{ background: s.bg }}
                >
                  {s.em}
                </span>
                <div className="min-w-0">
                  <div className="text-[22px] font-bold leading-none tracking-tight" style={{ color: '#0f2b2b' }}>
                    {s.v}
                  </div>
                  <div className="mt-1 text-[12.5px] leading-snug text-[#56635e] group-hover:text-[#0f2b2b]">{s.l}</div>
                </div>
              </button>
            ))}
      </div>
      </>
      )}

      {/* Stacked lens lanes — the homepage is organized AROUND the lenses: each
          lens is its own section (Money Moves → Follow-the-money drilldown).
          On a hard failure we show one honest error block, never fake stories. */}
      {errored ? (
        <div className="rounded-xl border border-dashed border-[#d4e8e8] bg-white px-6 py-10 text-center text-sm text-[#9bb8b8]">
          Couldn&rsquo;t load stories right now. <b className="text-[#56635e]">Please try again.</b>
        </div>
      ) : (
        LENSES.map((l) => {
          const apiLens = data?.lenses.find((x) => x.id === l.id)
          const lensCards = toRenderCards(apiLens?.cards ?? [], unscoped)
          const placeholder = !!data && (apiLens?.placeholder || lensCards.length === 0)
          return (
            <LensSection
              key={l.id}
              lens={l}
              cards={lensCards}
              placeholder={placeholder}
              loading={loading}
              savedKeys={savedKeys}
              onToggleSave={toggleSave}
              onOpen={openCard}
              cardKey={(c, i) => cardKey(l.id, c, i)}
              onSeeAll={() => onBrowseTopics?.()}
              sectionRef={(el) => {
                sectionRefs.current[l.id] = el
              }}
              body={l.id === 'money' ? <FollowTheMoney embedded /> : undefined}
            />
          )
        })
      )}
    </div>
  )
}
