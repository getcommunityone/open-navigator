import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowTrendingUpIcon,
  DocumentCurrencyDollarIcon,
  HeartIcon,
  ArrowsRightLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline'
import api from '../lib/api'
import { formatCurrency, formatNumber } from '../utils/formatters'

// "Follow the money" homepage section (Money Moves lens).
//
// Three drill-down cards framed by *who is paying whom*. Every figure is LIVE,
// traced to the warehouse:
//   • Money out  — real money-flagged civic decisions (net_dollar_impact) the
//                  parent already fetched from GET /api/lenses, passed in as
//                  `moneyCards`.
//   • The sector — real nonprofit directory count + aggregate 990 revenue /
//                  assets from GET /api/stats (scoped to the active location).
//   • Grants     — navigation into the grants surfaces. We have no per-scope
//                  grant *count*, so these are honest links with NO number.
//
// CLAUDE.md (No Fabricated Data): a line item shows a figure ONLY when a real
// value backs it; otherwise it renders as a plain navigation row (chevron only).
// Government budget line items (taxes, bonds, contracts as aggregates) are not
// yet ingested, so we never invent them — the footer says so explicitly.

/** One real money-lens decision, normalized by the parent (StoryLenses). */
export interface MoneyDecision {
  /** headline */
  h: string
  /** jurisdiction label */
  juris: string
  /** decision drill-down url, e.g. /decisions/{id} */
  url?: string
  /** pre-formatted real dollar amount from the money lens "Amount" stat */
  amount?: string
}

interface MoneyLineItem {
  label: string
  /** optional muted sub-text rendered beneath the label */
  sub?: string
  /** real figure — rendered as a badge ONLY when present (never fabricated) */
  amount?: string
  to: string
}

/** One real top grant from GET /api/grants/top (pre-formatted server-side). */
interface TopGrant {
  grant_id?: string | null
  grantor_name?: string | null
  grantee_name?: string | null
  amount?: number | null
  /** pre-formatted dollar label, e.g. "$2.9M" — render as-is, never reformat */
  amount_label?: string | null
  jurisdiction_label?: string | null
  tax_year?: string | null
  /** drill-down url, e.g. /grants/{id} */
  url?: string | null
}

interface MoneyCard {
  name: string
  /** small uppercase mono label beneath the card name */
  monoLabel: string
  tagline: string
  /** drill-down target for the whole card header */
  to: string
  Icon: typeof ArrowTrendingUpIcon
  /** hex used for the top accent bar */
  accentBar: string
  /** tailwind classes for the accent text/border treatment on hover */
  accentBorderHover: string
  items: MoneyLineItem[]
  /** honest message when the card has no real rows for this scope/window */
  emptyNote?: string
}

export interface FollowTheMoneyProps {
  /**
   * Render inline (no full-bleed <section> chrome or oversized header) so the
   * section can be embedded inside another surface — e.g. the "Money Moves"
   * lens on the homepage. Defaults to the standalone, full-width section.
   */
  embedded?: boolean
  /** 2-letter state code for scoping the /stats query. */
  stateCode?: string
  /** City for scoping the /stats query. */
  city?: string
  /** When true, ignore stateCode/city and show a national view. */
  national?: boolean
  /** Real money-lens decision cards (already fetched by the parent). */
  moneyCards?: MoneyDecision[]
}

// Grants live in unified search under the `types` query param (see
// UnifiedSearch.tsx — it reads `searchParams.get('types')`).
const GRANTS_ROUTE = '/search?types=grants'

function AmountBadge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-100 px-2 py-0.5 text-[11px] font-bold tracking-wider text-emerald-700">
      {children}
    </span>
  )
}

