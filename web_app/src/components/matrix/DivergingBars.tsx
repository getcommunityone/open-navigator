import { useRef } from 'react'
import { useElementWidth } from './hooks'
import { Tooltip, useTooltip, type TipInfo } from './Tooltip'

/** One piece of a row's bar. Pieces on a side are laid out outward from the centre axis in the order given. */
export interface BarSegment {
  key: string
  value: number
  side: 'left' | 'right'
  color: string
}
export interface BarRow {
  id: string
  label: string
  segments: BarSegment[]
  /** Text at the outer end of each side (already formatted); omitted when the side has no bar. */
  endLeft?: string
  endRight?: string
  info: TipInfo
  ariaLabel: string
}

const ROW_H = 40
const BAR_H = 16

/**
 * Diverging stacked bars on a shared centre axis, in the reference's Likert form: the row label sits above its bar, each
 * side stacks N ordered segments outward from the axis, end labels sit past each side's last segment, rows glide to new
 * positions when the order changes and the bars grow out from the axis when revealed.
 *
 * It takes generic rows (`{label, segments: [{key, value, side}]}`) so that a true five-category stack (for example the
 * public-comment stance data: For / Against / Asked questions / Mixed or neutral) can use it unchanged once that data is loaded.
 * `maxSide` is the largest total on either side (it sets the scale).
 */
export default function DivergingBars({
  rows,
  maxSide,
  revealed,
  hot,
  axisLabel,
  hotKeyOf,
}: {
  rows: BarRow[]
  maxSide: number
  revealed: boolean
  /** Series key under the pointer in the legend; other segments dim. */
  hot: string | null
  axisLabel: string
  /** Which legend series a segment belongs to (default: its side). */
  hotKeyOf?: (s: BarSegment) => string
}) {
  const host = useRef<HTMLDivElement>(null)
  const w = useElementWidth(host, 520)
  const tt = useTooltip()
  const side = Math.min(44, Math.round(w * 0.1))
  const cx = w / 2
  const unit = maxSide > 0 ? (w / 2 - side - 4) / maxSide : 0
  const h = 22 + rows.length * ROW_H + 8
  const keyOf = hotKeyOf ?? ((s: BarSegment) => s.side)
  return (
    <div ref={host}>
      <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} role="group" aria-label="Diverging bars" style={{ display: 'block', overflow: 'visible' }} onPointerLeave={tt.hide}>
        <text x={cx} y={10} textAnchor="middle" className="folio-svg-micro">
          {axisLabel}
        </text>
        <line x1={cx} x2={cx} y1={16} y2={h - 4} stroke="var(--ink)" strokeWidth={1.5} style={{ pointerEvents: 'none' }} />
        {rows.map((row, idx) => {
          const y = 22 + idx * ROW_H
          let left = 0
          let right = 0
          const parts = row.segments.map((s) => {
            const wpx = Math.max(0, s.value) * unit
            if (s.side === 'left') {
              left += wpx
              return { s, x: cx - left, w: wpx }
            }
            const x = cx + right
            right += wpx
            return { s, x, w: wpx }
          })
          return (
            <g key={row.id} className="folio-glide" style={{ transform: `translate3d(0, ${y}px, 0)` }}>
              <text x={0} y={11} className="folio-svg-label">
                {row.label}
              </text>
              <g
                tabIndex={0}
                role="img"
                aria-label={row.ariaLabel}
                style={{
                  transformOrigin: `${cx}px ${14 + BAR_H / 2}px`,
                  transform: `scaleX(${revealed ? 1 : 0})`,
                  transition: 'transform var(--d-3) var(--ease-out)',
                  transitionDelay: `${revealed ? Math.min(idx, 20) * 40 : 0}ms`,
                  cursor: 'pointer',
                }}
                {...tt.bind(row.info)}
              >
                {parts.map(({ s, x, w: pw }) => (
                  <rect
                    key={s.key}
                    x={x}
                    y={14}
                    width={pw}
                    height={BAR_H}
                    fill={s.color}
                    style={{ opacity: hot && hot !== keyOf(s) ? 0.25 : 1, transition: 'opacity var(--d-2) var(--ease-std)' }}
                  />
                ))}
                <rect x={cx - 1} y={12} width={2} height={BAR_H + 4} fill="var(--ink)" />
              </g>
              {row.endLeft && left > 0 && (
                <text x={cx - left - 6} y={14 + 12} textAnchor="end" style={{ fontSize: 11, fontWeight: 500, fill: 'var(--vermilion-ink)' }}>
                  {row.endLeft}
                </text>
              )}
              {row.endRight && right > 0 && (
                <text x={cx + right + 6} y={14 + 12} textAnchor="start" style={{ fontSize: 11, fontWeight: 500, fill: 'var(--violet-ink)' }}>
                  {row.endRight}
                </text>
              )}
              {/* A row exactly at the median has no bar: say so rather than leaving it blank. */}
              {left === 0 && right === 0 && (
                <text x={cx + 6} y={14 + 12} style={{ fontSize: 11, fill: 'var(--ink-2)' }}>
                  {row.endRight ?? row.endLeft ?? ''}
                </text>
              )}
            </g>
          )
        })}
      </svg>
      <Tooltip tip={tt.tip} />
    </div>
  )
}
