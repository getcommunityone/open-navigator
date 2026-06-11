// Home-page sections introduced by the new design prototype, all wired to REAL
// APIs with honest empty states (CLAUDE.md: No Fabricated Data). Three exports:
//
//   <MoneyHook>          "How much of your money is on the line?" — an address
//                        card that opens the interactive guess-and-reveal money
//                        game in a popup modal (<MoneyGameModal>), wired to REAL
//                        government-finance figures (/api/local-finance). With no
//                        location set the "Show me my money" button instead opens
//                        the Find-My-Community address modal so the user picks a
//                        place first (never an empty game).
//   <CityAtAGlance>      "[City] at a glance" — 4 stat cards from /api/money-flow
//                        (tracked spending) and /api/lenses (contested / analyzed
//                        / next-to-watch). Each card shows an empty state when its
//                        real source is null/zero.
//   <TrendingQuestions>  Real policy-question chips (/api/policy-question/).
//
// Palette/fonts follow the repo's existing teal/DM Sans conventions used by the
// hero + StoryLenses (#1a6b6b / #0f2b2b / #6b8a8a), not the prototype's raw hex.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BanknotesIcon,
  ScaleIcon,
  ChartBarIcon,
  CalendarIcon,
  MapPinIcon,
} from '@heroicons/react/24/outline'
import api from '../lib/api'
import { fetchPolicyQuestions } from '../api/policyQuestions'
import MoneyGameModal from './MoneyGameModal'

const FONT = { fontFamily: "'DM Sans', sans-serif" } as const
const SERIF = { fontFamily: "'Fraunces', serif" } as const

// ---------------------------------------------------------------------------
// Shared scope props — the home page only knows state (2-letter) + city + county
// (no jurisdiction_id), so money-and-talk is scoped by state_code and money-flow
// by state+city, exactly mirroring FollowTheMoney / MoneyTalk.
// ---------------------------------------------------------------------------
export interface HomeScopeProps {
  /** 2-letter state code, or undefined for the national view. */
  stateCode?: string
  /** City name (money-flow + local-finance scope). */
  city?: string
  /** County name (local-finance scope). */
  county?: string
  /** Short, human place label for headings, e.g. "Northport" or "Alabama". */
  locationLabel?: string
  /** When true, show the national view (no state/city filter). */
  national?: boolean
}

// ---- /api/money-flow response (subset we read) ----
interface FlowLensLite {
  head_amount: string
  head_label: string
  count_label: string
  placeholder: boolean
}
interface MoneyFlowLite {
  location_label?: string
  lenses: { spending: FlowLensLite; grants: FlowLensLite; economy: FlowLensLite }
}

function useMoneyFlow({ stateCode, city, national }: HomeScopeProps) {
  const scopedState = national ? undefined : stateCode
  const scopedCity = national ? undefined : city
  return useQuery<MoneyFlowLite>({
    queryKey: ['home-money-flow', national, scopedState, scopedCity],
    queryFn: () =>
      api
        .get('/money-flow', { params: { state: scopedState, city: scopedCity } })
        .then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  })
}

// ---- /api/lenses response (subset we read for the snapshot) ----
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
interface LensesLite {
  lenses: LensBlock[]
  activity: LensActivity[]
  location_label?: string
}

function useLenses({ stateCode, city, national }: HomeScopeProps) {
  return useQuery<LensesLite>({
    queryKey: ['home-lenses-snapshot', national, stateCode, city],
    queryFn: () => {
      const params: Record<string, string> = { window: 'auto' }
      if (!national && stateCode) params.state = stateCode
      if (!national && city) params.city = city
      return api.get('/lenses', { params }).then((r) => r.data)
    },
    staleTime: 5 * 60 * 1000,
  })
}

// ===========================================================================
// "[City] at a glance" — 4 snapshot stat cards, each honest about missing data.
// ===========================================================================
interface SnapshotCard {
  key: string
  Icon: typeof BanknotesIcon
  label: string
  value: string | null
  sub?: string
}

