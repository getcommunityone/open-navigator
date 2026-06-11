// "Your {jurisdiction} impact" — the interactive guess-and-reveal money game,
// opened as a popup modal from the home page money hook. EVERY figure is REAL,
// from GET /api/local-finance (Census state & local government finances); nulls
// render as "—"/omitted and are NEVER shown as 0 (CLAUDE.md: No Fabricated Data).
//
// The right column's "Grandkids forecast" panel is wired to REAL Opportunity
// Atlas mobility data (GET /api/grandkid-outlook, Chetty et al.). It compares the
// local commuting zone's child-income percentile to the national one for a chosen
// parent-income bracket — NOT the prototype's fabricated 1978-vs-1992 cohort
// slopegraph. When no commuting zone matched the city, or the matched cell has too
// little data, we show ONLY the national value plus the API's honest `note`; we
// never invent a local number.
//
// Honest gaps vs. the design prototype:
//   - When the requested city/county isn't found the API returns statewide
//     figures (matched===false); we surface that with an explicit note.
import { Fragment, useEffect, useMemo, useState } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { useQuery } from '@tanstack/react-query'
import { XMarkIcon } from '@heroicons/react/24/outline'
import {
  fetchLocalFinance,
  fetchPropertyTaxRate,
  fetchSalesTaxRate,
  type LocalFinance,
  type LocalFinanceCategory,
  type PropertyTaxRate,
  type SalesTaxRate,
} from '../api/localFinance'
import {
  fetchGrandkidOutlook,
  type GrandkidOutlook as GrandkidOutlookData,
} from '../api/grandkidOutlook'

// Match the design prototype's typography (loaded globally by HomeV9): Playfair
// Display for headlines, Source Sans for body, IBM Plex Mono for mono labels.
const FONT = { fontFamily: "'Source Sans 3', system-ui, sans-serif" } as const
const SERIF = { fontFamily: "'Playfair Display', Georgia, serif" } as const
const MONO = { fontFamily: "'IBM Plex Mono', ui-monospace, monospace" } as const

// Teal-forward palette for the spending categories (repo convention, not the
// prototype's raw hex).
const CAT_PALETTE = [
  '#1a6b6b',
  '#2a8576',
  '#e0723a',
  '#7a5cd0',
  '#2f6fb0',
  '#9a6b12',
  '#1d6b5f',
  '#c0432a',
]

// Whole-dollar currency, no decimals: 1495.81 -> "$1,496", 150505000 -> "$150,505,000".
function fmtDollars(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  return `$${Math.round(n).toLocaleString('en-US')}`
}

function pct(n: number): string {
  return `${Math.round(n)}%`
}

export interface MoneyGameModalProps {
  open: boolean
  onClose: () => void
  /** 2-letter state code — required to fetch (modal only opens with one). */
  stateCode: string
  city?: string
  county?: string
  /** Requested city/county label, for the city→state fallback note. */
  requestedLabel?: string
}

// ---------------------------------------------------------------------------
// Build the SAME set of categories the user guesses against and we reveal, with
// shares RENORMALIZED to sum to 100% across exactly that shown set (fair
// scoring). Only categories with a non-null share_pct are eligible. Top 6 are
// kept individually; any remainder is bucketed into a single "Other" row so the
// guessed set === the revealed set.
// ---------------------------------------------------------------------------
interface CategoryPart {
  /** real mart label, e.g. "Utilities" / "Other & Debt". */
  label: string
  /** share of the whole budget, percent (renormalized across the shown set). */
  share: number
}

interface GameCategory {
  category: string
  /** real renormalized share across the shown set, percent. */
  actual: number
  /** Present only on the "Other" bucket: its real constituents, for the
   *  drill-down. Display-only — never guessed, so it has no slider. */
  breakdown?: CategoryPart[]
}

// The named guess sliders, in the design prototype's order. We always show these
// (when present in the data) and fold every OTHER real category — Utilities,
// Health & Welfare, Other & Debt, etc. — into a single "Other" slider whose real
// constituents stay visible via an expandable drill-down (so nothing real is
// hidden). `match` is the verbose census label in the mart; `label` is the short
// prototype label we render.
const NAMED_CATEGORIES: { match: string; label: string }[] = [
  { match: 'Education', label: 'Education' },
  { match: 'Public Safety', label: 'Public Safety' },
  { match: 'Infrastructure & Highways', label: 'Infrastructure' },
  { match: 'Parks & Recreation', label: 'Parks & Rec' },
  { match: 'Administration & Government', label: 'Administration' },
]

function buildGameCategories(categories: LocalFinanceCategory[]): GameCategory[] {
  const eligible = categories.filter((c) => c.share_pct != null && (c.share_pct as number) > 0)
  if (eligible.length === 0) return []

  // Pull the named service categories out in prototype order; everything left
  // over becomes the single "Other" bucket.
  const named: { label: string; share: number }[] = []
  const usedRaw = new Set<string>()
  for (const { match, label } of NAMED_CATEGORIES) {
    const hit = eligible.find((c) => c.category === match)
    if (hit) {
      named.push({ label, share: hit.share_pct as number })
      usedRaw.add(match)
    }
  }
  const rest = eligible.filter((c) => !usedRaw.has(c.category))

  const total =
    named.reduce((s, n) => s + n.share, 0) +
    rest.reduce((s, c) => s + (c.share_pct as number), 0)
  if (total <= 0) return []

  // Renormalize so the shown shares sum to exactly 100.
  const result: GameCategory[] = named.map((n) => ({
    category: n.label,
    actual: (n.share / total) * 100,
  }))

  if (rest.length > 0) {
    const otherShare = rest.reduce((s, c) => s + (c.share_pct as number), 0)
    const breakdown: CategoryPart[] = rest
      .map((c) => ({ label: c.category, share: ((c.share_pct as number) / total) * 100 }))
      .sort((a, b) => b.share - a.share)
    result.push({ category: 'Other', actual: (otherShare / total) * 100, breakdown })
  }

  return result
}

