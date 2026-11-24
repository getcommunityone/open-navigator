export interface LegendItem {
  key: string
  label: string
  /** Any CSS colour (a hex from the theme). */
  color: string
  /** Draw the swatch as a ring (hollow). */
  hollow?: boolean
}

/**
 * The reference's interactive legend: square chips with a colour swatch. A click toggles the series (the last visible one
 * can't be turned off); an off chip is dimmed with a lighter border; hover or keyboard focus highlights one series.
 */
export default function LegendChips({
  items,
  off,
  onToggle,
  onHot,
  label,
}: {
  items: LegendItem[]
  off: ReadonlySet<string>
  onToggle: (key: string) => void
  onHot: (key: string | null) => void
  label: string
}) {
  const visible = items.filter((i) => !off.has(i.key)).length
  return (
    <div className="folio-legend-chips" role="group" aria-label={label}>
      {items.map((it) => {
        const on = !off.has(it.key)
        return (
          <button
            key={it.key}
            type="button"
            className="folio-legend-chip"
            aria-pressed={on}
            title={on && visible === 1 ? 'At least one series stays on' : undefined}
            onClick={() => onToggle(it.key)}
            onPointerEnter={() => onHot(it.key)}
            onPointerLeave={() => onHot(null)}
            onFocus={() => onHot(it.key)}
            onBlur={() => onHot(null)}
          >
            <span
              className="folio-legend-swatch"
              aria-hidden="true"
              style={it.hollow ? { background: 'transparent', border: `2px solid ${it.color}` } : { background: it.color }}
            />
            <span>{it.label}</span>
          </button>
        )
      })}
    </div>
  )
}