function StatCard({ card }: { card: SnapshotCard }) {
  const available = card.value != null
  return (
    <div
      className={`flex flex-col rounded-2xl border p-5 transition-all ${
        available
          ? 'border-[#d4e8e8] bg-white shadow-[0_4px_20px_rgba(26,107,107,0.06)]'
          : 'border-dashed border-[#d4e8e8] bg-[#f7fafb]'
      }`}
    >
      <span
        className={`mb-3 flex h-9 w-9 items-center justify-center rounded-full ${
          available ? 'bg-[#e8f4f4] text-[#1a6b6b]' : 'bg-white text-[#9bb8b8]'
        }`}
      >
        <card.Icon className="h-5 w-5" aria-hidden />
      </span>
      {available ? (
        <span
          className="text-[26px] font-semibold leading-none text-[#0f2b2b] tabular-nums"
          style={SERIF}
        >
          {card.value}
        </span>
      ) : (
        <span className="text-base font-medium text-[#9bb8b8]" style={FONT}>
          —
        </span>
      )}
      <span className="mt-2 text-[13px] font-medium text-[#56635e]" style={FONT}>
        {card.label}
      </span>
      <span className="mt-0.5 text-[12px] text-[#9bb8b8]" style={FONT}>
        {available ? card.sub : 'No data available'}
      </span>
    </div>
  )
}

export function CityAtAGlance(props: HomeScopeProps) {
  const { locationLabel, national } = props
  const { data: flow } = useMoneyFlow(props)
  const { data: lenses } = useLenses(props)

  // Tracked spending — money-flow spending lens head amount (already formatted).
  const spending = flow?.lenses?.spending
  const spendValue =
    spending && !spending.placeholder && spending.head_amount ? spending.head_amount : null

  // Contested + analyzed — match by activity-tile label.
  const activity = lenses?.activity ?? []
  const findActivity = (test: (l: string) => boolean): LensActivity | undefined =>
    activity.find((a) => test(a.label.toLowerCase()))
  const contested = findActivity((l) => l.includes('contest'))
  const analyzed = findActivity((l) => l.includes('decision') || l.includes('analyz'))

  // Next vote to watch — first card of the "Watch Next" lens (the closest real
  // proxy; there is no upcoming-events endpoint, so we never fabricate a date).
  const nextLens = lenses?.lenses?.find((l) => l.id === 'next')
  const nextCard = nextLens && !nextLens.placeholder ? nextLens.cards?.[0] : undefined

  const cards: SnapshotCard[] = [
    {
      key: 'spending',
      Icon: BanknotesIcon,
      label: 'Tracked spending',
      value: spendValue,
      sub: spending?.count_label || 'in money-flagged decisions',
    },
    {
      key: 'contested',
      Icon: ScaleIcon,
      label: 'Contested decisions',
      value: contested ? contested.value : null,
      sub: 'split votes & debate',
    },
    {
      key: 'analyzed',
      Icon: ChartBarIcon,
      label: 'Decisions analyzed',
      value: analyzed ? analyzed.value : null,
      sub: 'in this window',
    },
    {
      key: 'next',
      Icon: CalendarIcon,
      label: 'On the radar',
      value: nextCard ? nextCard.jurisdiction || 'Coming back' : null,
      sub: nextCard ? nextCard.headline : 'No upcoming votes flagged',
    },
  ]

  const place = national ? 'The U.S.' : locationLabel || 'Your community'

  return (
    <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 md:py-10">
      <div className="mb-5 flex items-center gap-2">
        <MapPinIcon className="h-5 w-5 text-[#1a6b6b]" aria-hidden />
        <h2
          className="text-2xl md:text-[28px] font-semibold text-[#0f2b2b]"
          style={SERIF}
        >
          {place} at a glance
        </h2>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
        {cards.map((c) => (
          <StatCard key={c.key} card={c} />
        ))}
      </div>
    </section>
  )
}

