import { Link } from 'react-router-dom'
import {
  ArrowTrendingUpIcon,
  DocumentCurrencyDollarIcon,
  HeartIcon,
  ArrowsRightLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline'

// "Follow the money" homepage section.
//
// Three drill-down cards (Revenue / Spending / Nonprofits) that frame civic
// finance by *who is paying whom*, so a "grant" always resolves to one clear
// destination. Both each card header and every line item are independent
// drill-down links into the app's analytics / nonprofits / search surfaces.

type BadgeTone = 'live' | 'recent' | 'fy' | 'count'

interface MoneyLineItem {
  label: string
  /** optional muted sub-text rendered beneath the label */
  sub?: string
  badge: string
  tone: BadgeTone
  to: string
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
}

export interface FollowTheMoneyProps {
  /** Pre-formatted nonprofit directory count (e.g. "43,726"). */
  nonprofitCount?: string
}

// Grants live in unified search under the `types` query param (see
// UnifiedSearch.tsx — it reads `searchParams.get('types')`). We route all
// "grant" line items there so the section's thesis (one clear home for a
// grant) holds.
const GRANTS_ROUTE = '/search?types=grants'

const BADGE_TONE_CLASSES: Record<BadgeTone, string> = {
  live: 'bg-emerald-100 text-emerald-700 border border-emerald-200',
  recent: 'bg-amber-100 text-amber-700 border border-amber-200',
  fy: 'bg-slate-100 text-slate-600 border border-slate-200',
  count: 'bg-violet-100 text-violet-700 border border-violet-200',
}

function StatusBadge({ children, tone }: { children: React.ReactNode; tone: BadgeTone }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider ${BADGE_TONE_CLASSES[tone]}`}
    >
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
      <div
        className="h-1.5 w-full rounded-t-xl"
        style={{ backgroundColor: card.accentBar }}
        aria-hidden="true"
      />

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
            <span className="mt-0.5 block text-[11px] font-semibold uppercase tracking-widest text-gray-400 font-mono">
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

        {/* Line items — each is its own drill-down link */}
        <ul className="-mx-2 flex flex-col">
          {card.items.map((item) => (
            <li key={item.label}>
              <Link
                to={item.to}
                className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-gray-50"
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-[#16201d]">{item.label}</span>
                  {item.sub && (
                    <span className="mt-0.5 block text-xs text-gray-400">{item.sub}</span>
                  )}
                </span>
                <StatusBadge tone={item.tone}>{item.badge}</StatusBadge>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default function FollowTheMoney({ nonprofitCount = '43,726' }: FollowTheMoneyProps) {
  const cards: MoneyCard[] = [
    {
      name: 'Revenue',
      monoLabel: 'Money in',
      tagline: 'Where the money comes from.',
      to: '/analytics',
      Icon: ArrowTrendingUpIcon,
      accentBar: '#10b981',
      accentBorderHover: 'hover:border-emerald-300',
      items: [
        { label: 'Taxes & fees', badge: 'FY2024', tone: 'fy', to: '/analytics' },
        {
          label: 'Grants received',
          sub: 'fed / state · ARPA',
          badge: 'Recent',
          tone: 'recent',
          to: GRANTS_ROUTE,
        },
        { label: 'Bonds & debt', badge: 'Recent', tone: 'recent', to: '/analytics' },
      ],
    },
    {
      name: 'Spending',
      monoLabel: 'Money out',
      tagline: 'Where it goes.',
      to: '/analytics',
      Icon: DocumentCurrencyDollarIcon,
      accentBar: '#ef4444',
      accentBorderHover: 'hover:border-rose-300',
      items: [
        { label: 'Contracts & vendors', badge: 'Live', tone: 'live', to: '/analytics' },
        { label: 'Capital projects (CIP)', badge: 'Recent', tone: 'recent', to: '/analytics' },
        {
          label: 'Grants awarded',
          sub: 'to orgs & nonprofits',
          badge: 'Live',
          tone: 'live',
          to: GRANTS_ROUTE,
        },
      ],
    },
    {
      name: 'Nonprofits',
      monoLabel: 'The sector',
      tagline: 'The parallel ecosystem.',
      to: '/nonprofits',
      Icon: HeartIcon,
      accentBar: '#a855f7',
      accentBorderHover: 'hover:border-violet-300',
      items: [
        {
          label: 'Directory',
          sub: `${nonprofitCount} organizations`,
          badge: nonprofitCount,
          tone: 'count',
          to: '/nonprofits',
        },
        { label: '990 finances', badge: 'FY2024', tone: 'fy', to: '/nonprofits' },
        {
          label: 'Grants received',
          sub: 'from government',
          badge: 'Recent',
          tone: 'recent',
          to: GRANTS_ROUTE,
        },
      ],
    },
  ]

  return (
    <section id="follow-the-money" className="bg-white py-16 px-4">
      <div className="mx-auto max-w-7xl">
        {/* Section header row */}
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2
              className="text-3xl font-bold text-[#0f2b2b] md:text-4xl"
              style={{ fontFamily: "'Fraunces', serif" }}
            >
              Follow the money
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-gray-500 md:text-base">
              Sorted by who's paying whom — so &ldquo;grant&rdquo; always has one clear home.
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

        {/* Three drill-down cards */}
        <div className="grid gap-5 md:grid-cols-3">
          {cards.map((card) => (
            <MoneyCardView key={card.name} card={card} />
          ))}
        </div>

        {/* Footer legend bar — the connection key */}
        <div className="mt-6 flex flex-col gap-3 rounded-xl border border-gray-200 bg-gray-50 px-5 py-3 text-sm text-gray-600 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-4">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-gray-400 font-mono">
            A grant goes →
          </span>
          <span className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <span>
              received → <span className="font-bold text-emerald-600">Revenue</span>
            </span>
            <span aria-hidden="true" className="text-gray-300">
              ·
            </span>
            <span>
              awarded → <span className="font-bold text-rose-600">Spending</span>
            </span>
            <span aria-hidden="true" className="text-gray-300">
              ·
            </span>
            <span>
              org&apos;s full picture → <span className="font-bold text-violet-600">Nonprofits</span>
            </span>
          </span>
        </div>
      </div>
    </section>
  )
}
