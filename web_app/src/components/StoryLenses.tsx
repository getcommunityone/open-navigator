import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ChevronRightIcon,
  ChevronLeftIcon,
  BookmarkIcon,
  ArrowRightIcon,
  MapPinIcon,
  PlusIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
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

// "Close to Home" is the cross-lens, personalized landing view; the five signal
// lenses (LENSES, above) are the editorial angles served by /api/lenses. The
// strip is just navigation between these views.
const HOME_LENS: Lens = {
  id: 'home',
  em: '\u{1F3E0}',
  label: 'Close to Home',
  desc: 'Near you, on what you care about',
  clr: '#1a6b6b',
}
const STRIP_LENSES: Lens[] = [HOME_LENS, ...LENSES]

// Value-frame "lenses" — how you READ a decision (Family First, Faith, …), a
// distinct axis from the signal tiles above. There is no card-level theme/topic
// tagging in the warehouse yet, so these render as an honest, disabled "coming
// soon" affordance and do NOT filter the feed. We never fake-filter or fabricate
// data to make the axis look live (CLAUDE.md: No Fabricated Data).
interface ValueFrame {
  id: string
  name: string
  em: string
}
const VALUE_FRAMES: ValueFrame[] = [
  { id: 'family', name: 'Family First', em: '\u{1F46A}' },
  { id: 'faith', name: 'Faith & Community', em: '⛪' },
  { id: 'charitable', name: 'Charitable Impact', em: '\u{1F91D}' },
  { id: 'neighborhood', name: 'Neighborhood Life', em: '\u{1F3D8}\u{FE0F}' },
  { id: 'education', name: 'Education', em: '\u{1F393}' },
  { id: 'economy', name: 'Local Economy', em: '\u{1F4BC}' },
]

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
// HScroll — a horizontal scroll rail with chevron buttons that appear only when
// there is more to scroll in that direction. Touch-swipe still works on mobile;
// the chevrons add an explicit affordance (and a click target) for the lens
// strip and the value-frame / signal filter rows.
// ---------------------------------------------------------------------------
function HScroll({
  children,
  innerClassName = 'flex items-center gap-2',
  step = 200,
}: {
  children: React.ReactNode
  innerClassName?: string
  step?: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [edges, setEdges] = useState({ left: false, right: false })

  const update = useCallback(() => {
    const el = ref.current
    if (!el) return
    setEdges({
      left: el.scrollLeft > 4,
      right: el.scrollLeft < el.scrollWidth - el.clientWidth - 4,
    })
  }, [])

  useEffect(() => {
    const el = ref.current
    if (!el) return
    update()
    const ro = new ResizeObserver(() => update())
    ro.observe(el)
    // Re-measure once webfonts settle (chip widths shift on swap).
    if (document.fonts?.ready) document.fonts.ready.then(update).catch(() => {})
    return () => ro.disconnect()
  }, [update, children])

  const nudge = (dir: number) => ref.current?.scrollBy({ left: dir * step, behavior: 'smooth' })

  const arrow = (side: 'left' | 'right') => (
    <button
      type="button"
      onClick={() => nudge(side === 'left' ? -1 : 1)}
      aria-label={side === 'left' ? 'Scroll left' : 'Scroll right'}
      className={`absolute top-1/2 z-10 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full border border-[#e1ebe7] bg-white text-[#56635e] shadow-[0_1px_5px_rgba(20,40,35,.18)] transition-colors hover:border-[#1a6b6b] hover:text-[#1a6b6b] ${
        side === 'left' ? '-left-1' : '-right-1'
      }`}
    >
      {side === 'left' ? (
        <ChevronLeftIcon className="h-3.5 w-3.5" aria-hidden />
      ) : (
        <ChevronRightIcon className="h-3.5 w-3.5" aria-hidden />
      )}
    </button>
  )

  return (
    <div className="relative min-w-0 flex-1">
      <div
        ref={ref}
        onScroll={update}
        className={`${innerClassName} overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden`}
      >
        {children}
      </div>
      {edges.left && arrow('left')}
      {edges.right && arrow('right')}
    </div>
  )
}

// Advisory note (e.g. Raised Eyebrows) shown above a lens's cards.
function LensNote({ note }: { note: string }) {
  return (
    <div className="mx-0.5 mb-4 flex gap-2 rounded-lg border border-[#e3dcf5] border-l-[3px] border-l-[#7a5cd0] bg-[#f4f0fc] px-3.5 py-2.5 text-[12.5px] leading-snug text-[#5b4a8a]">
      <span>{note}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// SingleLensBody — the feed body when one signal lens is selected from the
// strip: a horizontal swipe carousel of that lens's real cards, with honest
// loading / placeholder / empty states. Never fabricates stories.
// ---------------------------------------------------------------------------
interface SingleLensBodyProps {
  lens: Lens
  cards: RenderCard[]
  placeholder: boolean
  loading: boolean
  savedKeys: Set<string>
  onToggleSave: (key: string) => void
  onOpen: (card: RenderCard) => void
  cardKey: (card: RenderCard, i: number) => string
}

function SingleLensBody({
  lens,
  cards,
  placeholder,
  loading,
  savedKeys,
  onToggleSave,
  onOpen,
  cardKey,
}: SingleLensBodyProps) {
  if (loading) {
    return (
      <div className="flex gap-4 overflow-hidden">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-44 w-[300px] shrink-0 animate-pulse rounded-2xl border border-[#e1ebe7] bg-[#f3f7f6]" />
        ))}
      </div>
    )
  }
  if (placeholder) {
    return (
      <div className="rounded-xl border border-dashed border-[#d4e8e8] bg-white px-6 py-8 text-center text-sm text-[#9bb8b8]">
        Coming soon — we&rsquo;re still extracting the signals for this lens.
      </div>
    )
  }
  if (cards.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-[#d4e8e8] bg-white px-6 py-8 text-center text-sm text-[#9bb8b8]">
        Nothing in this window. <b className="text-[#56635e]">Try a wider time frame.</b>
      </div>
    )
  }
  return (
    <StoryCarousel
      cards={cards}
      lens={lens}
      savedKeys={savedKeys}
      onToggleSave={onToggleSave}
      onOpen={onOpen}
      cardKey={cardKey}
    />
  )
}

export default function StoryLenses({ locationLabel, stateCode, city, national, onSearch, onBrowseTopics }: StoryLensesProps) {
  const navigate = useNavigate()
  // Which strip view is active: 'home' (cross-lens, personalized) or a single
  // signal lens id. Signals narrow the Close-to-Home feed to the chosen lenses.
  const [lensId, setLensId] = useState('home')
  const [signals, setSignals] = useState<Set<string>>(() => new Set())
  const toggleSignal = (id: string) =>
    setSignals((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
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

  // Per-lens normalized cards from the live response (empty until data loads).
  const lensCards = useMemo(
    () =>
      LENSES.map((l) => {
        const apiLens = data?.lenses.find((x) => x.id === l.id)
        const cards = toRenderCards(apiLens?.cards ?? [], unscoped)
        const placeholder = !!data && (!!apiLens?.placeholder || cards.length === 0)
        return { lens: l, cards, placeholder }
      }),
    [data, unscoped],
  )

  // Close-to-Home feed: every lens's real cards in one stream, tagged with their
  // lens, narrowed to the selected signals (if any), and deduped so a decision
  // surfacing in two lenses shows once (under the first lens that ranked it).
  const homeFeed = useMemo(() => {
    const out: { card: RenderCard; lens: Lens }[] = []
    const seen = new Set<string>()
    for (const { lens, cards } of lensCards) {
      if (signals.size > 0 && !signals.has(lens.id)) continue
      for (const card of cards) {
        const k = card.url || `${card.h}__${card.juris}`
        if (seen.has(k)) continue
        seen.add(k)
        out.push({ card, lens })
      }
    }
    return out
  }, [lensCards, signals])

  const selected = STRIP_LENSES.find((l) => l.id === lensId) ?? HOME_LENS
  const isHome = lensId === 'home'
  const sel = lensCards.find((x) => x.lens.id === lensId)

  // Real money-lens decisions, normalized for the Follow-the-money body. The
  // money lens stat labeled "Amount" carries the decision's net dollar impact.
  const moneyDecisions = useMemo(
    () =>
      (lensCards.find((x) => x.lens.id === 'money')?.cards ?? []).map((c) => ({
        h: c.h,
        juris: c.juris,
        url: c.url,
        amount: c.stats.find((s) => s.l === 'Amount')?.v,
      })),
    [lensCards],
  )

  // Stable-ish key for save state & list rendering. Headline+jurisdiction is
  // unique enough for the handful of cards per lens; url wins when present.
  const keyFor = (id: string, c: RenderCard, i: number) => c.url || `${id}-${c.h}-${c.juris}-${i}`

  // An activity tile jumps to its lens when it maps to one; otherwise it runs the
  // derived search (generic tiles like "decisions analyzed").
  const onActivity = (label: string) => {
    const target = activityToLens(label)
    if (target && STRIP_LENSES.some((l) => l.id === target)) setLensId(target)
    else onSearch?.(activitySearchQuery(label))
  }

  return (
    <div className="mt-5 text-left" style={FONT}>
      {/* Lens strip — Close to Home + the five signal lenses. Selecting a card
          switches the feed below (persistent navigation; nothing gets lost). */}
      <HScroll innerClassName="flex items-start gap-2.5 pb-1" step={170}>
        {STRIP_LENSES.map((l) => {
          const on = lensId === l.id
          return (
            <button
              key={l.id}
              type="button"
              onClick={() => setLensId(l.id)}
              aria-pressed={on}
              className="relative w-[150px] shrink-0 rounded-2xl bg-white px-3.5 py-3 text-left transition-all hover:-translate-y-px"
              style={{
                border: `1.5px solid ${on ? l.clr : '#e1ebe7'}`,
                boxShadow: on ? `0 4px 14px ${l.clr}2e` : '0 1px 2px rgba(20,40,35,.04)',
              }}
            >
              {l.id === 'home' && (
                <span
                  className="absolute right-2.5 top-2.5 inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9.5px] font-bold"
                  style={{ color: '#1a6b6b', background: 'rgba(26,107,107,0.10)' }}
                >
                  <SparklesIcon className="h-2.5 w-2.5" aria-hidden /> FOR YOU
                </span>
              )}
              <span
                className="mb-2.5 flex h-9 w-9 items-center justify-center rounded-xl text-[17px]"
                style={{ background: `color-mix(in srgb, ${l.clr} 12%, #fff)` }}
                aria-hidden
              >
                {l.em}
              </span>
              <div className="mb-1 text-[14px] font-bold leading-tight" style={{ color: l.clr }}>
                {l.label}
              </div>
              <div className="text-[12px] leading-snug text-[#56635e]">{l.desc}</div>
            </button>
          )
        })}
      </HScroll>

      {/* Header for the selected view */}
      <div className="mb-2.5 mt-4 flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1.5">
          <span
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-[20px]"
            style={{ background: `color-mix(in srgb, ${selected.clr} 12%, #fff)` }}
            aria-hidden
          >
            {selected.em}
          </span>
          <div className="min-w-0">
            <h2 className="text-[22px] font-semibold leading-tight tracking-tight" style={{ ...SERIF, color: selected.clr }}>
              {selected.label}
            </h2>
            <p className="text-[13.5px] text-[#56635e]">{selected.desc}</p>
          </div>
          {isHome && (
            <span
              className="inline-flex shrink-0 items-center gap-1.5 rounded-full border-[1.5px] px-2.5 py-1"
              style={{ background: 'rgba(26,107,107,0.08)', borderColor: 'rgba(26,107,107,0.35)' }}
            >
              <MapPinIcon className="h-3.5 w-3.5 text-[#1a6b6b]" aria-hidden />
              <span className="text-[13px] font-bold text-[#0f2b2b]">{place}</span>
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => onBrowseTopics?.()}
          className="inline-flex shrink-0 items-center gap-1 text-[13.5px] font-semibold text-[#1a6b6b] transition-colors hover:underline"
        >
          See all
          <ArrowRightIcon className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>

      {/* Time-window control (applies to every view) */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-[#9bb8b8]">When</span>
        <div className="inline-flex rounded-full border-[1.5px] border-[#d4e8e8] bg-white p-[3px]">
          {TIME_OPTIONS.map((opt) => {
            const on = activeDay === opt.d
            return (
              <button
                key={opt.d}
                type="button"
                onClick={() => setWindowSel(opt.d)}
                className={`rounded-full px-3 py-1.5 text-[12.5px] font-semibold transition-colors ${
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

      {/* Personalization bar — Close to Home only */}
      {isHome && (
        <div className="mb-3 rounded-2xl border border-[#e1ebe7] bg-white p-3">
          {/* Value-frames — how you READ a decision. No card-level theme tagging
              exists yet, so these are an honest, disabled "coming soon" affordance
              and never filter or fabricate data (CLAUDE.md: No Fabricated Data). */}
          <div className="flex items-center gap-3">
            <span className="shrink-0 text-[10.5px] font-semibold uppercase tracking-wide text-[#9bb8b8]">Lens</span>
            <HScroll>
              {VALUE_FRAMES.map((p) => (
                <span
                  key={p.id}
                  title="Personalized value-frames are coming soon"
                  className="inline-flex shrink-0 cursor-not-allowed items-center gap-1.5 rounded-full border border-[#e1ebe7] bg-[#f3f7f6] px-3 py-1.5 text-[12.5px] font-semibold text-[#9bb8b8]"
                >
                  <span aria-hidden>{p.em}</span>
                  {p.name}
                </span>
              ))}
              <span className="inline-flex shrink-0 items-center rounded-full bg-[#eef5f3] px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-[#1d6b5f]">
                soon
              </span>
              <span className="inline-flex shrink-0 cursor-not-allowed items-center gap-1 rounded-full border border-dashed border-[#e1ebe7] px-2.5 py-1.5 text-[12.5px] font-semibold text-[#bcd0cb]">
                <PlusIcon className="h-3 w-3" aria-hidden /> Add
              </span>
            </HScroll>
          </div>

          {/* Signals — live; narrow the Close-to-Home feed to the chosen lenses */}
          <div className="mt-2.5 flex items-center gap-3 border-t border-[#e1ebe7] pt-2.5">
            <span className="shrink-0 text-[10.5px] font-semibold uppercase tracking-wide text-[#9bb8b8]">Signal</span>
            <HScroll>
              {LENSES.map((l) => {
                const on = signals.has(l.id)
                return (
                  <button
                    key={l.id}
                    type="button"
                    onClick={() => toggleSignal(l.id)}
                    aria-pressed={on}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-[12.5px] font-semibold transition-all"
                    style={{
                      background: on ? l.clr : '#fff',
                      border: `1px solid ${on ? l.clr : '#e1ebe7'}`,
                      color: on ? '#fff' : '#0f2b2b',
                    }}
                  >
                    <span aria-hidden>{l.em}</span>
                    {l.label}
                  </button>
                )
              })}
              {signals.size > 0 && (
                <button
                  type="button"
                  onClick={() => setSignals(new Set())}
                  className="shrink-0 text-[12px] font-semibold text-[#56635e] underline underline-offset-2 hover:text-[#0f2b2b]"
                >
                  Clear
                </button>
              )}
            </HScroll>
          </div>
        </div>
      )}

      {/* What's happening strip — Close to Home only; hidden on a hard failure */}
      {isHome && !errored && (
        <div className="mb-4">
          <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            <h3 className="text-[15px] font-semibold tracking-tight text-[#0f2b2b]" style={SERIF}>
              What&rsquo;s happening {happeningPrep} {place}
            </h3>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[#e7f2ef] px-2.5 py-0.5 text-[11px] font-semibold text-[#1d6b5f]">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#1d6b5f]" />
              Live update
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {loading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-[72px] animate-pulse rounded-2xl border border-[#e1ebe7] bg-[#f3f7f6]" />
                ))
              : activityTiles.map((s) => (
                  <button
                    key={s.l}
                    type="button"
                    onClick={() => onActivity(s.l)}
                    title={`${s.v} ${s.l}`}
                    className="group flex items-center gap-3 rounded-2xl border border-[#e1ebe7] bg-white px-4 py-3 text-left transition-all hover:-translate-y-0.5 hover:border-[#cfe0db] hover:shadow-[0_2px_4px_rgba(20,40,35,.06),0_10px_24px_rgba(20,40,35,.08)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a6b6b]/40"
                  >
                    <span
                      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-[19px]"
                      style={{ background: s.bg }}
                    >
                      {s.em}
                    </span>
                    <div className="min-w-0">
                      <div className="text-[22px] font-bold leading-none tracking-tight text-[#0f2b2b]">{s.v}</div>
                      <div className="mt-1 text-[12.5px] leading-snug text-[#56635e] group-hover:text-[#0f2b2b]">{s.l}</div>
                    </div>
                  </button>
                ))}
          </div>
        </div>
      )}

      {/* Feed. 100% live data — honest error / loading / empty states, never
          fabricated stories. */}
      {errored ? (
        <div className="rounded-xl border border-dashed border-[#d4e8e8] bg-white px-6 py-10 text-center text-sm text-[#9bb8b8]">
          Couldn&rsquo;t load stories right now. <b className="text-[#56635e]">Please try again.</b>
        </div>
      ) : isHome ? (
        loading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-48 animate-pulse rounded-2xl border border-[#e1ebe7] bg-[#f3f7f6]" />
            ))}
          </div>
        ) : homeFeed.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[#d4e8e8] bg-white px-6 py-10 text-center text-sm text-[#9bb8b8]">
            {signals.size > 0 ? (
              <>
                No decisions match those signals in this window.{' '}
                <b className="text-[#56635e]">Clear a filter or widen the time frame.</b>
              </>
            ) : (
              <>
                Nothing close to home in this window. <b className="text-[#56635e]">Try a wider time frame.</b>
              </>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {homeFeed.map(({ card, lens }, i) => {
              const key = keyFor(lens.id, card, i)
              return (
                <StoryCard
                  key={key}
                  card={card}
                  lens={lens}
                  saved={savedKeys.has(key)}
                  onToggleSave={() => toggleSave(key)}
                  onOpen={() => openCard(card)}
                />
              )
            })}
          </div>
        )
      ) : lensId === 'money' ? (
        // Money Moves keeps its Follow-the-money drilldown body, fed with the
        // real money-lens decisions + scope so every figure is warehouse-traced.
        <FollowTheMoney
          embedded
          national={national}
          stateCode={stateCode}
          city={city}
          moneyCards={moneyDecisions}
        />
      ) : (
        <>
          {selected.note && <LensNote note={selected.note} />}
          <SingleLensBody
            lens={selected}
            cards={sel?.cards ?? []}
            placeholder={!!sel?.placeholder}
            loading={loading}
            savedKeys={savedKeys}
            onToggleSave={toggleSave}
            onOpen={openCard}
            cardKey={(c, i) => keyFor(selected.id, c, i)}
          />
        </>
      )}
    </div>
  )
}