// Shared range-slider classes — the prototype's look: an 8px inset track with a
// colored fill, and an 18px HOLLOW thumb (white center, 3px ring in the
// category color via --thumb).
const SLIDER_CLS = [
  'h-2 w-full cursor-pointer appearance-none rounded-full shadow-[inset_0_0_0_1px_rgba(28,25,23,0.08)]',
  '[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-[18px] [&::-webkit-slider-thumb]:w-[18px]',
  '[&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-[3px] [&::-webkit-slider-thumb]:[border-color:var(--thumb)] [&::-webkit-slider-thumb]:bg-white',
  '[&::-webkit-slider-thumb]:shadow-[0_1px_3px_rgba(28,25,23,0.25)]',
  '[&::-moz-range-thumb]:h-[15px] [&::-moz-range-thumb]:w-[15px] [&::-moz-range-thumb]:rounded-full',
  '[&::-moz-range-thumb]:border-[3px] [&::-moz-range-thumb]:[border-color:var(--thumb)] [&::-moz-range-thumb]:bg-white',
].join(' ')

// One labelled estimate slider. `log` gives an exponential track (fine control
// in the everyday range) so a $230K home isn't pinned to the far left of a $2M
// slider — same trick as the design prototype.
function EstRow({
  label,
  value,
  min,
  max,
  step,
  onChange,
  display,
  log,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  onChange: (v: number) => void
  display: string
  log?: boolean
}) {
  const toT = (v: number) => Math.round(1000 * (Math.log(v / min) / Math.log(max / min)))
  const fromT = (t: number) => {
    const raw = min * Math.pow(max / min, t / 1000)
    return Math.min(max, Math.max(min, Math.round(raw / step) * step))
  }
  const filled = log ? toT(value) / 10 : ((value - min) / (max - min)) * 100
  return (
    <div className="mb-3">
      <div className="mb-1 flex items-baseline justify-between gap-2 text-[13px]" style={FONT}>
        <span className="min-w-0 truncate font-medium text-[#0f2b2b]">{label}</span>
        <span className="shrink-0 font-semibold tabular-nums text-[#1a6b6b]">{display}</span>
      </div>
      <input
        type="range"
        min={log ? 0 : min}
        max={log ? 1000 : max}
        step={log ? 1 : step}
        value={log ? toT(value) : value}
        onChange={(e) => onChange(log ? fromT(Number(e.target.value)) : Number(e.target.value))}
        style={
          {
            background: `linear-gradient(to right, #1a6b6b ${filled}%, #eef4f4 ${filled}%)`,
            '--thumb': '#1a6b6b',
          } as React.CSSProperties
        }
        className={SLIDER_CLS}
        aria-label={label}
      />
    </div>
  )
}

