import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronRightIcon, ChevronLeftIcon, BookmarkIcon, ArrowRightIcon } from '@heroicons/react/24/outline'
import { BookmarkIcon as BookmarkSolidIcon } from '@heroicons/react/24/solid'
import api from '../lib/api'
import { useIsMobile } from '../hooks/useMediaQuery'

/**
 * StoryLenses — the homepage "What's happening near you" section.
 *
 * Re-ranks civic activity by editorial *lenses* (Contested, Money Moves,
 * Raised Eyebrows, Moving Fast, Watch Next) rather than by topic, with a live
 * activity strip, a time-frame control, and a story-card grid.
 *
 * Live data comes from `GET /api/lenses` (state/city/window scoped). The
 * `CARDS` / `activityStats` demo constants below are kept ONLY as a graceful
 * fallback for the error / no-data path — analogous to the old
 * FALLBACK_TRENDING in Home.tsx. Lenses the API marks `placeholder: true`
 * (e.g. flags, soon — signals not yet extracted) render an honest empty state,
 * never demo cards.
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
interface Card {
  badge?: string
  /** Negative = past, positive = upcoming. */
  days: number
  h: string
  stats: Stat[]
  juris: string
}

const CARDS: Record<string, Card[]> = {
  contested: [
    { days: -1, h: 'Northport adds a $40 monthly trash fee after an hour of pushback', stats: [{ v: '3–2', l: 'Vote' }, { v: '18', l: 'Spoke against' }, { v: '+$480', l: 'Impact / year', tone: 'green' }], juris: 'City Council' },
    { days: -22, h: 'Council splits sharply over a downtown bar curfew', stats: [{ v: '4–3', l: 'Vote' }, { v: 'Tabled', l: 'Outcome', tone: 'amber' }, { v: '11', l: 'Spoke' }], juris: 'City Council' },
    { days: -68, h: 'Commission can’t agree on the rural broadband contract', stats: [{ v: 'Tie', l: 'Deadlock', tone: 'red' }, { v: '$4M', l: 'At stake' }, { v: '1', l: 'Bidder', tone: 'red' }], juris: 'County Commission' },
    { days: -210, h: 'Annexation barely passes after a packed three-hour hearing', stats: [{ v: '4–3', l: 'Vote' }, { v: '3 hr', l: 'Hearing' }, { v: '60+', l: 'Attended' }], juris: 'City Council' },
  ],
  money: [
    { days: -1, h: 'City approves $2.3M contract with developer connected to council donor', stats: [{ v: '$2.3M', l: 'Contract value', tone: 'green' }, { v: 'Donor link', l: 'Disclosed', tone: 'amber' }, { v: 'No', l: 'Bids received', tone: 'red' }], juris: 'City Council' },
    { days: -24, h: 'Northport water rates rise again — 9% this time', stats: [{ v: '+9%', l: 'Rate hike', tone: 'red' }, { v: '3rd', l: 'In 4 years' }, { v: '~33%', l: 'Since 2022' }], juris: 'Utilities Board' },
    { days: -70, h: 'County awards a $4.2M road contract to a single bidder', stats: [{ v: '$4.2M', l: 'Contract', tone: 'green' }, { v: '1', l: 'Bidder', tone: 'red' }, { v: '0', l: 'Competing bids', tone: 'red' }], juris: 'County Commission' },
    { days: -190, h: 'City refinanced $30M in debt to free up budget room', stats: [{ v: '$30M', l: 'Refinanced', tone: 'green' }, { v: '3 yr', l: 'Runway' }, { v: 'Consent', l: 'Passed on' }], juris: 'City Council' },
  ],
  flags: [
    { days: -2, h: 'One-third of traffic revenue comes from just two speed traps', stats: [{ v: '$1.1M', l: 'From tickets', tone: 'purple' }, { v: '32%', l: 'Of city revenue', tone: 'amber' }, { v: '4 locations', l: 'Concentrated', tone: 'blue' }], juris: 'Finance Committee' },
    { days: -15, h: 'Repeated purchases land just under the $5,000 approval limit', stats: [{ v: '7 buys', l: '~$4,950 each', tone: 'red' }, { v: '$5K', l: 'Sign-off line', tone: 'amber' }, { v: '0', l: 'Board reviews', tone: 'red' }], juris: 'County Procurement' },
    { days: -30, h: 'A contract went to a vendor sharing an address with an official’s relative', stats: [{ v: 'Match', l: 'Entity resolution', tone: 'purple' }, { v: 'No', l: 'Recusal', tone: 'red' }, { v: '1', l: 'Member tied' }], juris: 'City Council' },
    { days: -44, h: 'One official’s travel reimbursements run roughly 4x the board average', stats: [{ v: '4×', l: 'Peer median', tone: 'red' }, { v: 'Travel', l: 'Category', tone: 'amber' }, { v: '12 mo', l: 'Window' }], juris: 'City Council' },
  ],
  soon: [
    { days: -2, h: 'A $1.8M software contract passed on the consent agenda', stats: [{ v: '0 min', l: 'Debate', tone: 'red' }, { v: '$1.8M', l: 'Bundled', tone: 'green' }, { v: '1', l: 'Vote' }], juris: 'County Commission' },
    { days: -4, h: 'Fee-schedule changes adopted with no separate discussion', stats: [{ v: 'Consent', l: 'Track', tone: 'amber' }, { v: 'All', l: 'Permit fees up' }, { v: '0', l: 'Comments' }], juris: 'City Council' },
    { days: -8, h: 'Council quietly extended the mayor’s emergency powers', stats: [{ v: '6 mo', l: 'Extension', tone: 'amber' }, { v: 'Packaged', l: 'Resolution' }, { v: '0 min', l: 'Discussion', tone: 'red' }], juris: 'City Council' },
  ],
  next: [
    { days: 3, h: 'Public comment on the 2027 budget closes Friday', stats: [{ v: '3 days', l: 'To weigh in', tone: 'amber' }, { v: 'Open', l: 'Comment', tone: 'green' }, { v: '$2.3M', l: 'New spend' }], juris: 'City Council' },
    { days: 5, h: 'The downtown parking deck goes to a vote Tuesday', stats: [{ v: '5 days', l: 'Until vote', tone: 'amber' }, { v: '$9M', l: 'Project', tone: 'green' }, { v: '2 yr', l: 'Debated' }], juris: 'City Council' },
    { days: 8, h: 'Last hearing on the noise ordinance before adoption', stats: [{ v: 'Final', l: 'Reading', tone: 'red' }, { v: '8 days', l: 'Until adopted' }, { v: 'Open', l: 'Comment', tone: 'green' }], juris: 'City Council' },
    { days: 24, h: 'Comprehensive plan update opens for public input next month', stats: [{ v: '~24 days', l: 'Opens' }, { v: '10 yr', l: 'Zoning impact', tone: 'blue' }, { v: 'Draft', l: 'Stage' }], juris: 'Planning' },
  ],
}

