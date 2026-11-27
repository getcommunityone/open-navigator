import { useState } from 'react'
import { createPortal } from 'react-dom'
import { niceMax, pctLabel } from '../../utils/storyTimeline'
import { pickAxisTicks } from '../../utils/axisTicks'
import { HOUSE_STYLE } from '../../utils/houseTheme'
import { Tooltip, useTooltip } from '../matrix/Tooltip'
import { revealDelayMs } from '../../utils/folioMotion'
import { labelWidth, placeValueLabels, wrapLabel } from '../../utils/dumbbellLabels'
import { useChartReveal } from './useChartReveal'
import { useChartWidth } from './useChartWidth'
import './storyCharts.css'

export interface DumbbellRow {
  key: string
  label: string
  /** The hollow dot (the earlier or comparison value, 0–1); null draws a single filled dot on a stem from zero. */
  a: number | null
  /** The filled dot (the later or local value, 0–1). */
  b: number
  /** The right-hand column ("+3.2 pp", or the share itself on a single-value row) and whether it is a fall. */
  right: string
  negative?: boolean
  /** What a screen reader hears for the row. */
  ariaLabel: string
  tip: { cat: string; val: string; sub?: string }
}

interface Props {
  /** Rows in the order to draw them; a new order slides the rows to their place. */
  rows: DumbbellRow[]
  /** Legend names for the hollow and filled dots; aName is left out when no row has an `a`. */
  aName?: string
  bName: string
  ariaLabel: string
  /** Rows drawn before "Show all"; the button names `unitPlural`. */
  firstRows?: number
  unitPlural: string
  /** A new value (the scope) replays the entrance; a re-sort with the same key only slides the rows. */
  replayKey?: unknown
}

const fmt = (n: number) => n.toLocaleString('en-US')
/** Below this chart width the rows go compact (#1264); the timeline's milestone track uses the same breakpoint. */
const COMPACT_W = 560

/**
 * The presentational dumbbell (#1140, generalised in #1209): one row per item, hollow dot = `a`, filled dot = `b`, joined
 * by a line, the change right-aligned (warning colour when it falls), a % axis with light gridlines. On a phone (#1264) each
 * row is compact: label and change on one line, then a light track with each value printed over its dot, and no axis. Keyboard focus and a
 * tooltip per row. The entrance (#1228) plays when the chart scrolls into view (`useChartReveal`), and a re-sort slides the rows;
 * both are off under prefers-reduced-motion, which draws the final state. Used by the places dumbbell
 * (`DumbbellChart`) (the Concerns screen used `ConcernsDumbbell`, removed in #1289).
 */
