import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchPeriodCompare, type PeriodCompareResponse } from '../../api/topicTimeline'
import { niceMax, pctLabel, ppLabel, sortDumbbell, type DumbbellSort } from '../../utils/storyTimeline'
import { HOUSE_STYLE } from '../../utils/houseTheme'
import { DataTable } from '../matrix/SectionShell'
import { Tooltip, useTooltip } from '../matrix/Tooltip'
import usePrefersReducedMotion from '../../hooks/usePrefersReducedMotion'
import { useChartWidth } from './useChartWidth'
import './storyCharts.css'

const fmt = (n: number) => n.toLocaleString('en-US')
/** Rows drawn before "Show all". */
const FIRST_ROWS = 12

interface Props {
  topic: string
  stateCode?: string
  scopeLabel: string
  subject: string
  idBase: string
}

/**
 * Period dumbbell (#1140, the reference's §4.3): the topic's share of recorded meetings last year (hollow circle) and
 * this year (filled dot) for each state, or each town at state scope, with a ±pp change label. Sort by the later year,
 * by change or by the earlier year; rows slide to their new place (no motion with prefers-reduced-motion).
 */
export default function DumbbellChart({ topic, stateCode, scopeLabel, subject, idBase }: Props) {
  const q = useQuery<PeriodCompareResponse>({
    queryKey: ['topic-period-compare', topic, stateCode ?? 'national'],
    queryFn: () => fetchPeriodCompare(topic, stateCode),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const reduced = usePrefersReducedMotion()
  const { ref, width } = useChartWidth<HTMLDivElement>()
  const { bind, tip } = useTooltip()
  const [sortBy, setSortBy] = useState<DumbbellSort>('later')
  const [all, setAll] = useState(false)
  const [revealed, setRevealed] = useState(reduced)
  const [tableOpen, setTableOpen] = useState(false)
  const svgRef = useRef<SVGSVGElement>(null)
  const rows = useMemo(() => q.data?.rows ?? [], [q.data])
  const sorted = useMemo(() => sortDumbbell(rows, sortBy), [rows, sortBy])

  useEffect(() => {
    if (reduced) return setRevealed(true)
    const el = svgRef.current
    if (!el && q.isLoading) return // wait for the rows, so the reveal plays when they arrive
    if (!el || typeof IntersectionObserver === 'undefined') return setRevealed(true)
    const io = new IntersectionObserver((es) => es.some((e) => e.isIntersecting) && setRevealed(true), { threshold: 0.2 })
    io.observe(el)
    return () => io.disconnect()
  }, [reduced, rows.length, q.isLoading])

  // The section never disappears silently (#1192): loading, a failed request and a scope with nothing to compare each say so.
  const heading = (years: string) => (
    <p className="sc-h">
      Share of recorded meetings that discussed {subject}, {years} · {scopeLabel}
    </p>
  )
  if (q.isLoading) {
    return (
      <div className="sc-block">
        {heading('last year and this year')}
        <p className="sc-note" role="status">
          Loading the comparison…
        </p>
      </div>
    )
  }
  if (q.isError || !q.data) {
    return (
      <div className="sc-block">
        {heading('last year and this year')}
        <p className="sc-note">The year-over-year comparison could not be loaded right now.</p>
      </div>
    )
  }
  const d = q.data
  if (rows.length === 0 && d.hidden_rows === 0) {
    // No per-year counts of recorded meetings for the scope (recorded_meeting_year not loaded, #1194), or no meetings on
    // the topic in either year: there is no share to compare, and the chart says so instead of drawing nothing.
    return (
      <div className="sc-block">
        {heading(`${d.from_year} and ${d.to_year}`)}
        <p className="sc-note">
          No comparison to draw for {scopeLabel} yet: either no meetings on the topic are on record for {d.from_year} or{' '}
          {d.to_year}, or the yearly counts of recorded meetings per {d.grain === 'state' ? 'state' : 'town'} have not been loaded.
        </p>
      </div>
    )
  }
  if (rows.length === 0) {
    // Nothing clears the thresholds (often at state scope, where towns record few meetings a year): say so, never a blank.
    return d.hidden_rows > 0 ? (
      <div className="sc-block">
        <p className="sc-h">
          Share of recorded meetings that discussed {subject}, {d.from_year} and {d.to_year} · {scopeLabel}
        </p>
        <p className="sc-note">
          No {d.grain === 'state' ? 'state' : 'town'} here can be compared yet: {fmt(d.hidden_rows)}{' '}
          {d.grain === 'state' ? (d.hidden_rows === 1 ? 'state has' : 'states have') : d.hidden_rows === 1 ? 'town has' : 'towns have'} meetings on
          the topic, but none has at least {d.min_recorded_meetings} recorded meetings in both years and {d.min_topic_meetings} meetings on the
          topic across them.{d.grain === 'place' ? ' The national view compares states.' : ''}
        </p>
      </div>
    ) : null
  }
  const { from_year: y0, to_year: y1 } = d
  const visible = all ? sorted : sorted.slice(0, FIRST_ROWS)
  const visibleKeys = new Set(visible.map((r) => r.key))
  const rank = new Map(visible.map((r, i) => [r.key, i]))

  const w = Math.max(280, width)
  const stacked = w < 460
  const rowH = stacked ? 52 : 40
  const topPad = 28
  const labelW = stacked ? 0 : Math.min(190, w * 0.32)
  const deltaW = stacked ? 0 : 64
  const plotL = stacked ? 8 : labelW
  const plotR = stacked ? w - 12 : w - deltaW
  const xmaxShare = niceMax(Math.max(...rows.map((r) => Math.max(r.earlier_share, r.later_share))) * 100) / 100
  const xs = (v: number) => plotL + (v / xmaxShare) * (plotR - plotL)
  const h = topPad + visible.length * rowH + 30
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * xmaxShare)
  const place = d.grain === 'state' ? 'state' : 'town'

  return (
    <div className="sc-block">
      <p className="sc-h">
        Share of recorded meetings that discussed {subject}, {y0} and {y1}, by {place} · {scopeLabel}
      </p>
      <div className="sc-controls">
        <div className="folio-seg" role="group" aria-label="Sort the rows">
          {(
            [
              ['later', `By ${y1}`],
              ['change', 'By change'],
              ['earlier', `By ${y0}`],
            ] as Array<[DumbbellSort, string]>
          ).map(([k, label]) => (
            <button key={k} type="button" aria-pressed={sortBy === k} onClick={() => setSortBy(k)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <div ref={ref}>
        <svg ref={svgRef} className="sc-svg" viewBox={`0 0 ${w} ${h}`} role="group" aria-label={`Dumbbell chart, ${y0} against ${y1}, ${scopeLabel}`}>
          <circle cx={plotL + 5} cy={10} r={4.5} className="sc-dot-early" />
          <text className="sc-micro" x={plotL + 14} y={14}>
            {y0}
          </text>
          <circle cx={plotL + 60} cy={10} r={5} className="sc-dot-late" />
          <text className="sc-micro" x={plotL + 70} y={14}>
            {y1}
          </text>
          {ticks.map((t, i) => (
            <g key={i}>
              <line x1={xs(t)} x2={xs(t)} y1={topPad} y2={h - 24} stroke={t === 0 ? 'var(--ink)' : 'var(--rule)'} strokeWidth={t === 0 ? 1.5 : 1} />
              {(i % (plotR - plotL < 240 ? 2 : 1) === 0 || i === ticks.length - 1) && (
                <text className="sc-micro" x={xs(t)} y={h - 6} textAnchor="middle">
                  {pctLabel(t)}
                </text>
              )}
            </g>
          ))}
          {sorted.map((r, idx) => {
            if (!visibleKeys.has(r.key)) return null
            const y = topPad + (rank.get(r.key) ?? 0) * rowH
            const up = r.later_share >= r.earlier_share
            const trackY = stacked ? 34 : 20
            const textY = stacked ? 14 : 24
            const a = xs(r.earlier_share)
            const b = xs(r.later_share)
            const pp = ppLabel(r.earlier_share, r.later_share)
            const delay = reduced ? 0 : idx * 50
            const label = `${r.label}: ${y0} ${pctLabel(r.earlier_share)} (${fmt(r.earlier_meetings)} of ${fmt(r.earlier_recorded)} meetings), ${y1} ${pctLabel(r.later_share)} (${fmt(r.later_meetings)} of ${fmt(r.later_recorded)}), change ${pp.replace('pp', 'percentage points')}`
            return (
              <g
                key={r.key}
                className="sc-row"
                style={{ transform: `translate(0px, ${y}px)` }}
                tabIndex={0}
                role="img"
                aria-label={label}
                {...bind({
                  cat: r.label,
                  val: `${pctLabel(r.earlier_share)} → ${pctLabel(r.later_share)}`,
                  sub: `${fmt(r.earlier_meetings)} of ${fmt(r.earlier_recorded)} in ${y0}; ${fmt(r.later_meetings)} of ${fmt(r.later_recorded)} in ${y1} (${pp})`,
                })}
              >
                <rect className="sc-row-hit" x={0} y={0} width={w} height={rowH} fill="transparent" />
                <text className="sc-label" x={0} y={textY}>
                  {r.label}
                  {stacked ? `  ${pp}` : ''}
                </text>
                <line
                  className={`sc-bar ${up ? 'sc-up' : 'sc-down'}`}
                  x1={a}
                  x2={b}
                  y1={trackY}
                  y2={trackY}
                  style={{ transformOrigin: `${a}px ${trackY}px`, transform: revealed ? 'scaleX(1)' : 'scaleX(0)', transitionDelay: `${delay + 120}ms` }}
                />
                <circle className="sc-dot-early" cx={a} cy={trackY} r={5} style={{ opacity: revealed ? 1 : 0, transition: reduced ? undefined : `opacity 240ms ${delay}ms` }} />
                <circle className="sc-dot-late" cx={b} cy={trackY} r={6} style={{ opacity: revealed ? 1 : 0, transition: reduced ? undefined : `opacity 240ms ${delay + 360}ms` }} />
                {!stacked && (
                  <text className={up ? 'sc-delta-up' : 'sc-delta-down'} x={w} y={textY} textAnchor="end">
                    {pp}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      </div>
      {sorted.length > FIRST_ROWS && (
        <button type="button" className="folio-btn" onClick={() => setAll((v) => !v)}>
          {all ? `Show the first ${FIRST_ROWS}` : `Show all ${fmt(sorted.length)} ${place === 'state' ? 'states' : 'towns'}`}
        </button>
      )}
      <p className="sc-note">
        Each row divides meetings that discussed {subject} by every recorded meeting in that {place} and year. {y1} is the
        year so far. Rows with fewer than {d.min_recorded_meetings} recorded meetings in either year, or fewer than{' '}
        {d.min_topic_meetings} meetings on the topic across both, are left out
        {d.hidden_rows > 0 ? ` (${fmt(d.hidden_rows)} ${d.hidden_rows === 1 ? place : `${place === 'state' ? 'states' : 'towns'}`})` : ''}.
      </p>
      <button type="button" className="folio-btn" aria-expanded={tableOpen} aria-controls={`${idBase}-db-table`} onClick={() => setTableOpen((o) => !o)}>
        {tableOpen ? 'Hide data table' : 'Show data table'} {tableOpen ? '↑' : '↓'}
      </button>
      {tableOpen && (
        <DataTable
          id={`${idBase}-db-table`}
          caption={`Data table: share of recorded meetings that discussed ${subject}, ${y0} and ${y1}, ${scopeLabel}`}
          spec={{
            columns: [
              { label: place === 'state' ? 'State' : 'Town' },
              { label: `${y0} (%)`, numeric: true },
              { label: `${y1} (%)`, numeric: true },
              { label: 'Change (pp)', numeric: true },
              { label: `Meetings ${y0} / ${y1}`, numeric: true },
            ],
            rows: sorted.map((r) => [
              r.label,
              pctLabel(r.earlier_share),
              pctLabel(r.later_share),
              ppLabel(r.earlier_share, r.later_share),
              `${fmt(r.earlier_meetings)} of ${fmt(r.earlier_recorded)} / ${fmt(r.later_meetings)} of ${fmt(r.later_recorded)}`,
            ]),
          }}
        />
      )}
      {typeof document !== 'undefined' && createPortal(<div className="folio" style={HOUSE_STYLE}><Tooltip tip={tip} /></div>, document.body)}
    </div>
  )
}
