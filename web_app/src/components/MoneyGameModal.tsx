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
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { XMarkIcon } from '@heroicons/react/24/outline'
import {
  fetchCombinedFinance,
  fetchLocalFinance,
  fetchPropertyTaxRate,
  fetchSalesTaxRate,
  type CombinedFinance,
  type CombinedGovernment,
  type LocalFinance,
  type LocalFinanceCategory,
  type PropertyTaxRate,
  type SalesTaxRate,
} from '../api/localFinance'
import {
  fetchGrandkidOutlook,
  type GrandkidOutlook as GrandkidOutlookData,
} from '../api/grandkidOutlook'
import { useLocation as useLocationContext, type LocationData } from '../contexts/LocationContext'
import { resolveCoordsToLocation, resolveZipToChoices } from '../utils/resolvePlace'

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

// Human label for a stacked government: "City of Tuscaloosa", "Tuscaloosa
// County", "Tuscaloosa City Schools".
function labelGovernment(g: CombinedGovernment): string {
  if (g.level === 'city') return `City of ${g.jurisdiction_name}`
  if (g.level === 'county') return `${g.jurisdiction_name} County`
  return `${g.jurisdiction_name} Schools`
}

function pct(n: number): string {
  return `${Math.round(n)}%`
}

// Pull a 4-digit year out of a number or a date-ish string ("2025-01-01" -> "2025")
// for the wire/string form (CLAUDE.md: serialize a bare year as a string). null
// when there's no usable year — we never fabricate one.
function yearOf(v: string | number | null | undefined): string | null {
  if (v == null) return null
  const m = /(\d{4})/.exec(String(v))
  return m ? m[1] : null
}

export interface MoneyGameModalProps {
  open: boolean
  onClose: () => void
  /** 2-letter state code. Optional: when absent (no known location), the modal's
   *  first tab shows a "where's home?" ZIP gate instead of the bill. */
  stateCode?: string
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

// Sliders reuse the design prototype's exact `.range-x` CSS (in index.css) —
// 8px inset track + 18px hollow thumb whose ring color is set per-slider via
// the `--tc` CSS variable. Unfilled track color is the prototype's #ddd8d3.
const SLIDER_UNFILLED = '#ddd8d3'

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
        <span className="shrink-0 font-semibold tabular-nums text-[#0f766e]">{display}</span>
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
            '--tc': '#0d9488',
            background: `linear-gradient(to right, #0d9488 ${filled}%, ${SLIDER_UNFILLED} ${filled}%)`,
          } as React.CSSProperties
        }
        className="range-x"
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
// "Who collects it" — taxes COLLECTED per resident, by level of government.
// Each segment is the REAL Census `taxes_per_capita` for that level (total taxes
// that government collects ÷ its population), fetched from the same /api/local-
// finance?level=… endpoint the spending drill-down uses. This is the government's
// collections normalized per head — NOT the user's personalized bill — so it's
// labelled as such. A level with no data (404 / null taxes_per_capita) is simply
// omitted; we never fabricate a segment.
const COLLECT_LEVELS = [
  { level: 'state', label: 'State', color: '#9ca3af' },
  { level: 'county', label: 'County', color: '#e0723a' },
  { level: 'city', label: 'City', color: '#1a6b6b' },
  { level: 'school_district', label: 'Schools', color: '#2f6fb0' },
] as const