export default function DumbbellRows({ rows, aName, bName, ariaLabel, firstRows = 12, unitPlural, replayKey }: Props) {
  const { ref: revealRef, revealed, reduced } = useChartReveal<SVGSVGElement>(replayKey)
  const { ref, width } = useChartWidth<HTMLDivElement>()
  const { bind, tip } = useTooltip()
  const [all, setAll] = useState(false)

  if (rows.length === 0) return null
  const single = rows.every((r) => r.a == null)
  const visible = all ? rows : rows.slice(0, firstRows)
  const rank = new Map(visible.map((r, i) => [r.key, i]))

  const w = Math.max(280, width)
  // Phone (#1264): compact rows. Label and change on one line, then a light track with each value printed over its dot;
  // no axis, gridlines or scale row. Desktop keeps the label column, the % axis and the change column.
  const compact = w < COMPACT_W
  const topPad = compact ? 26 : 28
  const labelW = compact ? 0 : Math.min(190, w * 0.32)
  const deltaW = compact ? 0 : 72
  const plotL = compact ? 8 : labelW
  const plotR = compact ? w - 8 : w - deltaW
  const xmax = niceMax(Math.max(...rows.map((r) => Math.max(r.a ?? 0, r.b))) * 100) / 100
  const xs = (v: number) => plotL + (v / xmax) * (plotR - plotL)
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * xmax)
  // The % labels by the room they have (the same rule as the year axes), first and last always, never overlapping.
  const tickShown = new Set(pickAxisTicks(ticks.length, (plotR - plotL) / (ticks.length - 1), Math.max(...ticks.map((t) => pctLabel(t).length))))
  const bLegendX = single || !aName ? plotL + 5 : plotL + 14 + aName.length * 6.6 + 16

  // Compact layout, worked out for every visible row first, so all rows share one height.
  // (Label widths are estimates: ~6.9px a character for the 12px label, ~7.5px for the change.)
  const plan = new Map(
    (compact ? visible : []).map((r) => {
      const a = r.a == null ? null : { x: xs(r.a), width: labelWidth(pctLabel(r.a)) }
      const b = { x: xs(r.b), width: labelWidth(pctLabel(r.b)) }
      const right = single ? '' : r.right
      const lines = wrapLabel(r.label, Math.max(8, Math.floor((w - right.length * 7.5 - 14) / 6.9)))
      return [r.key, { lines, right, values: placeValueLabels(a, b, 0, w, 8) }] as const
    }),
  )
  const twoLines = compact && [...plan.values()].some((p) => p.lines.length > 1)
  const anyBelow = compact && [...plan.values()].some((p) => p.values.a?.below)
  const rowH = compact ? (twoLines ? 72 : 64) + (anyBelow ? 12 : 0) : 40
  const trackY = compact ? (twoLines ? 58 : 50) : 20
  const textY = compact ? 15 : 24
  const h = topPad + visible.length * rowH + (compact ? 4 : 30)

  return (
    <>
      <div ref={ref}>
        <svg ref={revealRef} className={`sc-svg${compact ? ' sc-dumbbell-compact' : ''}`} viewBox={`0 0 ${w} ${h}`} role="group" aria-label={ariaLabel}>
          {!single && aName && (
            <>
              <circle cx={plotL + 5} cy={10} r={4.5} className="sc-dot-early" />
              <text className="sc-micro" x={plotL + 14} y={14}>
                {aName}
              </text>
            </>
          )}
          <circle cx={bLegendX} cy={10} r={5} className="sc-dot-late" />
          <text className="sc-micro" x={bLegendX + 10} y={14}>
            {bName}
          </text>
          {!compact &&
            ticks.map((t, i) => (
              <g key={i}>
                <line x1={xs(t)} x2={xs(t)} y1={topPad} y2={h - 24} stroke={t === 0 ? 'var(--ink)' : 'var(--rule)'} strokeWidth={t === 0 ? 1.5 : 1} />
                {tickShown.has(i) && (
                  <text className="sc-micro" x={xs(t)} y={h - 6} textAnchor="middle">
                    {pctLabel(t)}
                  </text>
                )}
              </g>
            ))}
          {rows.map((r) => {
            const at = rank.get(r.key)
            const p = plan.get(r.key)
            if (at == null) return null
            const y = topPad + at * rowH
            const a = xs(r.a ?? 0)
            const b = xs(r.b)
            // The reference's entrance (§4.3), row by row: the hollow dot appears, the line grows from it and the filled dot
            // rides its end to the value; then the change. Rows keep their delay by rank, so a re-sort only slides them.
            // Compact rows fade each value in as its dot lands.
            const d = reduced ? 0 : 140 + revealDelayMs(at, visible.length)
            const delay = (ms: number) => (reduced ? undefined : `${ms}ms`)
            const fade = (ms: number) => ({ opacity: revealed ? 1 : 0, transitionDelay: delay(ms) })
            const tone = r.negative ? 'sc-down' : 'sc-up'
            return (
              <g key={r.key} className="sc-row" style={{ transform: `translate(0px, ${y}px)` }} tabIndex={0} role="img" aria-label={r.ariaLabel} {...bind(r.tip)}>
                <rect className="sc-row-hit" x={0} y={0} width={w} height={rowH} fill="transparent" />
                {compact && p ? (
                  p.lines.map((line, i) => (
                    <text key={i} className="sc-label" x={0} y={textY + i * 15}>
                      {line}
                    </text>
                  ))
                ) : (
                  <text className="sc-label" x={0} y={textY}>
                    {r.label}
                  </text>
                )}
                {compact && <line className="sc-track" x1={plotL} x2={plotR} y1={trackY} y2={trackY} />}
                <line
                  className={`sc-bar ${compact ? tone : single ? 'sc-stem' : tone}`}
                  x1={a}
                  x2={b}
                  y1={trackY}
                  y2={trackY}
                  style={{ transformOrigin: `${a}px ${trackY}px`, transform: revealed ? 'scaleX(1)' : 'scaleX(0)', transitionDelay: delay(d + 120) }}
                />
                {r.a != null && (
                  <circle
                    className="sc-dot-early sc-pop"
                    cx={a}
                    cy={trackY}
                    r={5}
                    style={{ opacity: revealed ? 1 : 0, transform: revealed ? 'scale(1)' : 'scale(0.3)', transitionDelay: delay(d) }}
                  />
                )}
                <circle
                  className="sc-dot-late sc-ride"
                  cx={b}
                  cy={trackY}
                  r={6}
                  style={{ opacity: revealed ? 1 : 0, transform: revealed ? 'translateX(0px)' : `translateX(${(a - b).toFixed(1)}px)`, transitionDelay: delay(d + 120) }}
                />
                {compact && p && r.a != null && p.values.a && (
                  <text className="sc-micro sc-fade sc-val-a" x={p.values.a.x} y={p.values.a.below ? trackY + 19 : trackY - 11} textAnchor="middle" style={fade(d + 200)}>
                    {pctLabel(r.a)}
                  </text>
                )}
                {compact && p && (
                  <text className="sc-micro sc-fade sc-val-b" x={p.values.b.x} y={trackY - 11} textAnchor="middle" style={fade(d + 640)}>
                    {pctLabel(r.b)}
                  </text>
                )}
                {(!compact || p?.right) && (
                  <text
                    className={`sc-fade ${single ? 'sc-delta-flat' : r.negative ? 'sc-delta-down' : 'sc-delta-up'}`}
                    x={w}
                    y={textY}
                    textAnchor="end"
                    style={fade(d + 600)}
                  >
                    {r.right}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      </div>
      {rows.length > firstRows && (
        <button type="button" className="folio-btn" onClick={() => setAll((v) => !v)}>
          {all ? `Show the first ${firstRows}` : `Show all ${fmt(rows.length)} ${unitPlural}`}
        </button>
      )}
      {typeof document !== 'undefined' && createPortal(<div className="folio" style={HOUSE_STYLE}><Tooltip tip={tip} /></div>, document.body)}
    </>
  )
}
