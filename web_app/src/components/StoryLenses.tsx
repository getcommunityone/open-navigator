import { useMemo, useState } from 'react'
import { ArrowTrendingUpIcon, ChevronDownIcon } from '@heroicons/react/24/outline'

/**
 * StoryLenses — the homepage "What's interesting near you" section.
 *
 * Replaces the flat "Trending" pill row with a set of editorial *lenses*
 * (Contested, Money moves, Near you, …) that re-rank civic activity by what's
 * interesting rather than by topic, plus a time-frame control and a card grid.
 *
 * The card data here is illustrative demo content (there is no
 * `interestingness_score` endpoint yet) — analogous to FALLBACK_TRENDING in
 * Home.tsx. The component is intentionally self-contained so it can later be
 * swapped to live API data without touching Home.tsx.
 */

const FONT = { fontFamily: "'DM Sans', sans-serif" } as const
const SERIF = { fontFamily: "'Newsreader', Georgia, 'Times New Roman', serif" } as const

interface Lens {
  id: string
  em: string
  label: string
  clr: string
  blurb: string
  /** Optional advisory shown above the grid (used by the "Raised Eyebrows" lens). */
  note?: string
}

const LENSES: Lens[] = [
  {
    id: 'contested',
    em: '\u{1F525}',
    label: 'Contested',
    clr: '#df5430',
    blurb:
      'Split votes, heated debate, and decisions people fought over. Signal: vote margin + competing views + opposition in public comment.',
  },
  {
    id: 'money',
    em: '\u{1F4B8}',
    label: 'Money moves',
    clr: '#b07d18',
    blurb:
      'New fees, big spends, and rate hikes — where your tax dollars actually go. Signal: extracted $ amounts ranked against the COFOG baseline.',
  },
  {
    id: 'near',
    em: '\u{1F4CD}',
    label: 'Near you',
    clr: '#1d6b5f',
    blurb:
      'Rezonings, road work, and decisions on your street. Signal: geocoded addresses in the item vs. your location.',
  },
  {
    id: 'new',
    em: '\u{2728}',
    label: 'New ideas',
    clr: '#6b5bd2',
    blurb:
      'Pilots, first-time proposals, and things this body has never tried. Signal: canonical subject slug appearing for the first time.',
  },
  {
    id: 'people',
    em: '\u{1F5E3}\u{FE0F}',
    label: 'People showed up',
    clr: '#e0608a',
    blurb:
      'The meetings residents packed and the mics they lined up for. Signal: public-comment speaker count + length of the comment section.',
  },
  {
    id: 'changed',
    em: '\u{1F504}',
    label: 'Changed course',
    clr: '#2f6fb0',
    blurb:
      'Reversals, walk-backs, and U-turns on past decisions. Signal: cross-session slug linking detecting a vote that undoes a prior one.',
  },
  {
    id: 'soon',
    em: '\u{23F0}',
    label: 'Decide soon',
    clr: '#d57a1e',
    blurb:
      'Open comment periods and votes coming up — your last chance to weigh in. Signal: future dates + tabled items scheduled to return.',
  },
  {
    id: 'slipped',
    em: '\u{1F575}\u{FE0F}',
    label: 'Slipped through',
    clr: '#6a6f8a',
    blurb:
      'Big-impact items that passed on the consent agenda with no discussion. Signal: high impact score + near-zero debate time.',
  },
  {
    id: 'flags',
    em: '\u{1F928}',
    label: 'Raised Eyebrows',
    clr: '#b0384a',
    note:
      '⚠ Flags are unverified anomalies pulled from public records — a prompt to look closer, not a finding of wrongdoing. Every card links to the underlying record so you can judge for yourself.',
    blurb:
      'Out-of-district addresses, just-under-the-limit spending, vendor–official ties, and expense outliers. Signal: address vs. district boundary, threshold structuring, donor–contract & relative–vendor matches, per-peer expense outliers.',
  },
]