const TIME_OPTIONS: { d: number; label: string }[] = [
  { d: 7, label: 'Week' },
  { d: 31, label: 'Month' },
  { d: 92, label: 'Quarter' },
  { d: 366, label: 'Year' },
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
const WINDOW_BY_DAYS: Record<number, string> = { 7: 'week', 31: 'month', 92: 'quarter', 366: 'year', 999999: 'all' }
const WINDOW_LABEL: Record<string, string> = { week: 'Week', month: 'Month', quarter: 'Quarter', year: 'Year', all: 'All time' }
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
}

// Relative-time label from an ISO yyyy-mm-dd date (reuses rel()'s wording).
function relFromDate(dateStr?: string): string {
  if (!dateStr) return ''
  const then = new Date(`${dateStr}T00:00:00`)
  if (Number.isNaN(then.getTime())) return ''
  const days = Math.round((then.getTime() - Date.now()) / 86_400_000)
  return rel(days)
}

const DEMO_ACTIVITY: { em: string; v: string; l: string; bg: string; q: string }[] = [
  { em: '\u{1F525}', v: '3', l: 'contested votes this week', bg: '#fdeeeb', q: 'contested' },
  { em: '\u{1F4B2}', v: '$2.3M', l: 'in new spending approved', bg: '#e7f2ef', q: 'budget' },
  { em: '\u{1F441}\u{FE0F}', v: '124', l: 'public comments submitted', bg: '#efebfb', q: 'public comment' },
  { em: '⚠️', v: '2', l: 'major projects proposed', bg: '#fbf3e2', q: 'projects' },
]

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
            <div key={key} className="w-[84%] max-w-[340px] shrink-0 snap-start">
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

