import { useState } from 'react'
import { createPortal } from 'react-dom'
import { niceMax, pctLabel } from '../../utils/storyTimeline'
import { HOUSE_STYLE } from '../../utils/houseTheme'
import { Tooltip, useTooltip } from '../matrix/Tooltip'
import { revealDelayMs } from '../../utils/folioMotion'
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

/**
 * The presentational dumbbell (#1140, generalised in #1209): one row per item, hollow dot = `a`, filled dot = `b`, joined
 * by a line, the change right-aligned (warning colour when it falls), a % axis with light gridlines. Keyboard focus and a
 * tooltip per row. The entrance (#1228) plays when the chart scrolls into view (`useChartReveal`), and a re-sort slides the rows;
 * both are off under prefers-reduced-motion, which draws the final state. Used by the places dumbbell
 * (`DumbbellChart`) and the Concerns screen (`ConcernsDumbbell`).
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
  // Phone: the label and the change share a line above the track, so the plot spans the whole width.
  const stacked = w < 460
  const rowH = stacked ? 52 : 40
  const topPad = 28
  const labelW = stacked ? 0 : Math.min(190, w * 0.32)
  const deltaW = stacked ? 0 : 72
  // Stacked (phone): room at both ends so the first and last axis labels are not clipped.
  const plotL = stacked ? 22 : labelW
  const plotR = stacked ? w - 26 : w - deltaW
  const xmax = niceMax(Math.max(...rows.map((r) => Math.max(r.a ?? 0, r.b))) * 100) / 100
  const xs = (v: number) => plotL + (v / xmax) * (plotR - plotL)
  const h = topPad + visible.length * rowH + 30
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * xmax)
  const bLegendX = single || !aName ? plotL + 5 : plotL + 14 + aName.length * 6.6 + 16
  const trackY = stacked ? 34 : 20
  const textY = stacked ? 14 : 24
  const tickLine = (t: number) => ({ stroke: t === 0 ? 'var(--ink)' : 'var(--rule)', strokeWidth: t === 0 ? 1.5 : 1 })

  return (
    <>
      <div ref={ref}>
        <svg ref={revealRef} className="sc-svg" viewBox={`0 0 ${w} ${h}`} role="group" aria-label={ariaLabel}>
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
          {ticks.map((t, i) => (
            <g key={i}>
              {/* Stacked, each row draws its own short gridlines around the track, so no line crosses a label. */}
              {!stacked && <line x1={xs(t)} x2={xs(t)} y1={topPad} y2={h - 24} {...tickLine(t)} />}
              {(i % (plotR - plotL < 240 ? 2 : 1) === 0 || i === ticks.length - 1) && (
                <text className="sc-micro" x={xs(t)} y={h - 6} textAnchor="middle">
                  {pctLabel(t)}
                </text>
              )}
            </g>
          ))}
          {rows.map((r) => {
            const at = rank.get(r.key)
            if (at == null) return null
            const y = topPad + at * rowH
            const a = xs(r.a ?? 0)
            const b = xs(r.b)
            // The reference's entrance (§4.3), row by row: the hollow dot appears, the line grows from it and the filled dot
            // rides its end to the value; then the change. Rows keep their delay by rank, so a re-sort only slides them.
            const d = reduced ? 0 : 140 + revealDelayMs(at, visible.length)
            const delay = (ms: number) => (reduced ? undefined : `${ms}ms`)
            return (
              <g key={r.key} className="sc-row" style={{ transform: `translate(0px, ${y}px)` }} tabIndex={0} role="img" aria-label={r.ariaLabel} {...bind(r.tip)}>
                <rect className="sc-row-hit" x={0} y={0} width={w} height={rowH} fill="transparent" />
                {stacked &&
                  ticks.map((t, i) => <line key={i} x1={xs(t)} x2={xs(t)} y1={trackY - 11} y2={trackY + 11} {...tickLine(t)} />)}
                <text className="sc-label" x={0} y={textY}>
                  {r.label}
                </text>
                <line
                  className={`sc-bar ${single ? 'sc-stem' : r.negative ? 'sc-down' : 'sc-up'}`}
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
                <text
                  className={`sc-fade ${single ? 'sc-delta-flat' : r.negative ? 'sc-delta-down' : 'sc-delta-up'}`}
                  x={w}
                  y={textY}
                  textAnchor="end"
                  style={{ opacity: revealed ? 1 : 0, transitionDelay: delay(d + 600) }}
                >
                  {r.right}
                </text>
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
