/**
 * InflationToggle — compact Nominal / Real pill for dollar charts.
 *
 * Matches the mockup: rounded-full pill, light gray track, white active
 * segment with subtle shadow. Stays small enough to sit in a KPI card
 * header without competing for attention with the headline number.
 *
 * State lives in ``useInflationToggle`` (localStorage-persisted, cross-tab
 * synced); this component is purely presentational, so the same hook can
 * drive multiple toggles on a page and they stay in sync.
 */
import type { InflationMode } from '../hooks/useInflationToggle'

interface Props {
  mode: InflationMode
  onChange: (next: InflationMode) => void
  /** Hidden visually but read by screen readers — e.g. "median home value". */
  ariaLabel?: string
  className?: string
}

export default function InflationToggle({ mode, onChange, ariaLabel, className }: Props) {
  const labelledBy = ariaLabel ? `inflation-toggle-${ariaLabel.replace(/\s+/g, '-')}` : undefined
  return (
    <div
      role="radiogroup"
      aria-labelledby={labelledBy}
      className={`inline-flex rounded-full bg-slate-100 p-0.5 text-[10px] font-medium ${className ?? ''}`}
    >
      {labelledBy ? (
        <span id={labelledBy} className="sr-only">
          {ariaLabel}: nominal or real dollars
        </span>
      ) : null}
      <button
        type="button"
        role="radio"
        aria-checked={mode === 'nominal'}
        onClick={() => onChange('nominal')}
        className={`rounded-full px-2.5 py-0.5 transition ${
          mode === 'nominal'
            ? 'bg-white text-slate-900 shadow-sm'
            : 'text-slate-500 hover:text-slate-700'
        }`}
      >
        Nominal
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={mode === 'real'}
        onClick={() => onChange('real')}
        className={`rounded-full px-2.5 py-0.5 transition ${
          mode === 'real'
            ? 'bg-white text-slate-900 shadow-sm'
            : 'text-slate-500 hover:text-slate-700'
        }`}
      >
        Real
      </button>
    </div>
  )
}