export default function StoryLenses({ locationLabel, stateCode, city, onSearch, onBrowseTopics }: StoryLensesProps) {
  const navigate = useNavigate()
  const isMobile = useIsMobile()
  const [active, setActive] = useState<string>('contested')
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

  const { data, isLoading, isError } = useQuery({
    queryKey: ['lenses', stateCode, city, windowParam],
    queryFn: () =>
      api
        .get('/lenses', {
          params: { state: stateCode || undefined, city: city || undefined, window: windowParam, limit_per_lens: 6 },
        })
        .then((r) => r.data as LensesResponse),
    staleTime: 5 * 60 * 1000,
    // Keep the prior window's data on screen while a new window loads, so the
    // grid doesn't flash back to the demo fallback on every toggle.
    placeholderData: (prev) => prev,
  })

  const lens = LENSES.find((l) => l.id === active) ?? LENSES[0]
  const place = locationLabel || data?.location_label || 'your area'

  // In auto mode the "Auto" segment is active and labelled with the grain the API
  // resolved to; an explicit pick highlights its own day segment instead.
  const autoActive = windowSel === 'auto'
  const autoLabel = autoActive && data?.window ? `Auto · ${WINDOW_LABEL[data.window] ?? ''}` : 'Auto'

  // Fall back to the demo content only on a hard failure (no successful payload).
  const useDemo = isError || !data
  const loading = isLoading && !data
  const apiLens = data?.lenses.find((l) => l.id === active)
  const isPlaceholder = !!data && (apiLens?.placeholder || (apiLens?.cards.length ?? 0) === 0)

  const cards: RenderCard[] = useDemo
    ? (CARDS[active] ?? []).map((c) => ({ h: c.h, stats: c.stats, juris: c.juris, when: rel(c.days) }))
    : (apiLens?.cards ?? []).map((c) => ({
        h: c.headline,
        stats: c.stats.map((s) => ({ v: s.value, l: s.label, tone: s.tone })),
        juris: c.jurisdiction,
        when: relFromDate(c.date),
        url: c.url,
      }))

  const activityTiles = useDemo
    ? DEMO_ACTIVITY
    : (data?.activity ?? []).map((a, i) => ({
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

  // Activity tiles switch the active lens and scroll to the (location-scoped)
  // story grid — NOT a keyword search, which leaked across jurisdictions
  // (e.g. a Northport "contested" tile returning a Jefferson County topic).
  const storiesRef = useRef<HTMLDivElement>(null)
  const handleActivityClick = (label: string) => {
    const lensId = activityToLens(label)
    if (lensId) setActive(lensId)
    storiesRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  // Stable-ish key for save state & list rendering. Headline+jurisdiction is
  // unique enough for the handful of cards per lens; url wins when present.
  const cardKey = (c: RenderCard, i: number) => c.url || `${active}-${c.h}-${c.juris}-${i}`

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

      {/* Lens cards row — wraps so every lens stays visible on mobile */}
      <div className="mb-7 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {LENSES.map((l) => {
          const on = active === l.id
          return (
            <button
              key={l.id}
              type="button"
              onClick={() => setActive(l.id)}
              className="flex flex-col items-start gap-1.5 rounded-2xl border bg-white px-4 py-3.5 text-left transition-all hover:-translate-y-0.5"
              style={{
                borderColor: on ? l.clr : '#e1ebe7',
                boxShadow: on
                  ? `0 0 0 1.5px ${l.clr}, 0 6px 16px ${l.clr}26`
                  : '0 1px 2px rgba(20,40,35,.04),0 6px 16px rgba(20,40,35,.05)',
              }}
            >
              <span
                className="flex h-9 w-9 items-center justify-center rounded-xl text-[17px]"
                style={{ background: `color-mix(in srgb, ${l.clr} 12%, #fff)` }}
              >
                {l.em}
              </span>
              <span className="text-[15px] font-bold tracking-tight" style={{ color: l.clr }}>
                {l.label}
              </span>
              <span className="text-[12.5px] leading-snug text-[#56635e]">{l.desc}</span>
            </button>
          )
        })}

        {/* View all */}
        <button
          type="button"
          onClick={onBrowseTopics}
          className="flex flex-col items-center justify-center gap-1 rounded-2xl border border-[#e1ebe7] bg-white px-4 py-3.5 text-[#1a6b6b] transition-colors hover:bg-[#f3f7f6]"
          aria-label="View all lenses"
        >
          <ChevronRightIcon className="h-5 w-5" aria-hidden />
          <span className="text-[11px] font-semibold leading-tight">View all</span>
        </button>
      </div>

      {/* What's happening strip */}
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 className="text-[20px] font-semibold tracking-tight text-[#0f2b2b]" style={SERIF}>
          What&rsquo;s happening in {place}
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
      <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {activityTiles.map((s) => (
          <button
            key={s.l}
            type="button"
            onClick={() => handleActivityClick(s.l)}
            title={`Show ${s.l} near ${place}`}
            aria-label={`${s.v} ${s.l} — show these near ${place}`}
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

      {/* Top stories header + time control */}
      <div ref={storiesRef} className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2 scroll-mt-4">
        <h2 className="text-[20px] font-semibold tracking-tight text-[#0f2b2b]" style={SERIF}>
          Top stories near {place}
        </h2>
        <div className="ml-auto inline-flex rounded-full border-[1.5px] border-[#d4e8e8] bg-white p-[3px]">
          <button
            type="button"
            onClick={() => setWindowSel('auto')}
            title="Automatically pick the best time range for your area"
            className={`rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition-colors ${
              autoActive
                ? 'bg-[#1a6b6b] text-white shadow-[0_2px_6px_rgba(26,107,107,0.30)]'
                : 'text-[#4a6a6a] hover:text-[#0f2b2b]'
            }`}
          >
            {autoLabel}
          </button>
          {TIME_OPTIONS.map((opt) => {
            const on = windowSel === opt.d
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

      {/* Advisory note (Raised Eyebrows) */}
      {lens.note && (
        <div className="mx-0.5 mb-4 flex gap-2 rounded-lg border border-[#e3dcf5] border-l-[3px] border-l-[#7a5cd0] bg-[#f4f0fc] px-3.5 py-2.5 text-[12.5px] leading-snug text-[#5b4a8a]">
          <span>{lens.note}</span>
        </div>
      )}

      {/* Card grid */}
      {loading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-44 animate-pulse rounded-2xl border border-[#e1ebe7] bg-[#f3f7f6]" />
          ))}
        </div>
      ) : isPlaceholder ? (
        <div className="rounded-xl border border-dashed border-[#d4e8e8] bg-white px-6 py-10 text-center text-sm text-[#9bb8b8]">
          Coming soon — we&rsquo;re still extracting the signals for this lens.
        </div>
      ) : cards.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#d4e8e8] bg-white px-6 py-10 text-center text-sm text-[#9bb8b8]">
          Nothing in this window. <b className="text-[#56635e]">Try a wider time frame.</b>
        </div>
      ) : isMobile ? (
        // Mobile → swipe carousel (#1): native scroll-snap, peeking next card, dots.
        <StoryCarousel
          cards={cards}
          lens={lens}
          savedKeys={savedKeys}
          onToggleSave={toggleSave}
          onOpen={openCard}
          cardKey={cardKey}
        />
      ) : (
        // Desktop → reflow grid (#2): auto-fill columns, no JS.
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
          {cards.map((c, i) => {
            const key = cardKey(c, i)
            return (
              <StoryCard
                key={key}
                card={c}
                lens={lens}
                saved={savedKeys.has(key)}
                onToggleSave={() => toggleSave(key)}
                onOpen={() => openCard(c)}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
