import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { geoPath } from 'd3-geo'
import { feature } from 'topojson-client'
import { STATES_ALBERS_TOPO, fetchTopo } from '../../lib/dotMatrix'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'

export interface StateMarker {
  state_code: string
  state?: string | null
  meetings: number
}

interface Props {
  /** Real meetings per state (meeting-mentions `counts.by_state`); null while loading. */
  byState: StateMarker[] | null | undefined
  /** The state the page is scoped to, drawn stronger. */
  highlight?: string | null
  /** Where a marker goes: the story for that state. */
  href: (stateCode: string) => string
}

const fmt = (n: number) => n.toLocaleString('en-US')

/**
 * The home page's story map (#985): the US in outline, one marker per state where a data center came up in at least one
 * meeting, its area proportional to that real count, each a link to the story for that state. A state with none has no
 * marker; nothing is drawn from a guess. The list under the map repeats every marker as a text link.
 */
export default function StoryStatesMap({ byState, highlight, href }: Props) {
  const [hover, setHover] = useState<string | null>(null)
  const { data: topo, isError } = useQuery({
    queryKey: ['us-atlas-states-albers'],
    queryFn: () => fetchTopo(STATES_ALBERS_TOPO),
    staleTime: 1000 * 60 * 60,
  })
  const shapes = useMemo(() => {
    if (!topo) return null
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const t = topo as any
    const fc = feature(t, t.objects.states) as unknown as { features: Array<{ id?: string | number; properties?: { name?: string } }> }
    const path = geoPath()
    return fc.features
      .filter((f) => String(f.id ?? '').padStart(2, '0') !== '72')
      .map((f) => {
        const fips = String(f.id ?? '').padStart(2, '0')
        return { fips, code: STATE_FIPS_TO_CODE[fips] ?? null, name: f.properties?.name ?? fips, d: path(f as never) ?? '', c: path.centroid(f as never) }
      })
  }, [topo])

  if (isError) return <p className="text-sm text-stone-500">The map could not be loaded. The list below links every state.</p>
  if (!shapes || byState == null) return <p className="text-sm text-stone-500" role="status">Loading the map…</p>

  const counts = new Map(byState.map((s) => [s.state_code, s.meetings]))
  const max = Math.max(1, ...byState.map((s) => s.meetings))
  // Area proportional to the count: radius ∝ √count, 3px to 18px in the 975-wide map.
  const r = (n: number) => 3 + 15 * Math.sqrt(n / max)
  const markers = shapes
    .filter((s) => s.code && (counts.get(s.code) ?? 0) > 0)
    .map((s) => ({ ...s, n: counts.get(s.code!)! }))
    .sort((a, b) => b.n - a.n)
  const hovered = markers.find((m) => m.code === hover)

  return (
    <div>
      <svg viewBox="0 0 975 610" className="block h-auto w-full" role="group" aria-label="States where a data center came up in local meetings">
        <g aria-hidden="true">
          {shapes.map((s) => (
            <path key={s.fips} d={s.d} fill={s.code === highlight ? '#ccfbf1' : '#f5f5f4'} stroke="#d6d3d1" strokeWidth={0.8} />
          ))}
        </g>
        {/* Largest first underneath, so small markers stay clickable on top. */}
        {markers.map((m) => (
          <Link
            key={m.fips}
            to={href(m.code!)}
            aria-label={`${m.name}: ${fmt(m.n)} ${m.n === 1 ? 'meeting' : 'meetings'} where a data center came up. Open the story for ${m.name}.`}
            onMouseEnter={() => setHover(m.code)}
            onMouseLeave={() => setHover(null)}
            onFocus={() => setHover(m.code)}
            onBlur={() => setHover(null)}
          >
            <title>{`${m.name}: ${fmt(m.n)} ${m.n === 1 ? 'meeting' : 'meetings'}`}</title>
            <circle
              cx={m.c[0]}
              cy={m.c[1]}
              r={r(m.n)}
              fill="#0f766e"
              fillOpacity={m.code === highlight || m.code === hover ? 0.95 : 0.6}
              stroke="#fff"
              strokeWidth={1.5}
              style={{ cursor: 'pointer' }}
            />
          </Link>
        ))}
      </svg>
      {/* A fixed two-line box: if the line changed height on hover the map would move under the pointer (#987). */}
      <p className="mt-1 h-[2.75rem] overflow-hidden text-sm leading-snug text-stone-600" aria-live="off">
        {hovered
          ? `${hovered.name}: ${fmt(hovered.n)} ${hovered.n === 1 ? 'meeting' : 'meetings'} where a data center came up. Click to open its story.`
          : markers.length
            ? `${markers.length} states with at least one meeting where a data center came up. Click a marker to open that state's story.`
            : 'No meetings on record yet.'}
      </p>
    </div>
  )
}
