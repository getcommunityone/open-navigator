import { useMemo } from 'react'
import { allocateBoxes, type BoxesSpec } from '../../utils/screenBoxes'
import './storyCharts.css'

const fmt = (n: number) => n.toLocaleString('en-US')

interface Props {
  spec: BoxesSpec | null | undefined
}

/**
 * A compact strip of boxes on a story screen (#1415): a takeaway title, one `[data-box]` mark per record (or per stated number
 * of records), and a colour legend with the counts. It is the landing place of the particle flights between screens (#1404),
 * so every screen has one. A screen with nothing on record shows one hollow box and says so; nothing is invented.
 */
export default function ScreenBoxes({ spec }: Props) {
  const alloc = useMemo(() => (spec ? allocateBoxes(spec.groups) : null), [spec])
  if (!spec || !alloc) return null
  const { cells, per, total } = alloc
  const legend = spec.groups.filter((g) => g.count > 0)
  return (
    <figure className="sb" data-screen-boxes="" aria-label={spec.title}>
      <figcaption className="sb-title" data-chart-title="">
        {spec.title}
      </figcaption>
      <div className="sb-grid" role="img" aria-label={`${fmt(total)} ${spec.unit}${per > 1 ? `, one box for ${fmt(per)}` : ''}`}>
        {cells.length === 0 ? (
          <span className="sb-box sb-box--empty" data-box="" data-group="none" />
        ) : (
          cells.map((c, i) => <span key={i} className="sb-box" data-box="" data-group={c.key} style={{ background: c.color, ['--i' as string]: i }} />)
        )}
      </div>
      <ul className="sb-legend" data-chart-legend="">
        {legend.map((g) => (
          <li key={g.key}>
            <span className="sb-swatch" style={{ background: g.color }} aria-hidden="true" />
            {g.label} <b>{fmt(g.count)}</b>
          </li>
        ))}
        {per > 1 && <li className="sb-unit">1 box = {fmt(per)} {spec.unit}</li>}
        {cells.length === 0 && <li className="sb-unit">0 {spec.unit}</li>}
      </ul>
      {spec.note && <p className="sb-note">{spec.note}</p>}
    </figure>
  )
}