function WhoCollectsBar({
  open,
  stateCode,
  city,
  county,
}: {
  open: boolean
  stateCode: string
  city?: string
  county?: string
}) {
  const results = useQueries({
    queries: COLLECT_LEVELS.map((l) => ({
      queryKey: ['who-collects', l.level, stateCode, city, county],
      queryFn: () => fetchLocalFinance({ state: stateCode, city, county, level: l.level }),
      enabled: open && !!stateCode,
      staleTime: 10 * 60 * 1000,
      retry: false,
    })),
  })

  const segments = COLLECT_LEVELS.flatMap((l, i) => {
    const value = results[i].data?.taxes_per_capita ?? null
    return value != null && value > 0
      ? [{ label: l.label as string, color: l.color as string, value }]
      : []
  })

  // Honest empty state: nothing to show until at least one level reports real
  // per-capita taxes. (Don't render a half-bar while still loading.)
  if (results.some((r) => r.isLoading)) return null
  if (segments.length === 0) return null

  const total = segments.reduce((s, x) => s + x.value, 0)

  return (
    <div className="mt-5 rounded-2xl border border-[#d4e8e8] bg-white p-4 md:p-5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#5d7d7d]" style={MONO}>
        Who collects it
      </p>
      <div className="mt-2.5 flex h-3.5 w-full overflow-hidden rounded-full bg-[#eef4f4]">
        {segments.map((s) => (
          <div
            key={s.label}
            style={{ width: `${(s.value / total) * 100}%`, backgroundColor: s.color }}
            title={`${s.label} · ${fmtDollars(s.value)} per resident`}
          />
        ))}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1">
        {segments.map((s) => (
          <span key={s.label} className="flex items-center gap-1.5 text-[12px] text-[#56635e]" style={FONT}>
            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: s.color }} />
            <span className="font-semibold text-[#0f2b2b]">{s.label}</span> {fmtDollars(s.value)}
          </span>
        ))}
      </div>
      <p className="mt-2 text-[10.5px] leading-relaxed text-[#5d7d7d]" style={FONT}>
        Taxes collected per resident, by level of government — Census Annual Survey of State &amp; Local
        Government Finances. This is each government&apos;s collections per head, not your personal bill.
      </p>
    </div>
  )
}

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
  // The data vintage for each rate — REAL years from the API, shown so the bill
  // is honest about how current it is (no fabricated "current year").
  const acsYear = yearOf(propQ.data?.acs_vintage_year)
  const salesYear = yearOf(salesQ.data?.as_of_date)

  const [own, setOwn] = useState(true)
  const [homeValue, setHomeValue] = useState<number | null>(null)
  // The user's own figures — start UNSET (0) so we never show a fabricated
  // default. Home value is the one seeded default, and it's the REAL local ACS
  // median (a citeable figure), framed as "the median household — adjust it".
  const [spend, setSpend] = useState(0)
  const [fees, setFees] = useState(0)
  const [income, setIncome] = useState(0)
  useEffect(() => {
    if (median != null) setHomeValue((v) => (v == null ? median : v))
  }, [median])

  const hv = homeValue ?? median ?? 0
  const homeMax = Math.max(1_000_000, Math.ceil(((median ?? 230_000) * 2.5) / 50_000) * 50_000)
  const propTax = own && propRate != null && hv > 0 ? hv * propRate : null
  const salesTax = salesFrac != null && spend > 0 ? spend * salesFrac : null

  // Only ever show line items backed by a real figure or the user's own input —
  // no $0 placeholder rows.
  const parts: { label: string; value: number; color: string }[] = []
  if (propTax != null && propTax > 0) parts.push({ label: 'Property tax', value: propTax, color: '#1a6b6b' })
  if (salesTax != null && salesTax > 0) parts.push({ label: 'Sales tax', value: salesTax, color: '#2a8576' })
  if (fees > 0) parts.push({ label: 'Fees & other', value: fees, color: '#7fd0c4' })
  const total = parts.reduce((s, p) => s + p.value, 0)
  const sharePct = income > 0 && total > 0 ? (total / income) * 100 : null

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
          <EstRow label="Your yearly spending on taxable goods" value={spend} min={0} max={100_000} step={500} onChange={setSpend} display={spend > 0 ? fmtDollars(spend) : 'add yours'} />
          <EstRow label="Your local fees (utilities, permits, garbage)" value={fees} min={0} max={2_500} step={50} onChange={setFees} display={fees > 0 ? fmtDollars(fees) : 'add yours'} />
          <EstRow label="Your household income" value={income} min={0} max={250_000} step={1_000} onChange={setIncome} display={income > 0 ? fmtDollars(income) : 'add yours'} />
        </div>

        {/* Live result */}
        <div className="flex-1 rounded-2xl border border-[#d4e8e8] bg-[#fafaf9] p-4 md:p-5">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#5d7d7d]" style={MONO}>
                You pay approximately
              </p>
              <p className="text-[36px] font-semibold leading-none text-[#0f2b2b]" style={SERIF}>
                {total > 0 ? fmtDollars(total) : '—'}
              </p>
              {total > 0 && (
                <p className="mt-1 text-[13px] text-[#56635e]" style={FONT}>
                  per year · {fmtDollars(total / 12)}/mo
                </p>
              )}
              {(acsYear || salesYear) && (
                <p className="mt-1 text-[10.5px] uppercase tracking-[0.08em] text-[#5d7d7d]" style={MONO}>
                  {acsYear ? `Property ${acsYear} ACS` : ''}
                  {acsYear && salesYear ? ' · ' : ''}
                  {salesYear ? `Sales ${salesYear}` : ''}
                </p>
              )}
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

          {(spend === 0 || income === 0) && (
            <p className="mt-3 rounded-lg bg-[#f0faf8] px-3 py-2 text-[12px] leading-relaxed text-[#2a5a52]" style={FONT}>
              Starts with {own ? `the real property tax on ${jurisdictionName}'s median home` : 'your inputs'}.
              Add your spending, fees, and income above to build your full bill — we don&apos;t fill those in for
              you.
            </p>
          )}
          <p className="mt-3 text-[11px] leading-relaxed text-[#5d7d7d]" style={FONT}>
            {propRate != null && (
              <>Property: {jurisdictionName}&apos;s {(propRate * 100).toFixed(2)}% effective ACS rate
                {acsYear ? ` (${acsYear} Census ACS)` : ' (Census)'}. </>
            )}
            {salesPct != null && (
              <>Sales: {salesPct.toFixed(2)}% combined state+local rate (Tax Foundation
                {salesYear ? `, ${salesYear}` : ''}). </>
            )}
            Spending, fees &amp; income are your own.
          </p>
        </div>
      </div>

      {/* Who collects it — REAL per-resident tax collections by level. */}
      <WhoCollectsBar open={open} stateCode={stateCode} city={city} county={county} />

      <button
        type="button"
        onClick={onContinue}
        className="mgm-pulse mt-5 w-full rounded-xl bg-[#1a6b6b] px-5 py-3.5 text-[15px] font-semibold text-white transition-colors hover:bg-[#155757]"
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
        className="mgm-ring flex h-24 w-24 shrink-0 items-center justify-center rounded-full border-[3px] border-dashed border-[#cfe0e0]"
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
          className="text-[9px] font-semibold uppercase leading-tight tracking-[0.08em] text-[#5d7d7d]"
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