interface Card {
  badge: string
  /** Negative = in the past, positive = upcoming. */
  days: number
  h: string
  p: string
  juris: string
}

// days: negative = in the past, positive = upcoming
const CARDS: Record<string, Card[]> = {
  contested: [
    { badge: '3–2 vote · 18 spoke against', days: -2, h: 'Northport adds a $40 monthly trash fee after an hour of pushback', p: 'Residents packed the chamber to oppose it; two council members flipped before the final vote.', juris: 'Northport City Council' },
    { badge: '4–3 split', days: -22, h: 'Council splits sharply over a downtown bar curfew', p: 'Supporters cited noise complaints; opponents warned it would gut nightlife. Tabled for revision.', juris: 'Tuscaloosa City Council' },
    { badge: 'Deadlocked · tabled', days: -68, h: 'Commission can’t agree on the rural broadband contract', p: 'A tie vote sent the $4M proposal back to committee amid questions about the lone bidder.', juris: 'Tuscaloosa County' },
    { badge: '4–3 · 3-hr hearing', days: -210, h: 'Annexation barely passes after a packed three-hour hearing', p: 'One of the most divisive votes of the year, decided by a single seat near midnight.', juris: 'Northport City Council' },
  ],
  money: [
    { badge: '$12.0M', days: -4, h: 'Tuscaloosa commits $12M to a riverfront amphitheater', p: 'The largest single capital outlay this year, funded partly by a bond approved in March.', juris: 'Tuscaloosa City Council' },
    { badge: '+9% · 3rd hike in 4 yrs', days: -24, h: 'Northport water rates rise again — 9% this time', p: 'Inflation-adjusted, the typical bill is up roughly a third since 2022.', juris: 'Northport Utilities Board' },
    { badge: '$4.2M · 1 bidder', days: -70, h: 'County awards a $4.2M road contract to a single bidder', p: 'No competing bids came in before the deadline, drawing questions from two commissioners.', juris: 'Tuscaloosa County' },
    { badge: '$30M refinance', days: -190, h: 'City refinanced $30M in debt to free up budget room', p: 'A quiet but consequential move that reshaped the next three years of spending capacity.', juris: 'Tuscaloosa City Council' },
  ],
  near: [
    { badge: '0.4 mi from you', days: -3, h: 'Rezoning could put apartments on Mitt Lary Road', p: 'A developer wants to shift 11 acres from residential to mixed-use. First hearing is set.', juris: 'Northport Planning' },
    { badge: 'In your area', days: -20, h: 'New signal approved at McFarland & Watermelon Rd', p: 'Funded after three years of resident petitions over near-misses at the intersection.', juris: 'Northport City Council' },
    { badge: 'Your neighborhood', days: -75, h: 'Sidewalk project funded along your block', p: 'Part of a $600K pedestrian-safety package targeting routes near elementary schools.', juris: 'Northport Public Works' },
    { badge: 'Your corridor', days: -160, h: 'Watermelon Road widening cleared its final design vote', p: 'Construction on the route you drive daily is now slated to begin next year.', juris: 'Northport Public Works' },
  ],
  new: [
    { badge: 'First time proposed', days: -6, h: 'Northport floats a downtown youth night-market pilot', p: 'A council member pitched a monthly vendor market for teens — no precedent in past meetings.', juris: 'Northport City Council' },
    { badge: 'New idea', days: -26, h: 'Tuscaloosa weighs a guaranteed-ride-home program for service workers', p: 'Modeled on a Nashville pilot; staff asked to study cost before a vote.', juris: 'Tuscaloosa City Council' },
    { badge: 'Novel', days: -72, h: 'County pilots a 4-day workweek for permitting staff', p: 'A 90-day trial to test whether faster turnaround offsets shorter office hours.', juris: 'Tuscaloosa County' },
    { badge: 'First ever', days: -220, h: 'City launched its first participatory-budgeting round', p: 'Residents got to directly allocate a slice of the capital budget for the first time.', juris: 'Tuscaloosa City Council' },
  ],
  people: [
    { badge: '61 speakers', days: -3, h: '60+ residents pack the meeting over a dog-park closure', p: 'Public comment ran past 10 p.m.; the council postponed the decision under pressure.', juris: 'Northport City Council' },
    { badge: '44 comments', days: -19, h: 'Parents flood the school rezoning hearing', p: 'Families from two neighborhoods turned out over which school their kids would attend.', juris: 'Tuscaloosa City Schools' },
    { badge: 'Standing room only', days: -64, h: 'Full chamber for the short-term rental debate', p: 'Hosts and neighbors squared off over a proposed cap on Airbnb-style permits.', juris: 'Tuscaloosa City Council' },
    { badge: '200+ attended', days: -240, h: 'Hundreds turn out against a proposed landfill expansion', p: 'The biggest crowd of the year forced the item back to study committee.', juris: 'Tuscaloosa County' },
  ],
  changed: [
    { badge: 'Reverses last month', days: -5, h: 'Council walks back its food-truck ban', p: 'After vendor backlash, the same body reversed itself and reopened downtown permits.', juris: 'Northport City Council' },
    { badge: 'Walked back', days: -21, h: 'County reinstates funding it cut in spring', p: 'A library budget line restored after public outcry over reduced weekend hours.', juris: 'Tuscaloosa County' },
    { badge: 'U-turn', days: -66, h: 'Northport pauses the annexation it approved earlier', p: 'New cost estimates pushed the council to hit pause on extending city limits.', juris: 'Northport City Council' },
    { badge: 'Full reversal', days: -300, h: 'Council reverses its own short-term rental cap a year later', p: 'What passed as a hard limit was quietly undone after a change in membership.', juris: 'Tuscaloosa City Council' },
  ],
  soon: [
    { badge: 'Closes in 3 days', days: 3, h: 'Public comment on the 2027 budget closes Friday', p: 'The draft includes the new trash fee and the amphitheater bond — weigh in before it locks.', juris: 'Tuscaloosa City Council' },
    { badge: 'Votes in 5 days', days: 5, h: 'The downtown parking deck goes to a vote Tuesday', p: 'A $9M structure that’s been debated for two years reaches a final decision.', juris: 'Tuscaloosa City Council' },
    { badge: 'Final reading', days: 8, h: 'Last hearing on the noise ordinance before adoption', p: 'After this meeting the rules take effect — the final window to comment.', juris: 'Northport City Council' },
    { badge: 'Opens soon', days: 24, h: 'Comprehensive plan update opens for public input next month', p: 'The document that shapes a decade of zoning is about to take comments.', juris: 'Northport Planning' },
    { badge: 'Vote this quarter', days: 70, h: 'Rezoning of the old mall site heads to a fall vote', p: 'A major redevelopment decision is scheduled after the summer recess.', juris: 'Tuscaloosa City Council' },
  ],
  slipped: [
    { badge: '0 min debate · $1.8M', days: -4, h: 'A $1.8M software contract passed on the consent agenda', p: 'Bundled with routine items and approved in one vote with no discussion.', juris: 'Tuscaloosa County' },
    { badge: 'Consent item', days: -23, h: 'Council quietly extended the mayor’s emergency powers', p: 'A six-month extension slipped through as part of a packaged resolution.', juris: 'Northport City Council' },
    { badge: 'Passed without comment', days: -71, h: 'Fee-schedule changes buried in a routine vote', p: 'Permit and inspection fees rose across the board with no separate discussion.', juris: 'Tuscaloosa City Council' },
    { badge: 'Consent · 0 min', days: -200, h: 'A 20-year utility easement passed on consent last fall', p: 'A long-term commitment approved without a single question from the dais.', juris: 'Tuscaloosa County' },
  ],
  flags: [
    { badge: 'Address mismatch', days: -8, h: 'A Ward 3 council member’s address on file sits in Ward 5', p: 'Voter-file and parcel records place the registered home outside the ward they represent — worth confirming.', juris: 'Northport City Council' },
    { badge: '7 buys at ~$4,950', days: -15, h: 'Repeated purchases land just under the $5,000 approval limit', p: 'A department logged seven separate buys between $4,900 and $4,990 — each a step below needing board sign-off.', juris: 'Tuscaloosa County' },
    { badge: 'Possible conflict', days: -30, h: 'A contract went to a vendor sharing an address with an official’s relative', p: 'Entity resolution matched the awarded firm to a household tied to a sitting member who didn’t recuse.', juris: 'Tuscaloosa City Council' },
    { badge: '4x peer median', days: -44, h: 'One official’s travel reimbursements run roughly 4x the board average', p: 'Per-diem and travel claims sit far above comparable members over the same period.', juris: 'Northport City Council' },
    { badge: '82% to one firm', days: -80, h: 'Most sole-source contracts this year went to a single vendor', p: 'One firm captured the bulk of no-bid awards — a concentration pattern worth a closer look.', juris: 'Tuscaloosa County' },
    { badge: 'Disclosure 90 days late', days: -180, h: 'A required economic-interest statement is overdue', p: 'The annual conflict-of-interest filing hasn’t been submitted within the statutory window.', juris: 'Tuscaloosa City Council' },
  ],
}

