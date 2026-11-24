import type { ReactNode } from 'react'
import { STEP_MID_T } from '../../utils/folioRamp'
import { stepColor } from './data'
import type { MatrixCtx } from './types'

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