function MoneyCardView({ card }: { card: MoneyCard }) {
  const { Icon } = card
  return (
    <div
      className={`group/card relative flex flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md ${card.accentBorderHover}`}
    >
      {/* Colored top accent bar */}
      <div className="h-1.5 w-full rounded-t-xl" style={{ backgroundColor: card.accentBar }} aria-hidden="true" />

      <div className="flex flex-1 flex-col p-5">
        {/* Card header — the whole header is a drill-down link */}
        <Link to={card.to} className="group/header flex items-start gap-3">
          <span className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-lg bg-gray-100">
            <Icon className="h-6 w-6 text-gray-600" aria-hidden="true" />
          </span>
          <span className="min-w-0 flex-1">
            <span
              className="block text-lg font-bold leading-tight text-[#16201d] group-hover/header:underline"
              style={{ fontFamily: "'Fraunces', serif" }}
            >
              {card.name}
            </span>
            <span className="mt-0.5 block font-mono text-[11px] font-semibold uppercase tracking-widest text-gray-400">
              {card.monoLabel}
            </span>
          </span>
          <ChevronRightIcon
            className="mt-1 h-5 w-5 flex-shrink-0 text-gray-300 transition-colors group-hover/header:text-gray-500"
            aria-hidden="true"
          />
        </Link>

        {/* One-line muted tagline */}
        <p className="mt-3 text-sm text-gray-500">{card.tagline}</p>

        <hr className="my-3 border-gray-100" />

        {/* Line items — each a drill-down link. A real figure shows as a badge;
            rows without a backing number show only a chevron (never a fake). */}
        {card.items.length > 0 ? (
          <ul className="-mx-2 flex flex-col">
            {card.items.map((item) => (
              <li key={item.label}>
                <Link
                  to={item.to}
                  className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-gray-50"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-[#16201d]">{item.label}</span>
                    {item.sub && <span className="mt-0.5 block truncate text-xs text-gray-400">{item.sub}</span>}
                  </span>
                  {item.amount ? (
                    <AmountBadge>{item.amount}</AmountBadge>
                  ) : (
                    <ChevronRightIcon className="h-4 w-4 flex-shrink-0 text-gray-300" aria-hidden="true" />
                  )}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-2 py-2 text-sm text-gray-400">{card.emptyNote ?? 'No data available yet.'}</p>
        )}
      </div>
    </div>
  )
}

export default function FollowTheMoney({
  embedded = false,
  stateCode,
  city,
  national = false,
  moneyCards = [],
}: FollowTheMoneyProps) {
  // National scope ignores any (possibly stale) city/state.
  const scopedState = national ? undefined : stateCode || undefined
  const scopedCity = national ? undefined : city || undefined

  // Real sector figures. /stats returns { success, data: {...} }.
  const { data: stats, isLoading } = useQuery({
    queryKey: ['stats', 'ftm', national, scopedState, scopedCity],
    queryFn: () =>
      api
        .get('/stats', { params: { state: scopedState, city: scopedCity } })
        .then((r) => (r.data?.data ?? null) as Record<string, unknown> | null),
    staleTime: 5 * 60 * 1000,
  })

  // Real top grants by dollar amount (scoped to the active location). The
  // /grants/top response carries the array at the top level: { grants: [...] }.
  const { data: topGrants } = useQuery({
    queryKey: ['grants-top', national, scopedState, scopedCity],
    queryFn: () =>
      api
        .get('/grants/top', { params: { state: scopedState, city: scopedCity, limit: 6 } })
        .then((r) => ((r.data?.grants ?? []) as TopGrant[])),
    staleTime: 5 * 60 * 1000,
  })

  const asNum = (v: unknown): number | null => {
    const n = typeof v === 'number' ? v : typeof v === 'string' ? Number(v) : NaN
    return Number.isFinite(n) ? n : null
  }
  const nonprofitN = stats ? asNum(stats.nonprofits) ?? asNum(stats.nonprofits_current) : null
  const revenue = stats ? asNum(stats.total_revenue) : null
  const assets = stats ? asNum(stats.total_assets) : null

  // Money out — real money-flagged decisions (top few with a dollar amount).
  const spendingItems: MoneyLineItem[] = moneyCards
    .filter((c) => c.amount)
    .slice(0, 4)
    .map((c) => ({ label: c.h, sub: c.juris, amount: c.amount, to: c.url || '/search?types=decisions' }))

  // The sector — only rows with a real value (count / 990 revenue / 990 assets).
  const sectorItems: MoneyLineItem[] = []
  if (nonprofitN && nonprofitN > 0) {
    sectorItems.push({
      label: 'Nonprofit directory',
      sub: `${formatNumber(nonprofitN)} organizations`,
      amount: formatNumber(nonprofitN),
      to: '/nonprofits',
    })
  }
  if (revenue && revenue > 0) {
    sectorItems.push({ label: '990 revenue', sub: 'aggregate filings', amount: formatCurrency(revenue), to: '/nonprofits' })
  }
  if (assets && assets > 0) {
    sectorItems.push({ label: '990 assets', sub: 'aggregate filings', amount: formatCurrency(assets), to: '/nonprofits' })
  }

  // Grants — real top 990 grants by dollar amount (scoped to the active
  // location), each drilling into /grants/{id}. amount_label is pre-formatted
  // server-side; render as-is. Rows without a real amount/url are dropped.
  const grantItems: MoneyLineItem[] = (topGrants ?? [])
    .filter((g) => g.amount_label && g.url)
    .slice(0, 4)
    .map((g) => ({
      label:
        g.grantor_name && g.grantee_name
          ? `${g.grantor_name} → ${g.grantee_name}`
          : g.grantee_name || g.grantor_name || 'Grant',
      sub: g.jurisdiction_label || g.grantor_name || undefined,
      amount: g.amount_label ?? undefined,
      to: g.url as string,
    }))

  const cards: MoneyCard[] = [
    {
      name: 'Money decisions',
      monoLabel: 'Money out',
      tagline: 'Real spending and contract votes from local meetings.',
      to: '/search?types=decisions',
      Icon: DocumentCurrencyDollarIcon,
      accentBar: '#ef4444',
      accentBorderHover: 'hover:border-rose-300',
      items: spendingItems,
      emptyNote: 'No money-flagged decisions in this view yet.',
    },
    {
      name: 'Nonprofit sector',
      monoLabel: 'The sector',
      tagline: 'The parallel civic ecosystem, from Form 990 filings.',
      to: '/nonprofits',
      Icon: HeartIcon,
      accentBar: '#a855f7',
      accentBorderHover: 'hover:border-violet-300',
      items: sectorItems,
      emptyNote: 'Sector figures load with a location.',
    },
    {
      name: 'Grants',
      monoLabel: 'Who funds whom',
      tagline: 'Federal, state, and 990 grant flows.',
      to: GRANTS_ROUTE,
      Icon: ArrowTrendingUpIcon,
      accentBar: '#10b981',
      accentBorderHover: 'hover:border-emerald-300',
      // Real top 990 grants by amount (nonprofit → recipient), scoped to the
      // active location. Header still drills to the grants search, which keeps
      // the Grants.gov opportunities tab.
      items: grantItems,
      emptyNote: 'No 990 grants in this view yet.',
    },
  ]

  // Header row. Embedded mode (inside the Money Moves lens) drops the oversized
  // title — the lens already names the section — keeping just the tagline and
  // the budget drill-down link.
  const header = (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {!embedded && (
          <h2 className="text-3xl font-bold text-[#0f2b2b] md:text-4xl" style={{ fontFamily: "'Fraunces', serif" }}>
            Follow the money
          </h2>
        )}
        <p className={`max-w-2xl text-sm text-gray-500 ${embedded ? '' : 'mt-2 md:text-base'}`}>
          Sorted by who&apos;s paying whom — so &ldquo;grant&rdquo; always has one clear home.
        </p>
      </div>

      <Link
        to="/analytics"
        className="inline-flex flex-shrink-0 items-center gap-2 self-start rounded-full border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:border-gray-400 hover:bg-gray-50 sm:self-auto"
      >
        <ArrowsRightLeftIcon className="h-4 w-4" aria-hidden="true" />
        Budget · how it connects
      </Link>
    </div>
  )

  const body = (
    <>
      {header}

      {/* Three drill-down cards */}
      {isLoading && !stats ? (
        <div className="grid gap-5 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-64 animate-pulse rounded-xl border border-gray-200 bg-gray-50" />
          ))}
        </div>
      ) : (
        <div className="grid gap-5 md:grid-cols-3">
          {cards.map((card) => (
            <MoneyCardView key={card.name} card={card} />
          ))}
        </div>
      )}

      {/* Footer — honest provenance note (what's live, what isn't yet ingested) */}
      <div className="mt-6 flex flex-col gap-3 rounded-xl border border-gray-200 bg-gray-50 px-5 py-3 text-sm text-gray-600 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-4">
        <span className="font-mono text-[11px] font-semibold uppercase tracking-widest text-gray-400">
          Live figures
        </span>
        <span>
          Money decisions and nonprofit 990 totals are read live from the civic warehouse. Government budget line
          items (taxes, bonds, line-item contracts) aren&apos;t ingested yet, so we show none rather than estimate.
        </span>
      </div>
    </>
  )

  // Embedded: a plain block that inherits the host surface's width/padding.
  if (embedded) {
    return (
      <div id="follow-the-money" className="scroll-mt-4">
        {body}
      </div>
    )
  }

  // Standalone: a full-bleed, padded homepage section.
  return (
    <section id="follow-the-money" className="bg-white px-4 py-16">
      <div className="mx-auto max-w-7xl">{body}</div>
    </section>
  )
}
