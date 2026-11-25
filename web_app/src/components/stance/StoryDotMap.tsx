import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { NATIONAL_BBOX, STATES_ALBERS_TOPO, dotsFor, fetchTopo, meetingColor, toFeats } from '../../lib/dotMatrix'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'
import { HOUSE_THEME } from '../../utils/houseTheme'

export interface StateCount {
  state_code: string
  state?: string | null
  meetings: number
}

interface Props {
  /** Real meetings per state across the whole country (meeting-mentions `counts.by_state`, never narrowed by scope). */
  byState: StateCount[] | null | undefined
  /** The state the story is scoped to, if any (its dots stand out; the rest are muted, still with their own counts). */
  scopeStateCode: string | null
  /** The city the story is scoped to, if any: clicking its state then broadens to the state, not past it. */
  scopeCity?: string | null
  /** The scope label, for the figure caption ("National", "Texas", "Austin, Texas"). */
  scopeLabel: string
  /** Narrow the story to a state, or broaden it to the whole country (null). */
  onPickState: (stateCode: string | null) => void
  labelledBy?: string
}

const fmt = (n: number) => n.toLocaleString('en-US')


/**
 * Overview dot map (#970): the country as a grid of dots, each state's dots shaded by the real number of its meetings where a
 * data center came up, nationally. A state with none stays the empty colour. When the story is scoped to a state, that state
 * stands out and the others are muted, still shaded by their own counts, so no state reads as empty because it wasn't counted.
 * Clicking or choosing a state narrows the whole story to it (the scope in the URL); from a city, clicking its state broadens
 * to the state, and United States broadens to the country.
 */
