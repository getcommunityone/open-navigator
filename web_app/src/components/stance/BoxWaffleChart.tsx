import { useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { HOUSE_STYLE } from '../../utils/houseTheme'
import { allocateWaffleCells, type WaffleCategory } from '../../utils/waffleGrid'
import { Tooltip, useTooltip } from '../matrix/Tooltip'
import { useChartReveal } from './useChartReveal'
import './storyCharts.css'

interface Props {
  categories: WaffleCategory[]
  title: string
  unitLabel?: string
  /** Optional key that replays the sequential box wave when scope changes. */
  replayKey?: string
}

const fmt = (n: number) => n.toLocaleString('en-US')

/**
 * 10x10 proportion waffle chart (#1400, ported from vizjb12 §4.8A): 100 rounded boxes filled from bottom-left,
 * with sequential entrance wave, interactive category spotlighting (dims others to `--neutral-data`), a bold headline
 * percentage stat readout, and `[data-box]` marks so its 100 boxes participate in cross-screen particle flights.
 */
export default function BoxWaffleChart({ categories, title, unitLabel = 'records', replayKey }: Props) {
  const { cells, shares, total } = useMemo(() => allocateWaffleCells(categories, 10), [categories])
  const { ref: revealRef, revealed, reduced } = useChartReveal<SVGSVGElement>(replayKey ?? `${title}|${total}`)
  const { bind, tip, hide } = useTooltip()
  const [hovered, setHovered] = useState<string | null>(null)
  const [pinned, setPinned] = useState<string | null>(null)

  if (total <= 0 || cells.length === 0) return null

  const activeKey = hovered ?? pinned
  const lead = (activeKey ? shares.find((s) => s.key === activeKey) : null) ?? shares[0]!
  const leadPct = Math.round(lead.pct)

  const cellSize = 18
  const gap = 3.5
  const step = cellSize + gap
  const gridPx = 10 * step - gap
  const cellsByKey = new Map(shares.map((s) => [s.key, s.cells]))

  return (
    <div className="wf-wrap" aria-label={`${title}: 100-box proportion grid of ${fmt(total)} ${unitLabel}`}>
      <div className="wf-main">
        <div className="wf-stat" aria-live="polite">
          <span className="wf-stat-num">{leadPct}%</span>
          <span className="wf-stat-label">{lead.label}</span>
          <span className="wf-stat-sub">
            {fmt(lead.count)} of {fmt(total)} {unitLabel}
          </span>
        </div>
        <svg
          ref={revealRef}
          className={`wf-svg${revealed ? ' is-revealed' : ''}`}
          viewBox={`0 0 ${gridPx} ${gridPx}`}
          role="img"
          aria-label={`10 by 10 box waffle chart of ${title}. Top share: ${lead.label}, ${leadPct}% (${fmt(lead.count)} of ${fmt(total)} ${unitLabel}).`}
          onPointerLeave={() => {
            setHovered(null)
            hide()
          }}
        >
          {cells.map((c) => {
            const dimmed = activeKey != null && activeKey !== c.categoryKey
            const delay = reduced ? 0 : c.index * 5
            const b = bind({
              cat: c.label,
              val: `${Math.round(c.sharePct)}% (${cellsByKey.get(c.categoryKey) ?? 0} of 100 boxes)`,
              sub: `${fmt(c.count)} of ${fmt(total)} ${unitLabel}`,
            })
            return (
              <rect
                key={c.index}
                data-box=""
                data-group={c.categoryKey}
                className="wf-cell"
                x={(c.col * step).toFixed(2)}
                y={(c.row * step).toFixed(2)}
                width={cellSize}
                height={cellSize}
                rx={3}
                fill={dimmed ? 'var(--neutral-data)' : c.color}
                opacity={dimmed ? 0.35 : 1}
                style={{ transitionDelay: `${delay}ms, 0ms, 0ms` }}
                onPointerEnter={(e) => {
                  setHovered(c.categoryKey)
                  b.onPointerEnter(e)
                }}
                onPointerMove={b.onPointerMove}
                onPointerLeave={b.onPointerLeave}
                onClick={() => setPinned((p) => (p === c.categoryKey ? null : c.categoryKey))}
              />
            )
          })}
        </svg>
      </div>
      <div className="wf-legend" role="group" aria-label={`Filter or highlight categories for ${title}`}>
        {shares.map((s) => {
          const on = pinned === s.key
          const active = activeKey === s.key
          return (
            <button
              key={s.key}
              type="button"
              className={`wf-leg-btn${on ? ' is-pinned' : ''}${active ? ' is-active' : ''}`}
              aria-pressed={on}
              onMouseEnter={() => setHovered(s.key)}
              onMouseLeave={() => setHovered(null)}
              onFocus={() => setHovered(s.key)}
              onBlur={() => setHovered(null)}
              onClick={() => setPinned((p) => (p === s.key ? null : s.key))}
            >
              <span className="wf-leg-swatch" style={{ background: s.color }} aria-hidden="true" />
              <span>{s.label}</span>
              <span className="wf-leg-n">{fmt(s.count)}</span>
            </button>
          )
        })}
      </div>
      {typeof document !== 'undefined' && createPortal(<div className="folio" style={HOUSE_STYLE}><Tooltip tip={tip} /></div>, document.body)}
    </div>
  )
}