const TIME_OPTIONS: { d: number; label: string }[] = [
  { d: 7, label: 'Week' },
  { d: 31, label: 'Month' },
  { d: 92, label: 'Quarter' },
  { d: 366, label: 'Year' },
  { d: 999999, label: 'All time' },
]
const ALL_TIME = 999999
const WINDOW_LABEL: Record<number, string> = { 7: 'week', 31: 'month', 92: 'quarter', 366: 'year', 999999: 'all time' }

function rel(d: number): string {
  if (d === 0) return 'today'
  const fut = d > 0
  const a = Math.abs(d)
  let t: string
  if (a < 7) {
    t = `${a} ${a === 1 ? 'day' : 'days'}`
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

interface StoryLensesProps {
  /** Short place label for the heading, e.g. "Northport". */
  locationLabel?: string
  /** Invoked when a lens card or the Browse-topics affordance is activated. */
  onSearch?: (query: string) => void
  /** Invoked by the retained "Browse topics" button. */
  onBrowseTopics?: () => void
}

export default function StoryLenses({ locationLabel, onSearch, onBrowseTopics }: StoryLensesProps) {
  const [active, setActive] = useState<string>('contested')
  const [windowDays, setWindowDays] = useState<number>(31)

  const lens = LENSES.find((l) => l.id === active) ?? LENSES[0]
  const allCards = CARDS[active] ?? []
  const rows = useMemo(
    () => allCards.filter((c) => Math.abs(c.days) <= windowDays),
    [allCards, windowDays],
  )
  const forward = active === 'soon'
  const countText = `${rows.length} of ${allCards.length} · ${
    windowDays >= ALL_TIME ? 'all time' : `${forward ? 'next ' : 'past '}${WINDOW_LABEL[windowDays]}`
  }`

  const heading = locationLabel ? `What’s interesting near ${locationLabel}` : "What’s interesting near you"

  return (
    <div className="mt-6 text-left" style={FONT}>
      {/* Header: title + "instead of trending" aside + time control */}
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <h2 className="text-[20px] font-semibold tracking-tight text-[#0f2b2b]" style={SERIF}>
          {heading}
        </h2>
        <span className="hidden items-center gap-1 text-[12.5px] text-[#9bb8b8] sm:inline-flex">
          instead of{' '}
          <s className="text-[#9bb8b8]">
            <ArrowTrendingUpIcon className="mr-0.5 inline h-3.5 w-3.5" aria-hidden />
            Trending topics
          </s>
        </span>

        <div className="ml-auto flex items-center gap-3">
          <span className="hidden whitespace-nowrap text-[12.5px] font-semibold text-[#9bb8b8] sm:inline">
            {countText}
          </span>
          <div className="inline-flex rounded-full border-[1.5px] border-[#d4e8e8] bg-white p-[3px]">
            {TIME_OPTIONS.map((opt) => {
              const on = windowDays === opt.d
              return (
                <button
                  key={opt.d}
                  type="button"
                  onClick={() => setWindowDays(opt.d)}
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
      </div>

      {/* Lens chips + retained Browse topics button */}
      <div className="mb-2 flex flex-wrap items-center gap-2.5">
        {LENSES.map((l) => {
          const on = active === l.id
          return (
            <button
              key={l.id}
              type="button"
              onClick={() => setActive(l.id)}
              className="inline-flex items-center gap-2 rounded-full border-[1.5px] px-3.5 py-2 text-[14px] font-semibold transition-all"
              style={{
                borderColor: on ? l.clr : '#d4e8e8',
                background: on ? l.clr : '#fff',
                color: on ? '#fff' : '#4a6a6a',
                boxShadow: on ? `0 4px 12px ${l.clr}59` : 'none',
              }}
            >
              <span className="text-[15px] leading-none">{l.em}</span>
              {l.label}
            </button>
          )
        })}

        {onBrowseTopics && (
          <button
            type="button"
            onClick={onBrowseTopics}
            className="ml-auto inline-flex shrink-0 items-center gap-1 text-sm font-medium text-[#1a6b6b] underline-offset-2 transition-colors hover:underline"
          >
            Browse topics
            <ChevronDownIcon className="h-4 w-4 -rotate-90" aria-hidden />
          </button>
        )}
      </div>

      {/* Active-lens blurb */}
      <p className="mx-0.5 mb-4 mt-3.5 min-h-[20px] text-[13.5px] leading-relaxed text-[#56635e]">
        {lens.blurb}
      </p>

      {/* Advisory note (Raised Eyebrows lens) */}
      {lens.note && (
        <div className="mx-0.5 mb-4 flex gap-2 rounded-lg border border-[#f0d3d9] border-l-[3px] border-l-[#b0384a] bg-[#fbeef0] px-3.5 py-2.5 text-[12.5px] leading-snug text-[#8a3142]">
          <span>{lens.note}</span>
        </div>
      )}

      {/* Card grid */}
      {rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#d4e8e8] bg-white px-6 py-10 text-center text-sm text-[#9bb8b8]">
          Nothing in this window. <b className="text-[#56635e]">Try a wider time frame.</b>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
          {rows.map((c, i) => (
            <button
              key={`${active}-${i}`}
              type="button"
              onClick={() => onSearch?.(c.juris)}
              className="group relative overflow-hidden rounded-2xl border border-[#e1ebe7] bg-white p-[18px] pb-[15px] text-left shadow-[0_1px_2px_rgba(20,40,35,.04),0_8px_24px_rgba(20,40,35,.06)] transition-transform hover:-translate-y-0.5"
            >
              <span
                className="absolute inset-y-0 left-0 w-1"
                style={{ background: lens.clr }}
                aria-hidden
              />
              <span
                className="mb-3 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-bold tracking-wide"
                style={{ color: lens.clr, background: `color-mix(in srgb, ${lens.clr} 12%, #fff)` }}
              >
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: lens.clr }} aria-hidden />
                {c.badge}
              </span>
              <h3 className="mb-2 text-[19px] font-semibold leading-tight tracking-tight text-[#0f2b2b]" style={SERIF}>
                {c.h}
              </h3>
              <p className="mb-3 text-[13.5px] leading-relaxed text-[#56635e]">{c.p}</p>
              <div className="flex items-center gap-2 border-t border-[#e1ebe7] pt-2.5 text-[12px] text-[#8a958f]">
                <span className="font-semibold text-[#56635e]">{c.juris}</span>
                <span className="opacity-50">·</span>
                <span>{rel(c.days)}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