export default function StoryDotMap({ byState, scopeStateCode, scopeCity = null, scopeLabel, onPickState, labelledBy }: Props) {
  const [hover, setHover] = useState<string | null>(null)
  const { data: topo, isError } = useQuery({
    queryKey: ['us-atlas-states-albers'],
    queryFn: () => fetchTopo(STATES_ALBERS_TOPO),
    staleTime: 1000 * 60 * 60,
  })
  const grid = useMemo(() => {
    if (!topo) return null
    const feats = toFeats(topo, 'states').filter((f) => f.id !== '72')
    return { feats, ...dotsFor(feats, NATIONAL_BBOX, 90) }
  }, [topo])

  const counts = useMemo(() => new Map((byState ?? []).map((s) => [s.state_code, s])), [byState])
  const max = Math.max(0, ...(byState ?? []).map((s) => s.meetings))
  const min = Math.min(...(byState ?? []).map((s) => s.meetings).filter((n) => n > 0), max)
  // The theme's light-to-brand teal steps; its last, near-black step is left out so the busiest states read as teal, not ink.
  const ramp = HOUSE_THEME.ramp.slice(1, 5)
  const colorFor = (n: number | undefined): string => meetingColor(n, max, ramp, HOUSE_THEME.neutral)
  const codeOf = (fips: string) => STATE_FIPS_TO_CODE[fips] ?? null
  const nameOf = (fips: string) => grid?.feats.find((f) => f.id === fips)?.name ?? fips
  const readout = (fips: string) => {
    const code = codeOf(fips)
    const n = code ? counts.get(code)?.meetings ?? 0 : 0
    return `${nameOf(fips)}: ${n ? `${fmt(n)} ${n === 1 ? 'meeting' : 'meetings'}` : 'no meetings on record'}`
  }

  if (isError) {
    return (
      <p className="stance-nodata" role="status">
        The map shapes could not be loaded. The counts below and the data table still show every state.
      </p>
    )
  }
  if (!grid || byState == null) {
    return (
      <p className="stance-note" role="status">
        Loading the map…
      </p>
    )
  }

  const listed = [...(byState ?? [])].sort((a, b) => b.meetings - a.meetings || a.state_code.localeCompare(b.state_code))
  const r = grid.step * 0.38
  const pad = 4
  const vb = `${-pad} ${-pad} ${NATIONAL_BBOX[2] + pad * 2} ${NATIONAL_BBOX[3] + pad * 2}`
  const options = [...grid.feats]
    .map((f) => ({ code: codeOf(f.id), name: f.name }))
    .filter((o): o is { code: string; name: string } => !!o.code)
    .sort((a, b) => a.name.localeCompare(b.name))

  return (
    <figure className="stance-map" aria-labelledby={labelledBy}>
      <figcaption className="stance-map-head">
        <span>
          Meetings where a data center came up, by state · National{scopeStateCode ? ` (${scopeLabel} highlighted)` : ''}
        </span>
        <span className="stance-map-controls">
          {scopeStateCode && (
            <button type="button" className="folio-link-btn" onClick={() => onPickState(null)}>
              United States
            </button>
          )}
          <select
            aria-label="Show one state"
            className="folio-select"
            value={scopeStateCode ?? ''}
            onChange={(e) => onPickState(e.target.value || null)}
          >
            <option value="">All states</option>
            {options.map((o) => (
              <option key={o.code} value={o.code}>
                {o.name}
              </option>
            ))}
          </select>
        </span>
      </figcaption>
      <svg
        viewBox={vb}
        className="stance-map-svg"
        role="img"
        aria-label={`Dot map of meetings where a data center came up, by state, nationally${scopeStateCode ? `, with ${scopeLabel} highlighted` : ''}. ${listed.length} ${listed.length === 1 ? 'state has' : 'states have'} at least one.`}
        onMouseLeave={() => setHover(null)}
      >
        {grid.dots.map((d, i) => {
          const code = codeOf(d.id)
          const mine = !scopeStateCode || code === scopeStateCode
          const n = code ? counts.get(code)?.meetings : undefined
          return (
            <circle
              key={i}
              cx={d.x}
              cy={d.y}
              r={n ? r : r * 0.55}
              fill={colorFor(n)}
              opacity={(hover && hover !== d.id) || !mine ? 0.3 : 1}
              style={{ cursor: code ? 'pointer' : 'default' }}
              onMouseEnter={() => setHover(d.id)}
              onClick={() => {
                if (!code) return
                // The scoped state again: from a city, up to the state; from the state, up to the country.
                if (code === scopeStateCode) onPickState(scopeCity ? code : null)
                else onPickState(code)
              }}
            />
          )
        })}
      </svg>
      {/* Not a live region: it changes on every pointer move. Keyboard and screen readers use the select and the table. */}
      <p className="stance-map-readout">
        {hover ? readout(hover) : 'Hover a state, or choose one, to see its count. Click a state to tell its story.'}
      </p>
      {max > 0 && (
        <div className="stance-map-legend" aria-hidden="true">
          {min < max ? (
            <>
              <span>{fmt(min)}</span>
              <span className="stance-map-ramp">
                {ramp.map((c, i) => (
                  <span key={i} style={{ background: c }} />
                ))}
              </span>
              <span>{fmt(max)} meetings</span>
            </>
          ) : (
            <>
              <span className="stance-map-ramp">
                <span style={{ background: colorFor(max) }} />
              </span>
              <span>
                {fmt(max)} {max === 1 ? 'meeting' : 'meetings'}
              </span>
            </>
          )}
          <span className="stance-map-none">
            <span style={{ background: HOUSE_THEME.neutral }} /> none on record
          </span>
        </div>
      )}
      <details className="stance-map-table">
        <summary>Show data table</summary>
        {listed.length === 0 ? (
          <p className="stance-note">No meetings on record.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th scope="col">State</th>
                <th scope="col">Meetings</th>
              </tr>
            </thead>
            <tbody>
              {listed.map((s) => (
                <tr key={s.state_code}>
                  <td>{s.state ?? s.state_code}</td>
                  <td>{fmt(s.meetings)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </details>
    </figure>
  )
}
