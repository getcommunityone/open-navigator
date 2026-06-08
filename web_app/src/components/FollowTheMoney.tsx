import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { sankey as d3Sankey, sankeyLinkHorizontal } from 'd3-sankey'
import api from '../lib/api'

// "Follow the money" — a tabbed Sankey flow hero (Money Moves lens on the
// homepage). Three lenses, ALL traced to the warehouse via GET /api/money-flow:
//   spending (real money decisions) · grants (990 Schedule I) · economy (real
//   nonprofit revenue decomposition). No fabricated numbers: a lens with no real
//   data renders an honest empty state; we never draw an invented diagram.

interface FlowMeta {
  title: string
  subtitle?: string | null
  url?: string | null
  source_label?: string | null
}
interface FlowNode {
  name: string
  /** Per-node drill-down target (grantor or grantee). null = not clickable. */
  url?: string | null
}
interface FlowLink {
  source: number
  target: number
  value: number
  value_label: string
  meta: FlowMeta
}
interface FlowLens {
  accent: string
  head_amount: string
  head_label: string
  /** Aggregate drill-down for the headline figure (decisions / grants / nonprofits). */
  head_url?: string | null
  count_label: string
  nodes: FlowNode[]
  links: FlowLink[]
  placeholder: boolean
}
interface MoneyFlowResp {
  location_label: string
  lenses: { spending: FlowLens; grants: FlowLens; economy: FlowLens }
}

export interface FollowTheMoneyProps {
  embedded?: boolean
  stateCode?: string
  city?: string
  national?: boolean
}

type LensKey = 'spending' | 'grants' | 'economy'
const TABS: { key: LensKey; label: string }[] = [
  { key: 'spending', label: 'Public spending' },
  { key: 'grants', label: 'Grants' },
  { key: 'economy', label: 'Nonprofit economy' },
]

const W = 800
const H = 300

// d3-sankey node/link after layout (geometry attached to copies of our data).
type LaidNode = FlowNode & { x0: number; x1: number; y0: number; y1: number; value: number }
type LaidLink = Omit<FlowLink, 'source' | 'target'> & {
  source: LaidNode
  target: LaidNode
  width: number
}

const trunc = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

interface TipState {
  x: number
  y: number
  meta: FlowMeta
  valueLabel: string
  accent: string
}

