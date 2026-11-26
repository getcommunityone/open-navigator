import type { ReactNode } from 'react'
import { STEP_MID_T } from '../../utils/folioRamp'
import { stepColor } from './data'
import { delayVar, type MatrixCtx } from './types'

/** Segmented control: one pressed button. */
export function Seg({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: Array<{ value: string; label: string }>
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div className="folio-seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="folio-muted" role="status">
      {children}
    </p>
  )
}

/**
 * A sortable column header: a real button inside `<th scope="col" aria-sort>`, with the reference's arrows (↕ unsorted,
 * ↓ descending, ↑ ascending). The arrow is decorative; `aria-sort` carries the state.
 */
export function SortTh({
  label,
  active,
  dir,
  onSort,
  numeric,
  className = '',
}: {
  label: ReactNode
  active: boolean
  dir: 'asc' | 'desc'
  onSort: () => void
  numeric?: boolean
  className?: string
}) {
  return (
    <th scope="col" className={`${numeric ? 'text-right' : 'text-left'} ${className}`.trim()} aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className="folio-sortbtn" onClick={onSort}>
        {label} <span aria-hidden="true">{active ? (dir === 'asc' ? '↑' : '↓') : '↕'}</span>
      </button>
    </th>
  )
}

/**
 * A number with a thin bar beside it (the reference's inline bar). `fraction` is 0..1 or null (no bar for a missing value).
 * The bar repeats the number's position and is hidden from assistive tech: the text is its equivalent.
 */
export function InlineBar({ fraction, children, delayMs = 0 }: { fraction: number | null; children: ReactNode; delayMs?: number }) {
  return (
    <span className="folio-ibar">
      {fraction != null && (
        <span className="folio-ibar-track" aria-hidden="true">
          <span className="folio-ibar-fill folio-grow" style={{ width: `${Math.round(fraction * 1000) / 10}%`, ...delayVar(delayMs) }} />
        </span>
      )}
      <span>{children}</span>
    </span>
  )
}

/** The six-step rank scale with the "highlight the top of the scale" slider (the `min` param). */
export function ScaleLegend({ ctx, note, slider = true, lit }: { ctx: MatrixCtx; note: string; slider?: boolean; lit?: string }) {
  const { theme, minPct } = ctx
  return (
    <div className="folio-legend" aria-label="Scale">
      <span className="folio-legend-title">Scale</span>
      {['Lower rank', '', '', '', '', 'Higher rank'].map((l, i) => (
        <span key={i} className="inline-flex items-center gap-1">
          <span className="folio-swatch" style={{ background: stepColor(theme, STEP_MID_T[i]!) }} />
          {l}
        </span>
      ))}
      <span className="inline-flex items-center gap-1">
        <span className="folio-swatch" style={{ background: theme.neutral }} />
        No data
      </span>
      <span>({note}; for lower-is-better metrics a low value ranks higher)</span>
      {slider && (
        <label className="inline-flex items-center gap-1">
          Highlight the top of the scale, from {minPct}%
          <input
            type="range"
            min={0}
            max={95}
            step={5}
            value={minPct}
            style={{ accentColor: 'var(--violet-ink)' }}
            onChange={(e) => ctx.setQP('min', e.target.value === '0' ? null : e.target.value)}
          />
        </label>
      )}
      {lit && minPct > 0 && <span aria-live="polite">{lit}</span>}
    </div>
  )
}

/** Flat / By region toggle shared by Tiles and Pivot (the `group` param). */
export const GROUP_OPTIONS = [
  { value: 'none', label: 'Flat' },
  { value: 'region', label: 'By region' },
]