// Small conic-gradient donut for the bill split.
function BillDonut({ parts }: { parts: { value: number; color: string }[] }) {
  const usable = parts.filter((p) => p.value > 0)
  const total = usable.reduce((s, p) => s + p.value, 0)
  if (total <= 0) return null
  let acc = 0
  const stops = usable
    .map((p) => {
      const start = (acc / total) * 100
      acc += p.value
      return `${p.color} ${start}% ${(acc / total) * 100}%`
    })
    .join(', ')
  return (
    <div className="relative h-[84px] w-[84px] shrink-0 rounded-full" style={{ background: `conic-gradient(${stops})` }} aria-hidden>
      <div className="absolute inset-[24%] rounded-full bg-[#fafaf9]" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// STAGE 1: "Your bill" — a personal estimate that mirrors the design prototype,
// every rate REAL: property tax = your home value × the local effective ACS
// rate (/property-tax-rate); sales tax = your taxable spending × the real
// combined state+local rate (/sales-tax-rate, Tax Foundation); fees are your
// own input. Renters: property tax is embedded in rent and remitted by the
// landlord, so we don't fabricate a pass-through — we say so and base the
// visible bill on sales + fees.
// ---------------------------------------------------------------------------
function YourBill({
  open,
  stateCode,
  city,
  county,
  jurisdictionName,
  onContinue,
}: {
  open: boolean
  stateCode: string
  city?: string
  county?: string
  jurisdictionName: string
  onContinue: () => void
}) {
  const propQ = useQuery<PropertyTaxRate>({
    queryKey: ['property-tax-rate', stateCode, city, county],
    queryFn: () => fetchPropertyTaxRate({ state: stateCode, city, county }),
    enabled: open && !!stateCode,
    staleTime: 10 * 60 * 1000,
    retry: false,
  })
  const salesQ = useQuery<SalesTaxRate>({
    queryKey: ['sales-tax-rate', stateCode],
    queryFn: () => fetchSalesTaxRate(stateCode),
    enabled: open && !!stateCode,
    staleTime: 10 * 60 * 1000,
    retry: false,
  })

  const propRate = propQ.data?.effective_property_tax_rate ?? null
  const median = propQ.data?.median_home_value ?? null
  const salesPct = salesQ.data?.combined_sales_tax_rate_pct ?? null
  const salesFrac = salesPct != null ? salesPct / 100 : null

  const [own, setOwn] = useState(true)
  const [homeValue, setHomeValue] = useState<number | null>(null)
  const [spend, setSpend] = useState(19_000)
  const [fees, setFees] = useState(800)
  const [income, setIncome] = useState(60_000)
  useEffect(() => {
    if (median != null) setHomeValue((v) => (v == null ? median : v))
  }, [median])

  const hv = homeValue ?? median ?? 230_000
  const homeMax = Math.max(1_000_000, Math.ceil(((median ?? 230_000) * 2.5) / 50_000) * 50_000)
  const propTax = own && propRate != null ? hv * propRate : null
  const salesTax = salesFrac != null ? spend * salesFrac : null

  const parts: { label: string; value: number; color: string }[] = []
  if (propTax != null) parts.push({ label: 'Property tax', value: propTax, color: '#1a6b6b' })
  if (salesTax != null) parts.push({ label: 'Sales tax', value: salesTax, color: '#2a8576' })
  parts.push({ label: 'Fees & other', value: fees, color: '#7fd0c4' })
  const total = parts.reduce((s, p) => s + p.value, 0)
  const sharePct = income > 0 ? (total / income) * 100 : null

  return (
    <div>
      <div className="flex flex-col gap-5 md:flex-row md:items-start">
        {/* Inputs */}
        <div className="flex-1">
          <div className="mb-4 inline-flex rounded-xl border border-[#d4e8e8] bg-[#f7fafb] p-0.5">
            {[
              { v: true, label: 'I own' },
              { v: false, label: 'I rent' },
            ].map((o) => (
              <button
                key={o.label}
                type="button"
                onClick={() => setOwn(o.v)}
                className={`rounded-lg px-4 py-1.5 text-[13px] font-semibold transition-colors ${
                  own === o.v ? 'bg-[#1a6b6b] text-white' : 'text-[#56635e] hover:text-[#0f2b2b]'
                }`}
                style={FONT}
              >
                {o.label}
              </button>
            ))}
          </div>

          {own ? (
            <EstRow label="Home value" value={hv} min={50_000} max={homeMax} step={5_000} onChange={setHomeValue} display={fmtDollars(hv)} log />
          ) : (
            <p className="mb-3 rounded-lg bg-[#f7fafb] px-3 py-2 text-[12px] leading-relaxed text-[#6b8a8a]" style={FONT}>
              Renters pay property tax through rent — your landlord remits it. We don&apos;t fabricate
              that split, so your visible bill below is local sales tax + fees.
            </p>
          )}
          <EstRow label="Yearly spending on taxable goods" value={spend} min={4_000} max={100_000} step={500} onChange={setSpend} display={fmtDollars(spend)} log />
          <EstRow label="Local fees (utilities, permits, garbage)" value={fees} min={0} max={2_500} step={50} onChange={setFees} display={fmtDollars(fees)} />
          <EstRow label="Household income" value={income} min={15_000} max={250_000} step={1_000} onChange={setIncome} display={fmtDollars(income)} log />
        </div>

        {/* Live result */}
        <div className="flex-1 rounded-2xl border border-[#d4e8e8] bg-[#fafaf9] p-4 md:p-5">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#9bb8b8]" style={MONO}>
                You pay approximately
              </p>
              <p className="text-[36px] font-semibold leading-none text-[#0f2b2b]" style={SERIF}>
                {fmtDollars(total)}
              </p>
              <p className="mt-1 text-[13px] text-[#56635e]" style={FONT}>
                per year · {fmtDollars(total / 12)}/mo
              </p>
            </div>
            <BillDonut parts={parts} />
          </div>

          {sharePct != null && (
            <p className="mt-3 text-[13.5px] font-semibold text-[#0f2b2b]" style={FONT}>
              That&apos;s {sharePct.toFixed(1)}% of your household income going to local government.
            </p>
          )}

          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
            {parts.map((p) => (
              <span key={p.label} className="flex items-center gap-1.5 text-[11.5px] text-[#56635e]" style={FONT}>
                <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: p.color }} />
                {p.label} · {fmtDollars(p.value)}
              </span>
            ))}
          </div>

          <p className="mt-3 text-[11px] leading-relaxed text-[#9bb8b8]" style={FONT}>
            {propRate != null && (
              <>Property: {jurisdictionName}&apos;s {(propRate * 100).toFixed(2)}% effective ACS rate. </>
            )}
            {salesPct != null && <>Sales: {salesPct.toFixed(2)}% combined state+local rate. </>}
            Fees are your own estimate.
          </p>
        </div>
      </div>

      <button
        type="button"
        onClick={onContinue}
        className="mt-5 w-full rounded-xl bg-[#1a6b6b] px-5 py-3.5 text-[15px] font-semibold text-white transition-colors hover:bg-[#155757]"
        style={FONT}
      >
        Now — can you guess where it goes? →
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// The live "your guess" donut: a "?" placeholder until the user touches a
// slider, then a conic split of the guessed categories with a faint remainder
// slice standing in for the not-yet-guessed ones.
// ---------------------------------------------------------------------------
function GuessDonut({
  game,
  guesses,
  touched,
}: {
  game: GameCategory[]
  guesses: number[]
  touched: boolean[]
}) {
  const anyTouched = touched.some(Boolean)
  if (!anyTouched) {
    return (
      <div
        className="flex h-24 w-24 shrink-0 animate-pulse items-center justify-center rounded-full border-[3px] border-dashed border-[#cfe0e0]"
        aria-hidden
      >
        <span className="text-[30px] font-semibold text-[#cfe0e0]" style={SERIF}>
          ?
        </span>
      </div>
    )
  }

  const touchedCount = touched.filter(Boolean).length
  const sum = guesses.reduce((s, g) => s + g, 0)
  const parts = game.map((_, i) => ({
    value: touched[i] ? guesses[i] : 0,
    color: CAT_PALETTE[i % CAT_PALETTE.length],
  }))
  // Faint slice for the categories still left to guess, so the ring grows as
  // the user works through them.
  const remainder =
    touchedCount < game.length
      ? Math.max((sum * (game.length - touchedCount)) / Math.max(touchedCount, 1), 8)
      : 0
  const allParts = remainder > 0 ? [...parts, { value: remainder, color: '#eef4f4' }] : parts
  const total = allParts.reduce((s, p) => s + p.value, 0) || 1

  let acc = 0
  const stops = allParts
    .map((p) => {
      const start = (acc / total) * 100
      acc += p.value
      const end = (acc / total) * 100
      return `${p.color} ${start}% ${end}%`
    })
    .join(', ')

  return (
    <div
      className="relative h-24 w-24 shrink-0 rounded-full"
      style={{ background: `conic-gradient(${stops})` }}
      aria-hidden
    >
      <div className="absolute inset-[30%] flex items-center justify-center rounded-full bg-white text-center">
        <span
          className="text-[9px] font-semibold uppercase leading-tight tracking-[0.08em] text-[#9bb8b8]"
          style={MONO}
        >
          Your
          <br />
          guess
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// LEFT: the guessing game. Sliders start empty; the user must drag every
// category before revealing, then each row shows the real share and how far
// off they were. Categories & shares are REAL (Census), never fabricated.
// ---------------------------------------------------------------------------
function GuessingGame({
  fin,
  game,
  revealed,
  onReveal,
  guesses,
  setGuesses,
  touched,
  setTouched,
  scoreInfo,
}: {
  fin: LocalFinance
  game: GameCategory[]
  revealed: boolean
  onReveal: () => void
  guesses: number[]
  setGuesses: (g: number[]) => void
  touched: boolean[]
  setTouched: (t: boolean[]) => void
  scoreInfo: { score: number; totalError: number } | null
}) {
  const [hintDismissed, setHintDismissed] = useState(false)
  // The "Other" slider can be expanded to reveal its real constituents (read-only).
  const [otherExpanded, setOtherExpanded] = useState(false)

  // Normalize the guesses to sum to 100 for display/scoring (auto-balance).
  const guessTotal = guesses.reduce((s, g) => s + g, 0)
  const normGuess = (i: number): number =>
    guessTotal > 0 ? (guesses[i] / guessTotal) * 100 : 0

  const setOne = (i: number, v: number) => {
    const next = [...guesses]
    next[i] = v
    setGuesses(next)
    if (!touched[i]) {
      const t = [...touched]
      t[i] = true
      setTouched(t)
    }
  }

  const touchedCount = touched.filter(Boolean).length
  const allGuessed = touchedCount === game.length && guesses.some((v) => v > 0)
  const firstUntouched = game.findIndex((_, i) => !touched[i])

  // Real top category after reveal.
  const top = useMemo(() => {
    if (game.length === 0) return null
    return [...game].sort((a, b) => b.actual - a.actual)[0]
  }, [game])

  const topDollars =
    top && fin.taxes_per_capita != null ? fin.taxes_per_capita * (top.actual / 100) : null

  return (
    <div className="rounded-2xl border border-[#d4e8e8] bg-white p-5 shadow-[0_4px_20px_rgba(26,107,107,0.06)]">
      <h3 className="text-[15px] font-semibold text-[#0f2b2b]" style={SERIF}>
        The guessing game
      </h3>
      <p className="mt-1 text-[12px] leading-relaxed text-[#6b8a8a]" style={FONT}>
        Drag each slider to guess how {fin.jurisdiction_name} splits its spending, then reveal the
        real numbers.
      </p>

      {/* Dismissible scoring explainer. */}
      {!hintDismissed ? (
        <div className="mt-3 flex items-start gap-2 rounded-xl border border-[#cdece7] bg-[#f0faf8] px-3 py-2.5">
          <p className="flex-1 text-[12px] leading-relaxed text-[#2a5a52]" style={FONT}>
            <span className="font-semibold">How scoring works:</span> drag all {game.length} to your gut
            feeling — percentages auto-balance to 100%, so just get the proportions right. On reveal, your
            score is 100 minus a point for every two percentage points you&apos;re off versus the real
            adopted budget.
          </p>
          <button
            type="button"
            onClick={() => setHintDismissed(true)}
            aria-label="Dismiss"
            className="-mr-1 shrink-0 rounded text-[14px] leading-none text-[#1a6b6b] transition-colors hover:text-[#0f2b2b]"
          >
            ✕
          </button>
        </div>
      ) : (
        <p className="mt-3 text-[12px] leading-relaxed text-[#9bb8b8]" style={FONT}>
          Slide your gut feeling, then reveal to score against the real budget.
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-start gap-4">
        <GuessDonut game={game} guesses={guesses} touched={touched} />

        <div className="min-w-[180px] flex-1 space-y-3.5">
          {game.map((c, i) => {
            const g = normGuess(i)
            const delta = revealed ? Math.round(g - c.actual) : 0
            const color = CAT_PALETTE[i % CAT_PALETTE.length]
            // Filled portion tracks the raw slider value (0 until first drag).
            const fill = touched[i] ? Math.round(guesses[i]) : 0
            return (
              <div key={c.category}>
                <div className="mb-1 flex items-center justify-between text-[13px]" style={FONT}>
                  <span className="flex items-center gap-1.5 font-medium text-[#0f2b2b]">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: CAT_PALETTE[i % CAT_PALETTE.length] }}
                    />
                    {c.category}
                    {!revealed && i === firstUntouched && (
                      <span className="animate-pulse text-[11px] font-semibold text-[#1a6b6b]">
                        drag to guess →
                      </span>
                    )}
                  </span>
                  <span className="flex items-center gap-2 tabular-nums">
                    {touched[i] ? (
                      <span className="font-semibold text-[#1a6b6b]">{pct(g)}</span>
                    ) : (
                      <span className="font-semibold text-[#cfe0e0]">?</span>
                    )}
                    {revealed && <span className="text-[#9bb8b8]">actual {pct(c.actual)}</span>}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={1}
                  value={Math.round(guesses[i])}
                  disabled={revealed}
                  onChange={(e) => setOne(i, Number(e.target.value))}
                  style={
                    {
                      // Colored filled track up to the thumb, then light gray;
                      // `--thumb` colors the knob (used by the pseudo-elements).
                      background: `linear-gradient(to right, ${color} ${fill}%, #eef4f4 ${fill}%)`,
                      '--thumb': color,
                    } as React.CSSProperties
                  }
                  className={`${SLIDER_CLS} disabled:cursor-default`}
                  aria-label={`Your guess for ${c.category}`}
                />
                {revealed && (
                  <>
                    <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[#eef4f4]">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.min(100, c.actual)}%`,
                          backgroundColor: CAT_PALETTE[i % CAT_PALETTE.length],
                        }}
                      />
                    </div>
                    <p
                      className="mt-1 text-[11px]"
                      style={{ ...FONT, color: Math.abs(delta) >= 8 ? '#9a6b12' : '#9bb8b8' }}
                    >
                      {Math.abs(delta) <= 3
                        ? '✓ close'
                        : delta > 0
                          ? `you guessed ${Math.abs(delta)} high`
                          : `you guessed ${Math.abs(delta)} low`}
                    </p>
                  </>
                )}
                {/* Read-only drill-down for the "Other" bucket: shows the real
                    categories folded into it. Percentages only after reveal so
                    expanding early doesn't leak the "Other" answer. */}
                {c.breakdown && c.breakdown.length > 0 && (
                  <div className="mt-2">
                    <button
                      type="button"
                      onClick={() => setOtherExpanded((v) => !v)}
                      aria-expanded={otherExpanded}
                      className="flex items-center gap-1 text-[11px] font-medium text-[#1a6b6b] transition-colors hover:text-[#0f2b2b]"
                      style={FONT}
                    >
                      <span
                        className="inline-block transition-transform"
                        style={{ transform: otherExpanded ? 'rotate(90deg)' : 'none' }}
                        aria-hidden
                      >
                        ▸
                      </span>
                      {otherExpanded ? 'Hide what’s inside' : 'What’s in “Other”?'}
                    </button>
                    {otherExpanded && (
                      <ul className="mt-1.5 space-y-1 rounded-lg border border-[#eef4f4] bg-[#f7fafb] px-3 py-2">
                        {c.breakdown.map((part) => (
                          <li
                            key={part.label}
                            className="flex items-center justify-between text-[11px]"
                            style={FONT}
                          >
                            <span className="text-[#56635e]">{part.label}</span>
                            {revealed ? (
                              <span className="font-semibold tabular-nums text-[#1a6b6b]">
                                {part.share.toFixed(1)}%
                              </span>
                            ) : (
                              <span className="text-[#9bb8b8]">included</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {!revealed ? (
        <button
          type="button"
          onClick={() => allGuessed && onReveal()}
          disabled={!allGuessed}
          className={`mt-5 w-full rounded-xl px-5 py-3 text-[15px] font-semibold transition-colors ${
            allGuessed
              ? 'bg-[#1a6b6b] text-white hover:bg-[#155757]'
              : 'cursor-default bg-[#eef4f4] text-[#9bb8b8]'
          }`}
          style={FONT}
        >
          {allGuessed
            ? 'Reveal reality'
            : `Guess all ${game.length} to reveal · ${game.length - touchedCount} to go`}
        </button>
      ) : (
        <div className="mt-5 space-y-2">
          {top && (
            <p className="text-[14px] leading-relaxed text-[#0f2b2b]" style={FONT}>
              <span className="font-semibold text-[#1a6b6b]">{pct(top.actual)}</span> of your money
              goes to <span className="font-semibold">{top.category}</span>
              {topDollars != null ? (
                <> — about {fmtDollars(topDollars)} per resident, per year.</>
              ) : (
                <>.</>
              )}
            </p>
          )}
          {scoreInfo != null && (
            <p className="text-[13px] text-[#6b8a8a]" style={FONT}>
              Your guess accuracy:{' '}
              <span className="font-semibold text-[#1a6b6b]">{pct(scoreInfo.score)}</span>
            </p>
          )}
        </div>
      )}
    </div>
  )
}

// Prototype grade ladder + score color for the accuracy readout (used by the
// stage-2 score box after reveal).
function gradeFor(score: number): string {
  if (score >= 90) return 'Civic genius'
  if (score >= 75) return 'Sharp eye'
  if (score >= 60) return 'Not bad'
  if (score >= 40) return 'Most people miss this'
  return 'Exactly why we built this'
}
function scoreColor(score: number): string {
  if (score >= 75) return '#3f8f2e'
  if (score >= 50) return '#9a6b12'
  return '#c0432a'
}

// ---------------------------------------------------------------------------
// "Grandkids forecast" — real Opportunity Atlas intergenerational mobility
// for the modal's location. For kids whose parents sat at the selected income
// bracket, what adult income percentile did they reach? We compare the local
// commuting zone to the U.S. on a 0–100 percentile scale. Every number is a real
// API value; when there's no local cell we show only the national one + the note.
// ---------------------------------------------------------------------------
const PARENT_INCOME_OPTIONS: { value: string; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'middle', label: 'Middle' },
  { value: 'high', label: 'High' },
]

interface ForecastBar {
  label: string
  pct: number
  color: string
}

/** One labelled 0–100 percentile bar. */
function PercentileBar({ bar }: { bar: ForecastBar }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-[12px]" style={FONT}>
        <span className="flex items-center gap-1.5 font-medium text-[#0f2b2b]">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: bar.color }} />
          {bar.label}
        </span>
        <span className="font-semibold tabular-nums text-[#0f2b2b]">{bar.pct.toFixed(1)}</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-[#eef4f4]">
        <div
          className="h-full rounded-full transition-[width] duration-300"
          style={{ width: `${Math.max(0, Math.min(100, bar.pct))}%`, backgroundColor: bar.color }}
        />
      </div>
    </div>
  )
}

function GrandkidsForecast({
  open,
  stateCode,
  city,
}: {
  open: boolean
  stateCode: string
  city?: string
}) {
  const [parentIncome, setParentIncome] = useState('low')

  const { data, isLoading, isError } = useQuery<GrandkidOutlookData>({
    queryKey: ['grandkid-outlook', stateCode, city, parentIncome],
    queryFn: () =>
      fetchGrandkidOutlook({ state: stateCode, city, parent_income: parentIncome }),
    enabled: open && !!stateCode,
    staleTime: 10 * 60 * 1000,
  })

  // Real national + (optional) local percentiles. Only ever drawn from a real
  // API value — never invented.
  const nat = data?.national
  const natPct =
    nat && nat.available && typeof nat.child_percentile === 'number' ? nat.child_percentile : null

  const local = data?.local
  const localPct =
    local && local.available && typeof local.child_percentile === 'number'
      ? local.child_percentile
      : null
  // local === null → no commuting zone matched; local.available === false → CZ
  // matched but this group has too little data. Both mean "national only".
  const hasLocal = localPct != null
  const localLabel = data?.cz_name || data?.scope_label || 'Your area'

  const bars: ForecastBar[] = []
  if (hasLocal) bars.push({ label: localLabel, pct: localPct as number, color: '#1a6b6b' })
  if (natPct != null) bars.push({ label: 'United States', pct: natPct, color: '#9bb8b8' })

  return (
    <div className="rounded-2xl border border-[#d4e8e8] bg-white p-5 shadow-[0_4px_20px_rgba(26,107,107,0.06)]">
      <h3 className="text-[15px] font-semibold text-[#0f2b2b]" style={SERIF}>
        Grandkids forecast
      </h3>
      <p className="mt-1 text-[12px] leading-relaxed text-[#6b8a8a]" style={FONT}>
        For kids who grow up here with{' '}
        <span className="font-semibold text-[#1a6b6b]">{parentIncome}-income</span> parents, the
        average adult income percentile they reach — compared with the U.S.
      </p>

      {/* Parent-income toggle. */}
      <div className="mt-4 inline-flex rounded-xl border border-[#d4e8e8] bg-[#f7fafb] p-0.5" role="group" aria-label="Parent income">
        {PARENT_INCOME_OPTIONS.map((o) => {
          const active = o.value === parentIncome
          return (
            <button
              key={o.value}
              type="button"
              onClick={() => setParentIncome(o.value)}
              aria-pressed={active}
              className={`rounded-lg px-3.5 py-1.5 text-[12px] font-semibold transition-colors ${
                active ? 'bg-[#1a6b6b] text-white' : 'text-[#56635e] hover:text-[#0f2b2b]'
              }`}
              style={FONT}
            >
              {o.label}
            </button>
          )
        })}
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="space-y-3" aria-hidden>
            {[0, 1].map((r) => (
              <div key={r}>
                <div className="mb-1 h-3 w-1/3 animate-pulse rounded bg-[#eef4f4]" />
                <div className="h-2.5 w-full animate-pulse rounded-full bg-[#eef4f4]" />
              </div>
            ))}
          </div>
        ) : isError || !data || natPct == null ? (
          <p className="py-4 text-[13px] text-[#9bb8b8]" style={FONT}>
            We couldn&apos;t load mobility data right now. Please try again in a moment.
          </p>
        ) : (
          <>
            {/* Local-CZ vs national comparison on a 0–100 percentile scale. */}
            <div className="space-y-3">
              {bars.map((b) => (
                <PercentileBar key={b.label} bar={b} />
              ))}
            </div>
            <p className="mt-1.5 text-[10px] uppercase tracking-[0.1em] text-[#9bb8b8]" style={MONO}>
              0 = bottom · 100 = top of the national income ladder
            </p>

            {/* Honest national-only explanation when there's no local number. */}
            {!hasLocal && (
              <p className="mt-3 rounded-lg bg-[#f7fafb] px-3 py-2 text-[12px] leading-relaxed text-[#6b8a8a]" style={FONT}>
                {local == null
                  ? 'We don’t have local mobility data matched to this place yet — showing the U.S. baseline.'
                  : `Not enough local data for ${localLabel} in this group — showing the U.S. baseline.`}
              </p>
            )}

            {/* API note — verbatim, generated from real numbers. */}
            {data.note && (
              <p className="mt-3 text-[12px] leading-relaxed text-[#6b8a8a]" style={FONT}>
                {data.note}
              </p>
            )}

            {/* Provenance. */}
            {data.source && (
              <p className="mt-3 border-t border-[#eef4f4] pt-2 text-[11px] text-[#9bb8b8]" style={FONT}>
                Source:{' '}
                {data.source_url ? (
                  <a
                    href={data.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline decoration-[#d4e8e8] underline-offset-2 hover:text-[#1a6b6b]"
                  >
                    {data.source}
                  </a>
                ) : (
                  data.source
                )}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Loading skeleton.
// ---------------------------------------------------------------------------
function ModalSkeleton() {
  return (
    <div className="grid gap-5 md:grid-cols-2" aria-hidden>
      {[0, 1].map((col) => (
        <div key={col} className="space-y-5">
          {[0, 1].map((card) => (
            <div key={card} className="rounded-2xl border border-[#d4e8e8] bg-white p-5">
              <div className="h-4 w-1/3 animate-pulse rounded bg-[#eef4f4]" />
              <div className="mt-4 space-y-3">
                {[0, 1, 2, 3].map((r) => (
                  <div key={r} className="h-3 animate-pulse rounded-full bg-[#eef4f4]" />
                ))}
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

// ===========================================================================
// The modal.
// ===========================================================================
export default function MoneyGameModal({
  open,
  onClose,
  stateCode,
  city,
  county,
  requestedLabel,
}: MoneyGameModalProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['local-finance', stateCode, city, county],
    queryFn: () => fetchLocalFinance({ state: stateCode, city, county }),
    enabled: open && !!stateCode,
    staleTime: 5 * 60 * 1000,
  })

  const game = useMemo(() => (data ? buildGameCategories(data.categories) : []), [data])

  // Guess sliders start empty (0 = "not yet guessed"); the user must drag each
  // category before they can reveal. `touched` tracks which have been moved.
  const [guesses, setGuesses] = useState<number[]>([])
  const [touched, setTouched] = useState<boolean[]>([])
  const [revealed, setRevealed] = useState(false)
  // Prototype's 3-stage flow: 1 your bill → 2 the guessing game → 3 the grandkids.
  const [stage, setStage] = useState<'estimate' | 'game' | 'grandkids'>('estimate')

  // Reset the game whenever it (re)opens or the category set changes.
  useEffect(() => {
    setGuesses(game.map(() => 0))
    setTouched(game.map(() => false))
    setRevealed(false)
    setStage('estimate')
  }, [open, game])

  // Score = 100 - totalError/2, where totalError sums |normalizedGuess - actual|
  // across the shown set (same formula as the prototype). Only after reveal.
  const scoreInfo = useMemo<{ score: number; totalError: number } | null>(() => {
    if (!revealed || game.length === 0 || guesses.length !== game.length) return null
    const guessTotal = guesses.reduce((s, g) => s + g, 0)
    if (guessTotal <= 0) return null
    const totalError = game.reduce((sum, c, i) => {
      const ng = (guesses[i] / guessTotal) * 100
      return sum + Math.abs(ng - c.actual)
    }, 0)
    return { score: Math.max(0, Math.min(100, 100 - totalError / 2)), totalError }
  }, [revealed, game, guesses])

  const title = data ? `Your ${data.jurisdiction_name} impact` : 'Your local money impact'

  return (
    <Transition appear show={open} as={Fragment}>
      <Dialog as="div" className="relative z-[60]" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-[#0f2b2b]/50 backdrop-blur-sm" aria-hidden="true" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-3 sm:p-6">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-200"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-150"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="relative flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-3xl bg-[#f7fafb] text-left shadow-2xl">
                {/* Pinned header — stays put while only the body below scrolls. */}
                <div className="relative shrink-0 px-5 pb-4 pt-5 sm:px-7 sm:pt-7">
                <button
                  type="button"
                  onClick={onClose}
                  className="absolute right-4 top-4 z-10 rounded-full bg-white/90 p-1.5 text-[#56635e] shadow-sm backdrop-blur transition-colors hover:bg-white hover:text-[#0f2b2b]"
                  aria-label="Close"
                >
                  <XMarkIcon className="h-5 w-5" />
                </button>

                <Dialog.Title
                  className="pr-10 text-[26px] font-semibold leading-tight text-[#0f2b2b]"
                  style={SERIF}
                >
                  {title}
                </Dialog.Title>

                {/* Subtitle — prototype-style, all real data. */}
                {data && (
                  <p className="mt-1 text-[13px] leading-relaxed text-[#6b8a8a]" style={FONT}>
                    {data.jurisdiction_name}
                    {data.state_code ? `, ${data.state_code}` : ''} · starts at the median household —
                    adjust the sliders to make it yours.
                  </p>
                )}

                {/* City→state fallback note — only on a true statewide fallback
                    (level "state"); a city-state like DC resolves to real city
                    data with matched=false but shouldn't claim a fallback. */}
                {data && !data.matched && data.level === 'state' && requestedLabel && (
                  <p className="mt-2 rounded-lg bg-[#fff4ea] px-3 py-2 text-[12px] text-[#9a6b12]" style={FONT}>
                    Showing {data.state} statewide figures — we don&apos;t have
                    local finance for {requestedLabel} yet.
                  </p>
                )}

                {/* Step indicator (1 · Your bill → 2 · The guessing game → 3 · The grandkids). */}
                {data && (
                  <div className="mt-3.5 flex flex-wrap gap-2">
                    {([
                      ['estimate', '1 · Your bill'],
                      ['game', '2 · The guessing game'],
                      ['grandkids', '3 · The grandkids'],
                    ] as const).map(([key, label]) => {
                      const unlocked = key !== 'grandkids' || revealed
                      const active = stage === key
                      return (
                        <button
                          key={key}
                          type="button"
                          onClick={() => unlocked && setStage(key)}
                          className={`rounded-full border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] transition-colors ${
                            active
                              ? 'border-[#1a6b6b] bg-[#f0faf8] text-[#1a6b6b]'
                              : unlocked
                                ? 'border-[#e2eaea] bg-white text-[#6b8a8a] hover:text-[#0f2b2b]'
                                : 'cursor-default border-[#eef4f4] bg-white text-[#cfe0e0]'
                          }`}
                          style={MONO}
                        >
                          {label}
                        </button>
                      )
                    })}
                  </div>
                )}
                </div>

                {/* Scrollable body — the only scroll region, so the bar sits in
                    the flat middle, not across the panel's rounded corners. */}
                <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5 pt-2 sm:px-7 sm:pb-7">
                  {isLoading ? (
                    <ModalSkeleton />
                  ) : isError || !data ? (
                    <div className="rounded-2xl border border-dashed border-[#d4e8e8] bg-white p-10 text-center">
                      <p className="text-sm text-[#6b8a8a]" style={FONT}>
                        We couldn&apos;t load finance data right now. Please try again in a moment.
                      </p>
                    </div>
                  ) : (
                    <>
                      {/* ── Stage 1: Your bill ── */}
                      {stage === 'estimate' && (
                        <YourBill
                          open={open}
                          stateCode={stateCode}
                          city={city}
                          county={county}
                          jurisdictionName={data.jurisdiction_name}
                          onContinue={() => setStage('game')}
                        />
                      )}

                      {/* ── Stage 2: The guessing game ── */}
                      {stage === 'game' && (
                        <div>
                          {game.length > 0 ? (
                            <GuessingGame
                              fin={data}
                              game={game}
                              revealed={revealed}
                              onReveal={() => setRevealed(true)}
                              guesses={guesses}
                              setGuesses={setGuesses}
                              touched={touched}
                              setTouched={setTouched}
                              scoreInfo={scoreInfo}
                            />
                          ) : (
                            <div className="rounded-2xl border border-dashed border-[#d4e8e8] bg-white p-6 text-center text-sm text-[#6b8a8a]" style={FONT}>
                              Spending-category breakdown isn&apos;t available for{' '}
                              {data.jurisdiction_name} yet.
                            </div>
                          )}

                          {/* Score + grandkids CTA, lands where the reveal happened. */}
                          {revealed && scoreInfo != null && (
                            <div className="mt-4 flex flex-wrap items-center gap-4 rounded-2xl border border-[#ccfbf1] bg-gradient-to-r from-[#f0faf8] to-[#f7fee7] px-5 py-4">
                              <span className="text-[34px] font-semibold leading-none" style={{ ...SERIF, color: scoreColor(scoreInfo.score) }}>
                                {pct(scoreInfo.score)}
                              </span>
                              <span className="min-w-[120px]">
                                <span className="block text-[14.5px] font-semibold text-[#0f2b2b]" style={FONT}>
                                  {gradeFor(scoreInfo.score)}
                                </span>
                                <span className="text-[9.5px] uppercase tracking-[0.04em] text-[#9bb8b8]" style={MONO}>
                                  Off by {Math.round(scoreInfo.totalError)} pts
                                </span>
                              </span>
                              <p className="min-w-[220px] flex-1 text-[13px] leading-relaxed text-[#44403c]" style={FONT}>
                                These dollars shape the schools, streets, and parks your grandkids grow
                                up with. Want to see how kids who grow up here actually fare?
                              </p>
                              <button
                                type="button"
                                onClick={() => setStage('grandkids')}
                                className="rounded-full bg-[#1a6b6b] px-4 py-2.5 text-[14px] font-semibold text-white transition-colors hover:bg-[#155757]"
                                style={FONT}
                              >
                                The grandkids forecast →
                              </button>
                            </div>
                          )}

                          <button
                            type="button"
                            onClick={() => setStage('estimate')}
                            className="mt-3 text-[13px] text-[#6b8a8a] underline transition-colors hover:text-[#0f2b2b]"
                            style={FONT}
                          >
                            ← Back to your bill
                          </button>
                        </div>
                      )}

                      {/* ── Stage 3: The grandkids ── */}
                      {stage === 'grandkids' && (
                        <div>
                          <GrandkidsForecast open={open} stateCode={stateCode} city={city} />

                          <div className="mt-5 rounded-2xl bg-[#1a6b6b] p-6 text-white">
                            <div className="flex flex-wrap items-center gap-5">
                              <div className="text-[28px] font-semibold leading-[1.05]" style={SERIF}>
                                Decisions
                                <br />
                                matter.
                              </div>
                              <p className="min-w-[240px] flex-1 text-[14px] leading-relaxed text-white/90" style={FONT}>
                                {scoreInfo != null && scoreInfo.score >= 75
                                  ? `You scored ${pct(scoreInfo.score)} — better than most. But the split changes one vote at a time, in meetings almost nobody watches. `
                                  : scoreInfo != null
                                    ? `You scored ${pct(scoreInfo.score)} — and that's typical. Most people can't say where their own money goes, because the decisions happen in meetings almost nobody watches. `
                                    : ''}
                                Every one of these dollars is set in a public meeting you can attend,
                                watch, and weigh in on. Open Navigator watches them for you.
                              </p>
                            </div>
                          </div>

                          <button
                            type="button"
                            onClick={() => setStage('game')}
                            className="mt-3 text-[13px] text-[#6b8a8a] underline transition-colors hover:text-[#0f2b2b]"
                            style={FONT}
                          >
                            ← Back to the game
                          </button>
                        </div>
                      )}

                      {/* Provenance — always shown. */}
                      <p className="mt-5 text-center text-[11px] text-[#9bb8b8]" style={MONO}>
                        Sources: U.S. Census · ACS property-tax rate · Tax Foundation sales tax · Opportunity Atlas
                      </p>
                    </>
                  )}
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  )
}