// Small labelled conic donut for the reveal comparison (your guess vs. real).
function RevealDonut({
  parts,
  label,
  accent,
}: {
  parts: { pct: number; color: string }[]
  label: React.ReactNode
  accent?: boolean
}) {
  const total = parts.reduce((s, p) => s + p.pct, 0) || 1
  let acc = 0
  const stops = parts
    .map((p) => {
      const start = (acc / total) * 100
      acc += p.pct
      return `${p.color} ${start}% ${(acc / total) * 100}%`
    })
    .join(', ')
  return (
    <div
      className="relative h-[76px] w-[76px] shrink-0 rounded-full"
      style={{ background: `conic-gradient(${stops})` }}
      aria-hidden
    >
      <div className="absolute inset-[28%] flex items-center justify-center rounded-full bg-white text-center">
        <span
          className={`text-[8.5px] font-semibold uppercase leading-tight tracking-[0.06em] ${accent ? 'text-[#1a6b6b]' : 'text-[#5d7d7d]'}`}
          style={MONO}
        >
          {label}
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Spending-level selector. "Combined" (default) keeps the merged donut + the
// guessing game; the single-level options drill into one government's REAL
// expenditure-by-function breakdown (GET /api/local-finance?level=…). A level
// with no data 404s and is surfaced as an explicit empty state — NEVER a
// fabricated number (CLAUDE.md: No Fabricated Data).
// ---------------------------------------------------------------------------
type SpendingLevel = 'combined' | 'city' | 'county' | 'state' | 'school_district'

const SPENDING_LEVELS: { value: SpendingLevel; label: string }[] = [
  { value: 'combined', label: 'Combined' },
  { value: 'city', label: 'City' },
  { value: 'county', label: 'County' },
  { value: 'state', label: 'State' },
  { value: 'school_district', label: 'School' },
]

// The phrase used in empty-state copy ("No City spending data…").
function levelNoun(level: Exclude<SpendingLevel, 'combined'>): string {
  if (level === 'school_district') return 'school district'
  return level
}

// Segmented pill row of government levels. Accessible: a `tablist` of buttons
// with `aria-selected`; a level whose query 404'd is greyed + disabled (its
// `disabled` flag is set once we know there's no data for that level).
function LevelSelector({
  value,
  onChange,
  disabledLevels,
}: {
  value: SpendingLevel
  onChange: (l: SpendingLevel) => void
  disabledLevels: Partial<Record<SpendingLevel, boolean>>
}) {
  return (
    <div
      role="tablist"
      aria-label="Government level"
      className="inline-flex flex-wrap gap-1 rounded-xl border border-[#d4e8e8] bg-[#f7fafb] p-0.5"
    >
      {SPENDING_LEVELS.map((opt) => {
        const active = value === opt.value
        const disabled = !!disabledLevels[opt.value]
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={disabled}
            onClick={() => !disabled && onChange(opt.value)}
            className={`rounded-lg px-3.5 py-1.5 text-[12.5px] font-semibold transition-colors ${
              active
                ? 'bg-[#1a6b6b] text-white'
                : disabled
                  ? 'cursor-not-allowed text-[#cfe0e0]'
                  : 'text-[#56635e] hover:text-[#0f2b2b]'
            }`}
            style={FONT}
            title={disabled ? `No ${levelNoun(opt.value as Exclude<SpendingLevel, 'combined'>)} data for this location` : undefined}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

// A compact conic donut for a single level's expenditure-by-function split,
// with a legend list of REAL (category, amount, share) rows. Mirrors the
// combined reveal's palette/typography.
function SpendingDonut({ categories }: { categories: LocalFinanceCategory[] }) {
  const usable = categories.filter((c) => c.amount > 0)
  const total = usable.reduce((s, c) => s + c.amount, 0)
  if (total <= 0) return null
  let acc = 0
  const stops = usable
    .map((c, i) => {
      const start = (acc / total) * 100
      acc += c.amount
      return `${CAT_PALETTE[i % CAT_PALETTE.length]} ${start}% ${(acc / total) * 100}%`
    })
    .join(', ')
  return (
    <div
      className="relative h-[120px] w-[120px] shrink-0 rounded-full"
      style={{ background: `conic-gradient(${stops})` }}
      aria-hidden
    >
      <div className="absolute inset-[28%] rounded-full bg-white" />
    </div>
  )
}

// Drill into ONE government level's REAL expenditure-by-function breakdown.
// 404 (or empty categories) → explicit "no data" state; we never substitute
// another level's numbers.
function LevelBreakdown({
  open,
  level,
  stateCode,
  city,
  county,
  onNoData,
}: {
  open: boolean
  level: Exclude<SpendingLevel, 'combined'>
  stateCode: string
  city?: string
  county?: string
  /** Reported once we learn this level has no data (404), so the parent can
   *  grey out the tab. */
  onNoData: (level: Exclude<SpendingLevel, 'combined'>) => void
}) {
  const { data, isLoading, isError, error } = useQuery<LocalFinance>({
    queryKey: ['local-finance-level', level, stateCode, city, county],
    queryFn: () => fetchLocalFinance({ state: stateCode, city, county, level }),
    enabled: open && !!stateCode,
    staleTime: 5 * 60 * 1000,
    retry: false,
  })

  // A 404 from the API means "no data for this level" — surface it, don't retry
  // forever, and let the parent disable the tab.
  const status = (error as { response?: { status?: number } } | undefined)?.response?.status
  const is404 = status === 404
  useEffect(() => {
    if (is404) onNoData(level)
  }, [is404, level, onNoData])

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-[#d4e8e8] bg-white p-5" aria-hidden>
        <div className="h-4 w-1/3 animate-pulse rounded bg-[#eef4f4]" />
        <div className="mt-4 space-y-3">
          {[0, 1, 2, 3].map((r) => (
            <div key={r} className="h-3 animate-pulse rounded-full bg-[#eef4f4]" />
          ))}
        </div>
      </div>
    )
  }

  const noData = is404 || !data || data.categories.filter((c) => c.amount > 0).length === 0
  if (isError && !is404) {
    return (
      <div className="rounded-2xl border border-dashed border-[#d4e8e8] bg-white p-8 text-center text-sm text-[#6b8a8a]" style={FONT}>
        We couldn&apos;t load {levelNoun(level)} spending right now. Please try again in a moment.
      </div>
    )
  }
  if (noData) {
    return (
      <div className="rounded-2xl border border-dashed border-[#d4e8e8] bg-white p-8 text-center" style={FONT}>
        <p className="text-sm font-semibold text-[#0f2b2b]">
          No {levelNoun(level)} spending data for this location.
        </p>
        <p className="mt-1.5 text-[12.5px] leading-relaxed text-[#5d7d7d]">
          We only show figures that trace to a real government-finance record — so there&apos;s nothing to
          display for this level here. Try another level above.
        </p>
      </div>
    )
  }

  // Sort by amount desc so the donut and list read top-down.
  const cats = [...data.categories].filter((c) => c.amount > 0).sort((a, b) => b.amount - a.amount)

  return (
    <div className="rounded-2xl border border-[#d4e8e8] bg-white p-4 shadow-[0_4px_20px_rgba(26,107,107,0.06)] sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[15px] font-semibold text-[#0f2b2b]" style={SERIF}>
          {data.jurisdiction_name} — where it goes
        </h3>
        <span className="text-[11px] uppercase tracking-[0.06em] text-[#5d7d7d]" style={MONO}>
          FY {data.fiscal_year}
        </span>
      </div>

      {/* Statewide-fallback honesty note (matched===false). */}
      {!data.matched && (
        <p className="mt-2 rounded-lg bg-[#f7fafb] px-3 py-2 text-[12px] leading-relaxed text-[#6b8a8a]" style={FONT}>
          No exact {levelNoun(level)} match for this location — showing the statewide {levelNoun(level)} figures.
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-5">
        <SpendingDonut categories={cats} />
        <div className="min-w-[220px] flex-1 space-y-2">
          {data.direct_expenditure != null && data.direct_expenditure > 0 && (
            <div className="mb-1 flex items-baseline justify-between border-b border-[#eef4f4] pb-2">
              <span className="text-[12px] font-semibold uppercase tracking-[0.06em] text-[#5d7d7d]" style={MONO}>
                Total direct expenditure
              </span>
              <span className="text-[15px] font-semibold tabular-nums text-[#0f2b2b]" style={FONT}>
                {fmtDollars(data.direct_expenditure)}
              </span>
            </div>
          )}
          {cats.map((c, i) => (
            <div key={c.category} className="flex items-baseline justify-between text-[13px]" style={FONT}>
              <span className="flex min-w-0 items-center gap-1.5 font-medium text-[#0f2b2b]">
                <span
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: CAT_PALETTE[i % CAT_PALETTE.length] }}
                />
                <span className="truncate">{c.category}</span>
              </span>
              <span className="shrink-0 tabular-nums">
                {c.share_pct != null && (
                  <span className="font-semibold text-[#1a6b6b]">{pct(c.share_pct)}</span>
                )}
                <span className="ml-2 text-[#56635e]">{fmtDollars(c.amount)}</span>
              </span>
            </div>
          ))}
        </div>
      </div>

      <p className="mt-4 border-t border-[#eef4f4] pt-2 text-[11px] leading-relaxed text-[#5d7d7d]" style={FONT}>
        {data.source}
        {data.note ? ` · ${data.note}` : ''}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// LEFT: the guessing game. Sliders start empty; the user must drag every
// category before revealing, then each row shows the real share and how far
// off they were. Categories & shares are REAL (Census), never fabricated.
// ---------------------------------------------------------------------------
function GuessingGame({
  placeName,
  governments,
  game,
  revealed,
  onReveal,
  guesses,
  setGuesses,
  touched,
  setTouched,
}: {
  placeName: string
  governments: CombinedGovernment[]
  game: GameCategory[]
  revealed: boolean
  onReveal: () => void
  guesses: number[]
  setGuesses: (g: number[]) => void
  touched: boolean[]
  setTouched: (t: boolean[]) => void
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

  const schoolGov = governments.find((g) => g.level === 'school_district')

  return (
    <div className="rounded-2xl border border-[#d4e8e8] bg-white p-4 shadow-[0_4px_20px_rgba(26,107,107,0.06)]">
      <h3 className="text-[15px] font-semibold text-[#0f2b2b]" style={SERIF}>
        The guessing game
      </h3>

      {/* Dismissible scoring explainer. */}
      {!hintDismissed ? (
        <div className="mt-2 flex items-start gap-2 rounded-xl border border-[#cdece7] bg-[#f0faf8] px-3 py-2">
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
        <p className="mt-2 text-[12px] leading-relaxed text-[#5d7d7d]" style={FONT}>
          Slide your gut feeling, then reveal to score against the real budget.
        </p>
      )}

      {/* Guessing: donut + sliders (hidden once revealed). */}
      {!revealed && (
        <>
          <div className="mx-auto mt-4 flex max-w-[640px] flex-wrap items-center justify-center gap-x-5 gap-y-3">
            <GuessDonut game={game} guesses={guesses} touched={touched} />

            <div className="min-w-[200px] max-w-[440px] flex-1 space-y-2">
              {game.map((c, i) => {
                const color = CAT_PALETTE[i % CAT_PALETTE.length]
                const fill = touched[i] ? Math.round(guesses[i]) : 0
                return (
                  <div key={c.category}>
                    <div className="mb-1 flex items-center justify-between text-[13px]" style={FONT}>
                      <span className="flex items-center gap-1.5 font-medium text-[#0f2b2b]">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                        {c.category}
                        {i === firstUntouched && (
                          <span className="mgm-nudge text-[11px] font-semibold text-[#1a6b6b]">
                            drag to guess →
                          </span>
                        )}
                      </span>
                      <span className="tabular-nums">
                        {touched[i] ? (
                          <span className="font-semibold text-[#1a6b6b]">{pct(normGuess(i))}</span>
                        ) : (
                          <span className="font-semibold text-[#cfe0e0]">?</span>
                        )}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      step={1}
                      value={Math.round(guesses[i])}
                      onChange={(e) => setOne(i, Number(e.target.value))}
                      style={
                        {
                          '--tc': color,
                          background: `linear-gradient(to right, ${color} ${fill}%, ${SLIDER_UNFILLED} ${fill}%)`,
                        } as React.CSSProperties
                      }
                      className="range-x"
                      aria-label={`Your guess for ${c.category}`}
                    />
                    {/* Read-only drill-down for the "Other" bucket. */}
                    {c.breakdown && c.breakdown.length > 0 && (
                      <div className="mt-2">
                        <button
                          type="button"
                          onClick={() => setOtherExpanded((v) => !v)}
                          aria-expanded={otherExpanded}
                          className="flex items-center gap-1 text-[11px] font-medium text-[#1a6b6b] transition-colors hover:text-[#0f2b2b]"
                          style={FONT}
                        >
                          <span className="inline-block transition-transform" style={{ transform: otherExpanded ? 'rotate(90deg)' : 'none' }} aria-hidden>
                            ▸
                          </span>
                          {otherExpanded ? 'Hide what’s inside' : 'What’s in “Other”?'}
                        </button>
                        {otherExpanded && (
                          <ul className="mt-1.5 space-y-1 rounded-lg border border-[#eef4f4] bg-[#f7fafb] px-3 py-2">
                            {c.breakdown.map((part) => (
                              <li key={part.label} className="flex items-center justify-between text-[11px]" style={FONT}>
                                <span className="text-[#56635e]">{part.label}</span>
                                <span className="text-[#5d7d7d]">included</span>
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

          <button
            type="button"
            onClick={() => allGuessed && onReveal()}
            disabled={!allGuessed}
            className={`mt-4 w-full rounded-xl px-5 py-3 text-[15px] font-semibold transition-colors ${
              allGuessed ? 'mgm-pulse bg-[#1a6b6b] text-white hover:bg-[#155757]' : 'cursor-default bg-[#eef4f4] text-[#5d7d7d]'
            }`}
            style={FONT}
          >
            {allGuessed ? 'Reveal reality' : `Guess all ${game.length} to reveal · ${game.length - touchedCount} to go`}
          </button>
        </>
      )}

      {/* Reveal: your guess vs the real budget — two donuts + grow-in bars with
          a vertical guess marker. */}
      {revealed && (
        <div className="mt-4 mgm-fade">
          <div className="flex flex-wrap items-center gap-5">
            <div className="flex shrink-0 gap-3">
              <RevealDonut
                parts={game.map((_, i) => ({ pct: guesses[i], color: CAT_PALETTE[i % CAT_PALETTE.length] }))}
                label={<>YOUR<br />GUESS</>}
              />
              <RevealDonut
                parts={game.map((c, i) => ({ pct: c.actual, color: CAT_PALETTE[i % CAT_PALETTE.length] }))}
                label="REAL"
                accent
              />
            </div>
            <div className="min-w-[240px] flex-1 space-y-2.5">
              {game.map((c, i) => {
                const g = normGuess(i)
                const d = Math.round(g - c.actual)
                const color = CAT_PALETTE[i % CAT_PALETTE.length]
                return (
                  <div key={c.category}>
                    <div className="flex items-baseline justify-between text-[12.5px]" style={FONT}>
                      <span className="flex items-center gap-1.5 font-medium text-[#0f2b2b]">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                        {c.category}
                      </span>
                      <span>
                        <span className="font-semibold tabular-nums text-[#0f2b2b]">{pct(c.actual)}</span>
                        <span className="ml-1.5 text-[11px]" style={{ color: Math.abs(d) >= 8 ? '#9a6b12' : '#9bb8b8' }}>
                          {Math.abs(d) <= 3 ? '✓ close' : d > 0 ? `${Math.abs(d)} high` : `${Math.abs(d)} low`}
                        </span>
                      </span>
                    </div>
                    <div className="relative mt-1 h-2.5 rounded-full bg-[#f1f5f5]">
                      <div className="mgm-grow h-full rounded-full" style={{ width: `${Math.min(100, c.actual)}%`, backgroundColor: color }} />
                      <div
                        className="absolute -top-[3px] h-[15px] w-[2.5px] rounded bg-[#0f2b2b]"
                        style={{ left: `calc(${Math.min(100, g)}% - 1px)` }}
                        title={`Your guess: ${pct(g)}`}
                      />
                    </div>
                  </div>
                )
              })}
              <p className="text-[9.5px] uppercase tracking-[0.05em] text-[#5d7d7d]" style={MONO}>
                Bar = real budget · | = your guess
              </p>
            </div>
          </div>

          {top && (
            <p className="mt-3.5 text-center text-[13px] leading-relaxed text-[#6b8a8a]" style={FONT}>
              <span className="font-semibold text-[#1a6b6b]">{pct(top.actual)}</span> of every local dollar
              goes to {top.category} alone — every year.
            </p>
          )}

          {/* These are REAL combined Census figures — city + county + school
              district stacked. That's why Education is a big slice now. */}
          <p className="mt-2 rounded-lg bg-[#f7fafb] px-3 py-2 text-center text-[11.5px] leading-relaxed text-[#6b8a8a]" style={FONT}>
            This stacks {placeName}&apos;s city, county
            {schoolGov ? <> and school district ({schoolGov.jurisdiction_name} Schools)</> : null} budgets —
            the full local government you fund (U.S. Census). &ldquo;Administration&rdquo; also folds in
            general spending the Census doesn&apos;t classify elsewhere.
          </p>
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
// Selector options — REAL Opportunity Atlas dimensions (value -> API code).
const PARENT_OPTIONS: [string, string][] = [
  ['low', 'Low'],
  ['middle', 'Middle'],
  ['high', 'High'],
]
const RACE_OPTIONS: [string, string][] = [
  ['pooled', 'All'],
  ['black', 'Black'],
  ['white', 'White'],
  ['hisp', 'Hispanic'],
  ['asian', 'Asian'],
]
const GENDER_OPTIONS: [string, string][] = [
  ['pooled', 'All'],
  ['female', 'Female'],
  ['male', 'Male'],
]

// Prototype-style vertical dot-column selector (radio dots).
function DotColumn({
  title,
  options,
  active,
  onSelect,
}: {
  title: string
  options: [string, string][]
  active: string
  onSelect: (v: string) => void
}) {
  return (
    <div>
      <div
        className="mb-2 whitespace-pre-line text-[10px] font-semibold uppercase leading-tight tracking-[0.08em] text-[#5d7d7d]"
        style={MONO}
      >
        {title}
      </div>
      {options.map(([value, label]) => {
        const isActive = active === value
        return (
          <button
            key={value}
            type="button"
            onClick={() => onSelect(value)}
            className="flex items-center gap-2 py-1"
          >
            <span
              className="box-border h-[11px] w-[11px] shrink-0 rounded-full transition-colors"
              style={{
                background: isActive ? '#1a6b6b' : '#fff',
                border: isActive ? '2px solid #1a6b6b' : '1.5px solid #a8a29e',
              }}
            />
            <span
              className="text-[10.5px] font-semibold uppercase tracking-[0.05em] transition-colors"
              style={{ ...MONO, color: isActive ? '#1a6b6b' : '#44403c' }}
            >
              {label}
            </span>
          </button>
        )
      })}
    </div>
  )
}

// REAL local-vs-U.S. slope on a 0–100 child-income-rank scale. (The Atlas is a
// single cohort, so we compare place-vs-nation — not the prototype's invented
// 1978-vs-1992 cohorts.)
function SlopeChart({
  localPct,
  natPct,
  localLabel,
}: {
  localPct: number | null
  natPct: number
  localLabel: string
}) {
  const W = 320
  const H = 134
  const topY = 16
  const botY = 104
  const y = (p: number) => botY - (Math.max(0, Math.min(100, p)) / 100) * (botY - topY)
  const xUS = 66
  const xLoc = 232
  const short = localLabel.length > 14 ? localLabel.slice(0, 13) + '…' : localLabel
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Child income rank: your area vs the U.S.">
      {[25, 50, 75].map((g) => (
        <g key={g}>
          <line x1="58" x2="250" y1={y(g)} y2={y(g)} stroke="#f1f5f5" strokeWidth="1" />
          <text x="52" y={y(g) + 3} fontSize="8.5" fill="#9bb8b8" textAnchor="end" fontFamily="'IBM Plex Mono', monospace">{g}</text>
        </g>
      ))}
      {localPct != null ? (
        <>
          <line x1={xUS} y1={y(natPct)} x2={xLoc} y2={y(localPct)} stroke="#1a6b6b" strokeWidth="2.5" strokeLinecap="round" />
          <circle cx={xUS} cy={y(natPct)} r="4.5" fill="#9bb8b8" />
          <circle cx={xLoc} cy={y(localPct)} r="5" fill="#1a6b6b" />
          <text x={xLoc + 9} y={y(localPct) + 1} fontSize="11" fontWeight="800" fill="#1a6b6b" fontFamily="'Source Sans 3', sans-serif">
            {localPct.toFixed(0)} {short}
          </text>
          <text x={xUS - 9} y={y(natPct) - 6} fontSize="10" fontWeight="700" fill="#9bb8b8" textAnchor="end" fontFamily="'Source Sans 3', sans-serif">
            {natPct.toFixed(0)} U.S.
          </text>
        </>
      ) : (
        <>
          <line x1="58" x2="250" y1={y(natPct)} y2={y(natPct)} stroke="#9bb8b8" strokeWidth="2.5" strokeDasharray="4 3" />
          <text x="250" y={y(natPct) - 6} fontSize="10.5" fontWeight="700" fill="#9bb8b8" textAnchor="end" fontFamily="'Source Sans 3', sans-serif">
            U.S. avg {natPct.toFixed(0)}
          </text>
        </>
      )}
      <text x={xUS} y={H - 4} fontSize="9" fill="#78716c" textAnchor="middle" fontFamily="'IBM Plex Mono', monospace">U.S. AVG</text>
      <text x={xLoc} y={H - 4} fontSize="9" fill="#1c1917" fontWeight="700" textAnchor="middle" fontFamily="'IBM Plex Mono', monospace">{short.toUpperCase()}</text>
    </svg>
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
  const [race, setRace] = useState('pooled')
  const [gender, setGender] = useState('pooled')

  const { data, isLoading, isError } = useQuery<GrandkidOutlookData>({
    queryKey: ['grandkid-outlook', stateCode, city, parentIncome, race, gender],
    queryFn: () => fetchGrandkidOutlook({ state: stateCode, city, parent_income: parentIncome, race, gender }),
    enabled: open && !!stateCode,
    staleTime: 10 * 60 * 1000,
  })

  // Real national + (optional) local percentiles — only ever a real API value.
  const nat = data?.national
  const natPct = nat && nat.available && typeof nat.child_percentile === 'number' ? nat.child_percentile : null
  const local = data?.local
  const localPct =
    local && local.available && typeof local.child_percentile === 'number' ? local.child_percentile : null
  const hasLocal = localPct != null
  const localLabel = data?.cz_name || data?.scope_label || 'Your area'
  const blank = isLoading || isError || !data || natPct == null
  const diff = !blank && hasLocal ? (localPct as number) - (natPct as number) : null

  const raceLabel = RACE_OPTIONS.find(([v]) => v === race && v !== 'pooled')?.[1]
  const genderLabel = GENDER_OPTIONS.find(([v]) => v === gender && v !== 'pooled')?.[1]
  const demoQual = [raceLabel, genderLabel].filter(Boolean).join(' · ')

  const verdict = blank
    ? 'Grandkids forecast'
    : !hasLocal
      ? 'Grandkids forecast'
      : diff != null && Math.abs(diff) < 1
        ? `Kids raised in ${localLabel} land about the U.S. average`
        : diff != null && diff > 0
          ? `Better off: kids raised in ${localLabel} reach a higher income rank than the U.S. average`
          : `Tougher odds: kids raised in ${localLabel} reach a lower income rank than the U.S. average`

  return (
    <div className="overflow-hidden rounded-2xl border border-[#d4e8e8] bg-white shadow-[0_4px_20px_rgba(26,107,107,0.06)]">
      {/* Teal verdict header (real numbers only). */}
      <div className="bg-[#1a6b6b] px-5 py-3.5 text-white">
        <h3 className="text-[15.5px] font-semibold leading-snug" style={SERIF}>
          {verdict}
        </h3>
        <p className="mt-0.5 text-[12px] text-white/85" style={FONT}>
          Adult income rank for kids with <span className="font-semibold">{parentIncome}-income</span> parents
          {demoQual ? ` · ${demoQual}` : ''} · vs the U.S.
        </p>
      </div>

      <div className="flex flex-wrap items-start gap-5 p-5">
        {/* Dot-column selectors — REAL Atlas dimensions. */}
        <div className="flex shrink-0 gap-5">
          <DotColumn title={'Parent\nincome'} options={PARENT_OPTIONS} active={parentIncome} onSelect={setParentIncome} />
          <DotColumn title={'Child\nrace'} options={RACE_OPTIONS} active={race} onSelect={setRace} />
          <DotColumn title={'Child\ngender'} options={GENDER_OPTIONS} active={gender} onSelect={setGender} />
        </div>

        {/* Chart — dashed "?" while blank, else the local-vs-U.S. slope. */}
        <div className="min-w-[220px] flex-1">
          {blank ? (
            <div className="flex h-[134px] items-center justify-center">
              <div className="mgm-ring flex h-24 w-24 items-center justify-center rounded-full border-[3px] border-dashed border-[#cfe0e0]" aria-hidden>
                <span className="text-[30px] font-semibold text-[#cfe0e0]" style={SERIF}>?</span>
              </div>
            </div>
          ) : (
            <>
              <SlopeChart localPct={hasLocal ? (localPct as number) : null} natPct={natPct as number} localLabel={localLabel} />
              <p className="mt-1 text-[9.5px] uppercase tracking-[0.08em] text-[#5d7d7d]" style={MONO}>
                0 = bottom · 100 = top of the U.S. income ladder
              </p>
            </>
          )}
        </div>
      </div>

      {/* Notes — honest about missing local cells + provenance. */}
      <div className="px-5 pb-4">
        {isError && (
          <p className="text-[12px] text-[#5d7d7d]" style={FONT}>
            We couldn&apos;t load mobility data right now. Try again, or change a filter.
          </p>
        )}
        {!blank && !hasLocal && (
          <p className="rounded-lg bg-[#f7fafb] px-3 py-2 text-[12px] leading-relaxed text-[#6b8a8a]" style={FONT}>
            {local == null
              ? 'No local mobility data matched to this place for this group yet — showing the U.S. baseline.'
              : `Not enough local data for ${localLabel} in this group — showing the U.S. baseline.`}
          </p>
        )}
        {!blank && data?.note && (
          <p className="mt-2 text-[12px] leading-relaxed text-[#6b8a8a]" style={FONT}>
            {data.note}
          </p>
        )}
        {!blank && data?.source && (
          <p className="mt-2 border-t border-[#eef4f4] pt-2 text-[11px] text-[#5d7d7d]" style={FONT}>
            Source:{' '}
            {data.source_url ? (
              <a href={data.source_url} target="_blank" rel="noopener noreferrer" className="underline decoration-[#d4e8e8] underline-offset-2 hover:text-[#1a6b6b]">
                {data.source}
              </a>
            ) : (
              data.source
            )}
          </p>
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
// "First — where's home?" — the in-modal location gate (tab 1) shown when the
// modal opens without a known place. The ZIP/coords resolve to a REAL place via
// the shared /api/geocode helpers (never fabricated); a ZIP that spans cities /
// city-vs-county offers the real choices, since city taxes stack on the county's.
function WhereIsHome({ onResolved }: { onResolved: (loc: LocationData) => void }) {
  const [zip, setZip] = useState('')
  const [busy, setBusy] = useState(false)
  const [locating, setLocating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [choices, setChoices] = useState<{ label: string; loc: LocationData }[] | null>(null)

  const zipValid = /^\d{5}$/.test(zip)
  const needsChoice = !!choices && choices.length > 1

  const resolveZip = async () => {
    setError(null)
    setChoices(null)
    setBusy(true)
    try {
      const opts = await resolveZipToChoices(zip)
      if (opts.length === 0) {
        setError("We couldn't find that ZIP. Try another, or use your location.")
      } else if (opts.length === 1) {
        onResolved(opts[0].loc)
      } else {
        setChoices(opts)
      }
    } catch {
      setError("We couldn't look up that ZIP right now. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  const handleShow = () => {
    if (busy || needsChoice) return
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
          const loc = await resolveCoordsToLocation(coords.latitude, coords.longitude)
          if (!loc) {
            setError("We couldn't pin your location. Enter your ZIP instead.")
            return
          }
          onResolved(loc)
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

  return (
    <div className="rounded-2xl border border-[#d4e8e8] bg-white px-5 py-8 text-center sm:py-10">
      <h3 className="text-[22px] font-semibold text-[#0f2b2b]" style={SERIF}>
        First — where&apos;s home?
      </h3>
      <p className="mx-auto mt-1.5 max-w-sm text-[13.5px] leading-relaxed text-[#6b8a8a]" style={FONT}>
        Every town reaches into your pocket a little differently. Just the ZIP — nothing stored.
      </p>

      <div className="mt-5 flex flex-wrap items-center justify-center gap-2.5">
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
          className="w-40 rounded-full border-[1.5px] px-4 py-3 text-center text-[16px] tracking-[0.12em] outline-none transition-colors"
          style={{ ...MONO, borderColor: zipValid ? '#1a6b6b' : '#d4e8e8' }}
        />
        <button
          type="button"
          onClick={handleShow}
          disabled={busy || needsChoice || !zipValid}
          className="rounded-full px-6 py-3 text-[15px] font-semibold text-white transition-colors"
          style={{
            ...FONT,
            backgroundColor: zipValid && !needsChoice ? '#1a6b6b' : '#cfe0e0',
            cursor: zipValid && !needsChoice && !busy ? 'pointer' : 'default',
          }}
        >
          {busy ? 'Finding…' : needsChoice ? 'Pick your area' : 'Show me my money'}
        </button>
      </div>

      {/* Real geography: this ZIP spans places / city limits, and city rates stack
          on the county's, so the choice changes the bill. */}
      {needsChoice && choices && (
        <div className="mt-4">
          <p className="text-[13px] font-semibold text-[#56635e]" style={FONT}>
            {zip} crosses jurisdiction lines — where&apos;s home? (City taxes stack on the county&apos;s.)
          </p>
          <div className="mt-2 flex flex-wrap justify-center gap-2">
            {choices.map((c, i) => (
              <button
                key={c.label + i}
                type="button"
                onClick={() => onResolved(c.loc)}
                className="rounded-full border border-[#d4e8e8] bg-white px-4 py-2 text-[13.5px] font-semibold text-[#0f2b2b] transition-colors hover:border-[#1a6b6b]"
                style={FONT}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && (
        <p className="mt-3 text-[12.5px] font-semibold text-[#b45309]" style={FONT}>
          {error}
        </p>
      )}

      <button
        type="button"
        onClick={useMyLocation}
        className="mt-4 block w-full text-[13px] font-semibold text-[#0f766e] transition-colors hover:underline"
        style={FONT}
      >
        {locating ? 'Locating…' : '📍 or use my location'}
      </button>
    </div>
  )
}

export default function MoneyGameModal({
  open,
  onClose,
  stateCode,
  city,
  county,
  requestedLabel,
}: MoneyGameModalProps) {
  const { location, setLocation } = useLocationContext()

  // The place the bill is scoped to. Seeded from props (the banner passes the
  // known location), else the resolved context location; when neither exists,
  // tab 1 shows the "where's home?" gate and `place` is filled from it.
  const [place, setPlace] = useState<LocationData | null>(null)
  useEffect(() => {
    if (!open) return
    if (stateCode) {
      setPlace({ state: stateCode, city: city || '', county: county || '', address: requestedLabel || '' })
    } else if (location?.state) {
      setPlace(location)
    }
    // else: leave null → the gate is shown.
  }, [open, stateCode, city, county]) // eslint-disable-line react-hooks/exhaustive-deps

  const scopeState = place?.state
  const scopeCity = place?.city || undefined
  const scopeCounty = place?.county || undefined
  const hasPlace = !!scopeState

  const onResolvePlace = useCallback(
    (loc: LocationData) => {
      setPlace(loc)
      setLocation(loc) // persist the choice site-wide, like the home banner
    },
    [setLocation],
  )

  // Re-open the "where's home?" gate so a user with an already-known place (e.g.
  // a previously cached location) can switch to a different ZIP. Only clears the
  // modal's scope — the site-wide saved location is left untouched until they
  // resolve a new one via the gate (which calls onResolvePlace).
  const changePlace = useCallback(() => setPlace(null), [])

  // Combined city + county + school-district budget — the full local government
  // a resident funds, so the guessing game's "Education" reflects real K-12.
  const { data, isLoading, isError } = useQuery<CombinedFinance>({
    queryKey: ['combined-finance', scopeState, scopeCity, scopeCounty],
    queryFn: () => fetchCombinedFinance({ state: scopeState as string, city: scopeCity, county: scopeCounty }),
    enabled: open && hasPlace,
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
  // Which government level's "where it goes" breakdown is shown in stage 2.
  // 'combined' (default) keeps the merged donut + the guessing game; the others
  // drill into one government via /api/local-finance?level=…
  const [spendingLevel, setSpendingLevel] = useState<SpendingLevel>('combined')
  // Levels we've learned have no data (404) — greyed out in the selector.
  const [disabledLevels, setDisabledLevels] = useState<Partial<Record<SpendingLevel, boolean>>>({})
  const markLevelNoData = useCallback((l: Exclude<SpendingLevel, 'combined'>) => {
    setDisabledLevels((prev) => (prev[l] ? prev : { ...prev, [l]: true }))
  }, [])

  // Reset the game whenever it (re)opens or the category set changes.
  useEffect(() => {
    setGuesses(game.map(() => 0))
    setTouched(game.map(() => false))
    setRevealed(false)
    setStage('estimate')
    setSpendingLevel('combined')
    setDisabledLevels({})
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

  // Human label for the scoped place (the user's CHOSEN place, else the matched
  // jurisdiction). Drives the subtitle; the title stays place-agnostic.
  const placeName = scopeCity || scopeCounty || requestedLabel || data?.jurisdiction_name || null
  const title = 'Your money, mapped'

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
              <Dialog.Panel className="relative max-h-[90vh] w-full max-w-4xl overflow-y-auto overscroll-contain rounded-3xl bg-[#f7fafb] text-left shadow-2xl">
                {/* The whole panel scrolls; the close button sticks at the top
                    via a zero-height sticky bar so it stays reachable. */}
                <div className="pointer-events-none sticky top-0 z-20 flex h-0 justify-end">
                  <button
                    type="button"
                    onClick={onClose}
                    className="pointer-events-auto mr-3 mt-3 rounded-full bg-white/90 p-1.5 text-[#56635e] shadow-sm backdrop-blur transition-colors hover:bg-white hover:text-[#0f2b2b] sm:mr-4 sm:mt-4"
                    aria-label="Close"
                  >
                    <XMarkIcon className="h-5 w-5" />
                  </button>
                </div>
                <div className="px-5 pb-6 pt-4 sm:px-7 sm:pb-7 sm:pt-5">

                <Dialog.Title
                  className="pr-10 text-[26px] font-semibold leading-tight text-[#0f2b2b]"
                  style={SERIF}
                >
                  {title}
                </Dialog.Title>

                {/* Subtitle — prototype-style, all real data. */}
                <p className="mt-1 text-[13px] leading-relaxed text-[#6b8a8a]" style={FONT}>
                  {hasPlace ? (
                    <>
                      {placeName || data?.jurisdiction_name}
                      {data?.state_code ? `, ${data.state_code}` : ''}{' '}
                      <button
                        type="button"
                        onClick={changePlace}
                        className="font-semibold text-[#0f766e] underline-offset-2 hover:underline"
                        style={FONT}
                      >
                        (change)
                      </button>{' '}
                      · starts at the median household — adjust the sliders to make it yours.
                    </>
                  ) : (
                    <>First, tell us where home is — every town reaches into your pocket a little differently.</>
                  )}
                </p>

                {/* Stacked-governments callout — the FULL local government a
                    resident funds (city + county + their school district), so
                    K-12 spending is included rather than hidden. */}
                {data && data.governments.length > 0 && (
                  <div className="mt-2 rounded-lg bg-[#f0faf8] px-3 py-2 text-[#2a5a52]" style={FONT}>
                    <p className="text-[15px] font-bold leading-snug">
                      {data.governments.map((g) => labelGovernment(g)).join(' + ')}
                    </p>
                    <p className="mt-0.5 text-[12px] leading-relaxed text-[#3f6f67]">
                      Stacked, because you fund all of them.
                    </p>
                  </div>
                )}

                {/* Step indicator (1 · Your bill → 2 · The guessing game → 3 · The grandkids).
                    Tab 1 is always available (it hosts the "where's home?" gate); the
                    others unlock once a place is chosen and its data has loaded. */}
                <div className="mt-3.5 flex flex-wrap gap-2">
                  {([
                    ['estimate', '1 · Your bill'],
                    ['game', '2 · The guessing game'],
                    ['grandkids', '3 · The grandkids'],
                  ] as const).map(([key, label]) => {
                      const unlocked = key === 'estimate' ? true : key === 'game' ? !!data : revealed
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

                <div className="mt-4">
                  {!hasPlace ? (
                    /* ── Tab 1 gate: resolve a real place before any bill ── */
                    <WhereIsHome onResolved={onResolvePlace} />
                  ) : isLoading ? (
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
                          stateCode={scopeState as string}
                          city={scopeCity}
                          county={scopeCounty}
                          jurisdictionName={data.jurisdiction_name}
                          onContinue={() => setStage('game')}
                        />
                      )}

                      {/* ── Stage 2: The guessing game ── */}
                      {stage === 'game' && (
                        <div>
                          {/* Level selector: Combined (the merged donut + game)
                              vs. a single government's REAL breakdown. */}
                          <div className="mb-4">
                            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5d7d7d]" style={MONO}>
                              Where your tax money goes
                            </div>
                            <LevelSelector
                              value={spendingLevel}
                              onChange={setSpendingLevel}
                              disabledLevels={disabledLevels}
                            />
                          </div>

                          {spendingLevel === 'combined' ? (
                            game.length > 0 ? (
                              <GuessingGame
                                placeName={placeName || data.jurisdiction_name}
                                governments={data.governments}
                                game={game}
                                revealed={revealed}
                                onReveal={() => setRevealed(true)}
                                guesses={guesses}
                                setGuesses={setGuesses}
                                touched={touched}
                                setTouched={setTouched}
                              />
                            ) : (
                              <div className="rounded-2xl border border-dashed border-[#d4e8e8] bg-white p-6 text-center text-sm text-[#6b8a8a]" style={FONT}>
                                Spending-category breakdown isn&apos;t available for{' '}
                                {data.jurisdiction_name} yet.
                              </div>
                            )
                          ) : (
                            <LevelBreakdown
                              open={open}
                              level={spendingLevel}
                              stateCode={scopeState as string}
                              city={scopeCity}
                              county={scopeCounty}
                              onNoData={markLevelNoData}
                            />
                          )}

                          {/* Score + grandkids CTA, lands where the reveal
                              happened — only on the Combined (guessing-game) view. */}
                          {spendingLevel === 'combined' && revealed && scoreInfo != null && (
                            <div className="mgm-fade mt-4 flex flex-wrap items-center gap-4 rounded-2xl border border-[#ccfbf1] bg-gradient-to-r from-[#f0faf8] to-[#f7fee7] px-5 py-4">
                              <span className="text-[34px] font-semibold leading-none" style={{ ...SERIF, color: scoreColor(scoreInfo.score) }}>
                                {pct(scoreInfo.score)}
                              </span>
                              <span className="min-w-[120px]">
                                <span className="block text-[14.5px] font-semibold text-[#0f2b2b]" style={FONT}>
                                  {gradeFor(scoreInfo.score)}
                                </span>
                                <span className="text-[9.5px] uppercase tracking-[0.04em] text-[#5d7d7d]" style={MONO}>
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
                                className="mgm-pulse rounded-full bg-[#1a6b6b] px-4 py-2.5 text-[14px] font-semibold text-white transition-colors hover:bg-[#155757]"
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
                          <GrandkidsForecast open={open} stateCode={scopeState as string} city={scopeCity} />

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
                      <p className="mt-5 text-center text-[11px] text-[#5d7d7d]" style={MONO}>
                        Sources: U.S. Census · ACS property-tax rate · Tax Foundation sales tax · Opportunity Atlas
                      </p>
                    </>
                  )}
                </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  )
}