// ===========================================================================
// Trending questions — real policy-question chips.
// ===========================================================================
export function TrendingQuestions({ onOpen }: { onOpen: (questionId: string) => void }) {
  const { data } = useQuery({
    queryKey: ['home-trending-questions'],
    queryFn: () => fetchPolicyQuestions({ limit: 12 }),
    staleTime: 30 * 60 * 1000,
  })

  const chips = (data ?? []).filter((q) => !!q.canonical_text)
  if (chips.length === 0) return null // never show fabricated questions

  return (
    <div className="mt-4 flex flex-nowrap items-center gap-2 overflow-x-auto px-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <span className="shrink-0 whitespace-nowrap text-[13px] font-medium text-[#9bb8b8]" style={FONT}>
        Trending questions:
      </span>
      {chips.map((q) => (
        <button
          key={q.question_id}
          type="button"
          onClick={() => onOpen(q.question_id)}
          className="shrink-0 whitespace-nowrap rounded-full border border-[#d4e8e8] bg-white px-3.5 py-1.5 text-[13px] font-medium text-[#1a6b6b] transition-colors hover:border-[#1a6b6b] hover:bg-[#f0f8f8]"
          style={FONT}
        >
          {q.canonical_text}
        </button>
      ))}
    </div>
  )
}

// ===========================================================================
// "How much of your money is on the line?" — address card that launches the
// interactive money game in a popup modal (<MoneyGameModal>), scoped to the
// user's location and wired to REAL /api/local-finance figures.
// ===========================================================================
export function MoneyHook({
  stateCode,
  city,
  county,
  national,
  locationLabel,
  onSetLocation,
}: HomeScopeProps & { onSetLocation: () => void }) {
  // Local-only address text; passing it onward is optional — the real
  // "Find My Community" AddressLookup modal (opened via onSetLocation) does the
  // geocoding. We never fabricate a result from this string.
  const [address, setAddress] = useState('')
  const [modalOpen, setModalOpen] = useState(false)

  // The game needs a real state to scope /api/local-finance. The national view
  // has no single state, so there it always falls back to the address modal.
  const canPlay = !national && !!stateCode

  const handleSubmit = () => {
    // No location/state yet → let the user pick a place first (don't open an
    // empty game). Otherwise open the real money game modal.
    if (canPlay) {
      setModalOpen(true)
    } else {
      onSetLocation()
    }
  }

  return (
    <section className="bg-gradient-to-b from-stone-50 via-white to-white">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10 md:py-14">
        {/* Centered headline + subtitle */}
        <div className="mx-auto max-w-2xl text-center">
          <h2
            className="text-3xl md:text-[42px] font-semibold leading-[1.1] tracking-tight text-[#0f2b2b]"
            style={SERIF}
          >
            How much of <span className="text-[#1a6b6b]">your money</span> is on the line?
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-[15px] md:text-[17px] leading-relaxed text-[#6b8a8a]" style={FONT}>
            Enter your address and discover how local decisions affect your wallet — and your
            grandkids&apos; future.
          </p>
        </div>

        {/* Centered white address card (reuses the real location flow) */}
        <div className="mx-auto mt-7 w-full max-w-[640px] rounded-2xl border border-[#e2eaea] bg-white p-5 md:p-6 shadow-[0_8px_30px_rgba(26,107,107,0.08)]">
          <label
            htmlFor="moneyhook-address"
            className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.14em] text-[#9bb8b8]"
            style={{ fontFamily: "'DM Mono', ui-monospace, monospace" }}
          >
            Address or ZIP
          </label>
          <div className="flex flex-col gap-2.5 sm:flex-row">
            <div className="relative flex-1">
              <MapPinIcon className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-[#9bb8b8]" aria-hidden />
              <input
                id="moneyhook-address"
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    handleSubmit()
                  }
                }}
                placeholder="Try 123 Main St, Tuscaloosa"
                className="w-full rounded-xl border border-[#d4e8e8] bg-white py-3 pl-10 pr-3 text-[15px] text-[#0f2b2b] placeholder-[#9bb8b8] outline-none transition-colors focus:border-[#1a6b6b] focus:ring-2 focus:ring-[#1a6b6b]/20"
                style={FONT}
              />
            </div>
            <button
              type="button"
              onClick={handleSubmit}
              className="shrink-0 rounded-xl bg-[#1a6b6b] px-5 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-[#155757]"
              style={FONT}
            >
              Show me my money
            </button>
          </div>
          <div className="mt-3 flex flex-col gap-1 text-[12px] sm:flex-row sm:items-center sm:justify-between">
            <span
              className="font-medium uppercase tracking-[0.1em] text-[#9bb8b8]"
              style={{ fontFamily: "'DM Mono', ui-monospace, monospace" }}
            >
              Takes 15 seconds · No data stored
            </span>
            <span className="text-[#9bb8b8]" style={FONT}>
              {canPlay
                ? 'See your real local tax split.'
                : 'Set your community to see your real local tax split.'}
            </span>
          </div>
        </div>
      </div>

      {/* The interactive money game — real /api/local-finance figures, scoped to
          the user's location. Only mounted/opened once a real state is known. */}
      {canPlay && stateCode && (
        <MoneyGameModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          stateCode={stateCode}
          city={city}
          county={county}
          requestedLabel={locationLabel}
        />
      )}
    </section>
  )
}