export default function FollowTheMoney({
  embedded = false,
  stateCode,
  city,
  national = false,
}: FollowTheMoneyProps) {
  const navigate = useNavigate()
  const [tab, setTab] = useState<LensKey>('spending')
  const [tip, setTip] = useState<TipState | null>(null)

  const scopedState = national ? undefined : stateCode || undefined
  const scopedCity = national ? undefined : city || undefined

  const { data, isLoading, isError } = useQuery({
    queryKey: ['money-flow', national, scopedState, scopedCity],
    queryFn: () =>
      api
        .get('/money-flow', { params: { state: scopedState, city: scopedCity } })
        .then((r) => r.data as MoneyFlowResp),
    staleTime: 5 * 60 * 1000,
  })

  const lens = data?.lenses[tab]
  const accent = lens?.accent || '#0d9488'

  // Compute the Sankey layout for the active lens (only when it has real links).
  const laid = useMemo(() => {
    if (!lens || lens.placeholder || lens.links.length === 0) return null
    try {
      const layout = d3Sankey<LaidNode, LaidLink>()
        .nodeWidth(11)
        .nodePadding(22)
        .extent([
          // Match the left gutter (175px) to the right so long left-side names
          // (grantors like "AUBURN UNIVERSITY FOUNDATION") render right-anchored
          // without overflowing the SVG's left edge and clipping ("…UNIVERSITY").
          [175, 14],
          // Pull the right edge well in (175px gutter) so the two-line target
          // labels — name + dollar value — always fit inside the viewBox and
          // never clip at the SVG edge the way a single concatenated line did.
          [W - 175, H - 14],
        ])
      const graph = layout({
        nodes: lens.nodes.map((n) => ({ ...n })) as LaidNode[],
        links: lens.links.map((l) => ({ ...l })) as unknown as LaidLink[],
      })
      const linkPath = sankeyLinkHorizontal<LaidNode, LaidLink>()
      return {
        nodes: graph.nodes as LaidNode[],
        links: (graph.links as LaidLink[]).map((l) => ({ link: l, d: linkPath(l) || '' })),
      }
    } catch {
      return null
    }
  }, [lens])

  const onSvgLeave = () => setTip(null)
  const onLinkMove = (e: React.MouseEvent, l: LaidLink) =>
    setTip({ x: e.clientX, y: e.clientY, meta: l.meta, valueLabel: l.value_label, accent })
  const onLinkClick = (l: LaidLink) => {
    if (l.meta.url) navigate(l.meta.url)
  }

  const header = (
    <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {!embedded && (
          <h2 className="text-3xl font-bold text-[#0f2b2b] md:text-4xl" style={{ fontFamily: "'Fraunces', serif" }}>
            Follow the money
          </h2>
        )}
        <p className={`max-w-2xl text-sm text-gray-500 ${embedded ? '' : 'mt-2 md:text-base'}`}>
          Public money and grants flow from funders into projects, nonprofits, and vendors —{' '}
          {data?.location_label ? (
            <span className="font-medium text-gray-700">{data.location_label}</span>
          ) : (
            'one flow'
          )}
          , three lenses.
        </p>
      </div>
    </div>
  )

  const body = (
    <>
      {header}
      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white">
        <div className="h-1 w-full transition-colors" style={{ background: accent }} />
        {/* tabs */}
        <div className="flex gap-1 border-b border-gray-200 px-4 pt-3">
          {TABS.map((t) => {
            const on = t.key === tab
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => setTab(t.key)}
                className={`-mb-px border-b-2 px-3 pb-3 pt-2 text-sm font-semibold transition-colors ${
                  on ? 'text-[#0f2b2b]' : 'border-transparent text-gray-400 hover:text-gray-700'
                }`}
                style={on ? { borderColor: accent } : undefined}
              >
                {t.label}
              </button>
            )
          })}
        </div>

        {/* flow header */}
        <div className="flex items-baseline justify-between gap-3 px-5 pb-1 pt-3">
          <div className="text-[13px] text-gray-500">
            {lens && !lens.placeholder ? (
              lens.head_url ? (
                <button
                  type="button"
                  onClick={() => navigate(lens.head_url!)}
                  title="See the full breakdown"
                  className="group inline-flex items-baseline gap-1 text-left text-gray-500 transition-colors hover:text-gray-800"
                >
                  <b className="text-[15px] font-bold text-[#0f2b2b] group-hover:underline">{lens.head_amount}</b>
                  <span>{lens.head_label}</span>
                  <span aria-hidden className="text-gray-400 transition-transform group-hover:translate-x-0.5">
                    &rarr;
                  </span>
                </button>
              ) : (
                <>
                  <b className="text-[15px] font-bold text-[#0f2b2b]">{lens.head_amount}</b> {lens.head_label}
                </>
              )
            ) : (
              <span className="text-gray-400">—</span>
            )}
          </div>
          <div className="font-mono text-[11.5px] text-gray-400">{lens?.count_label}</div>
        </div>

        {/* flow area */}
        <div className="px-3 pb-4 pt-1">
          {isLoading ? (
            <div className="h-[260px] animate-pulse rounded-xl bg-gray-50" />
          ) : isError ? (
            <div className="flex h-[200px] items-center justify-center rounded-xl border border-dashed border-gray-200 px-6 text-center text-sm text-gray-400">
              Couldn&rsquo;t load the money flow right now.{' '}
              <b className="ml-1 text-gray-600">Please try again.</b>
            </div>
          ) : !laid ? (
            <div className="flex h-[200px] items-center justify-center rounded-xl border border-dashed border-gray-200 px-6 text-center text-sm text-gray-400">
              No {TABS.find((t) => t.key === tab)?.label.toLowerCase()} flows available for this area yet.
            </div>
          ) : (
            <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Money flow Sankey diagram">
              {laid.links.map(({ link, d }, i) => (
                <path
                  key={i}
                  d={d}
                  fill="none"
                  stroke={accent}
                  strokeOpacity={0.32}
                  strokeWidth={Math.max(2, link.width)}
                  style={{ cursor: link.meta.url ? 'pointer' : 'default' }}
                  onMouseMove={(e) => onLinkMove(e, link)}
                  onMouseLeave={onSvgLeave}
                  onClick={() => onLinkClick(link)}
                />
              ))}
              {laid.nodes.map((n, i) => {
                const leftSide = n.x0 < W / 2
                const isSource = i === 0 && tab !== 'grants'
                // Right-side (target) nodes drill down via their feeding link —
                // works on all three lenses (decision / grantee / revenue split).
                const feed = leftSide ? undefined : lensTargetLink(lens, n)
                const clickable = !!feed?.meta.url
                const labelX = leftSide ? n.x0 - 8 : n.x1 + 8
                const cy = (n.y0 + n.y1) / 2
                return (
                  <g
                    key={i}
                    style={{ cursor: clickable ? 'pointer' : 'default' }}
                    onMouseMove={
                      feed
                        ? (e) =>
                            setTip({
                              x: e.clientX,
                              y: e.clientY,
                              meta: feed.meta,
                              valueLabel: feed.value_label,
                              accent,
                            })
                        : undefined
                    }
                    onMouseLeave={feed ? onSvgLeave : undefined}
                    onClick={clickable ? () => navigate(feed!.meta.url!) : undefined}
                  >
                    <rect
                      x={n.x0}
                      y={n.y0}
                      width={n.x1 - n.x0}
                      height={Math.max(2, n.y1 - n.y0)}
                      rx={2}
                      fill={isSource ? '#44403c' : tab === 'economy' ? '#a78bfa' : '#78716c'}
                    />
                    {leftSide ? (
                      <text
                        x={labelX}
                        y={cy}
                        dy="0.32em"
                        textAnchor="end"
                        fontSize={12}
                        fill="#44403c"
                        style={{ fontFamily: "'DM Sans', sans-serif" }}
                      >
                        {trunc(n.name, 24)}
                      </text>
                    ) : (
                      // Two lines: name on top, the dollar value beneath in the
                      // lens accent. Splitting them keeps the value on-screen
                      // instead of being clipped off the right edge.
                      <text x={labelX} y={cy} textAnchor="start" style={{ fontFamily: "'DM Sans', sans-serif" }}>
                        <tspan x={labelX} dy="-0.25em" fontSize={12} fontWeight={600} fill="#44403c">
                          {trunc(n.name, 22)}
                        </tspan>
                        <tspan
                          x={labelX}
                          dy="1.25em"
                          fontSize={11}
                          fontWeight={700}
                          fill={accent}
                          style={{ fontFamily: "'DM Mono', ui-monospace, monospace" }}
                        >
                          {feed?.value_label || lensValueLabel(lens, n)}
                        </tspan>
                      </text>
                    )}
                  </g>
                )
              })}
            </svg>
          )}
        </div>
      </div>

      <p className="mt-3 text-[12.5px] leading-relaxed text-gray-500">
        Live from the warehouse — spending is real money-flagged decisions, grants are 990 Schedule I
        flows, and the nonprofit-economy tab is a real decomposition of sector revenue (a snapshot drawn
        as a flow), not invented funder&rarr;grantee edges.
      </p>

      {tip && (
        <div
          className="pointer-events-none fixed z-20 max-w-[260px] rounded-lg bg-[#1c1917] px-3 py-2 text-xs leading-snug text-white shadow-lg"
          style={{ left: tip.x + 14, top: tip.y + 14 }}
        >
          <div className="font-semibold">{tip.meta.title}</div>
          {tip.meta.subtitle && <div className="mt-0.5 text-[11px] text-stone-300">{tip.meta.subtitle}</div>}
          <div className="mt-1 flex items-center gap-1.5 font-mono text-[10.5px]">
            <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: tip.accent }} />
            {tip.valueLabel}
            {tip.meta.source_label ? ` · ${tip.meta.source_label}` : ''}
          </div>
        </div>
      )}
    </>
  )

  if (embedded) {
    return (
      <div id="follow-the-money" className="scroll-mt-4">
        {body}
      </div>
    )
  }
  return (
    <section id="follow-the-money" className="bg-white px-4 py-16">
      <div className="mx-auto max-w-4xl">{body}</div>
    </section>
  )
}

// The link that feeds a right-side (target) node — its meta.url is the
// drill-down target and its value_label is the node's pre-formatted amount.
function lensTargetLink(lens: FlowLens | undefined, node: LaidNode): FlowLink | undefined {
  if (!lens) return undefined
  const idx = lens.nodes.findIndex((n) => n.name === node.name)
  return lens.links.find((l) => l.target === idx)
}

// Right-side node value label: reuse the feeding link's pre-formatted
// value_label (never re-format numbers on the client).
function lensValueLabel(lens: FlowLens | undefined, node: LaidNode): string {
  return lensTargetLink(lens, node)?.value_label || ''
}
