import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { geoPath } from 'd3-geo'
import { feature } from 'topojson-client'
import { STATES_ALBERS_TOPO, fetchTopo } from '../../lib/dotMatrix'
import { excerptAroundMark, highlightSnippet } from '../../lib/highlight'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'

export interface StateMarker {
  state_code: string
  state?: string | null
  meetings: number
}

/** One real meeting passage for a state's card: verbatim, with where and when it was said. */
export interface StateQuote {
  place: string
  /** A speaker's recorded side, when the quote is a speaker's own words (#995); absent for a meeting passage. */
  side?: 'for' | 'against' | 'question' | null
  /** Who spoke ("Resident"), when given. */
  who?: string | null
  /** Verbatim transcript excerpt; matched words in <mark>. */
  text: string
  date: string | null
  meeting: string | null
  /** The recording at the passage's moment, or the recording. */
  url: string | null
}

interface Props {
  /** Real meetings per state (meeting-mentions `counts.by_state`); null while loading. */
  byState: StateMarker[] | null | undefined
  /** The newest passage per state, by state code. A state without one has no card. */
  quotes?: Map<string, StateQuote>
  /** The state the page is scoped to, drawn stronger. */
  highlight?: string | null
  /** Where a pin goes: the story for that state. */
  href: (stateCode: string) => string
}

const fmt = (n: number) => n.toLocaleString('en-US')
const W = 975
const H = 610

function fmtDate(iso: string | null): string | null {
  if (!iso) return null
  const d = new Date(`${iso.slice(0, 10)}T12:00:00`)
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}


/**
 * The home page's story map (#985, #995): the US in outline, one pin per state where a data center came up in at least one
 * meeting (a little larger where there were more), each a link to the story for that state. Hovering or focusing a pin
 * shows that state's newest meeting passage, verbatim, with the place, date and meeting; the page's (or top) state's card
 * shows at rest. A state with no meetings has no pin and a state with no passage no card: nothing is drawn from a guess.
 */
export default function StoryStatesMap({ byState, quotes, highlight, href }: Props) {
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

  if (isError) return <p className="text-sm text-stone-500">The map could not be loaded.</p>
  if (!shapes || byState == null) return <p className="text-sm text-stone-500" role="status">Loading the map…</p>

  const counts = new Map(byState.map((s) => [s.state_code, s.meetings]))
  const max = Math.max(1, ...byState.map((s) => s.meetings))
  const r = (n: number) => 5 + 6 * Math.sqrt(n / max)
  const pins = shapes
    .filter((s) => s.code && (counts.get(s.code) ?? 0) > 0)
    .map((s) => ({ ...s, n: counts.get(s.code!)! }))
    .sort((a, b) => b.n - a.n)
  // The card shows only while a pin is hovered or focused; at rest the map is just the map (owner, #1002).
  const shown = hover ? pins.find((p) => p.code === hover) : undefined
  const quote = shown ? quotes?.get(shown.code!) : undefined
  const left = shown ? (shown.c[0] / W) * 100 : 0

  return (
    <div style={{ position: 'relative' }} onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="group" aria-label="States where a data center came up in local meetings">
        <g aria-hidden="true">
          {shapes.map((s) => (
            <path key={s.fips} d={s.d} fill={s.code === highlight ? '#ccfbf1' : '#f5f5f4'} stroke="#d6d3d1" strokeWidth={0.8} />
          ))}
        </g>
        {pins.map((m) => {
          const on = m.code === shown?.code
          return (
            <Link
              key={m.fips}
              to={href(m.code!)}
              aria-label={`${m.name}: ${fmt(m.n)} ${m.n === 1 ? 'meeting' : 'meetings'} where a data center came up. Open the story for ${m.name}.`}
              onMouseEnter={() => setHover(m.code)}
              onFocus={() => setHover(m.code)}
            >
              <title>{`${m.name}: ${fmt(m.n)} ${m.n === 1 ? 'meeting' : 'meetings'}`}</title>
              <circle cx={m.c[0]} cy={m.c[1]} r={r(m.n) + 4} fill="#fff" stroke="#0f766e" strokeWidth={on ? 3 : 2} style={{ cursor: 'pointer' }} />
              <circle cx={m.c[0]} cy={m.c[1]} r={Math.max(2.5, r(m.n) - 2)} fill="#0f766e" fillOpacity={on || m.code === highlight ? 1 : 0.75} />
            </Link>
          )
        })}
      </svg>

      {shown && quote && (
        // At the top of the map, on the side away from the pin, so it never covers the pin it describes or runs off the map.
        <figure className="home-map-card" style={left < 55 ? { right: 0, top: '2%' } : { left: 0, top: '2%' }}>
          <figcaption style={{ fontWeight: 700, fontSize: 15, color: '#1c1917', margin: '0 0 2px' }}>{quote.place}</figcaption>
          <p style={{ margin: '0 0 6px', fontSize: 12, color: '#57534e' }}>
            {quote.side
              ? `${quote.side === 'against' ? 'Spoke against' : quote.side === 'for' ? 'Spoke for' : 'Asked a question'}${quote.who ? ` · ${quote.who}` : ''}`
              : 'In the meeting'}
          </p>
          <blockquote style={{ margin: 0, fontStyle: 'italic', fontSize: 13.5, lineHeight: 1.45, color: '#44403c' }}>
            “{highlightSnippet(excerptAroundMark(quote.text))}”
          </blockquote>
          <p style={{ margin: '8px 0 0', paddingTop: 8, borderTop: '1px solid #e7e5e4', fontSize: 12.5, color: '#57534e', display: 'flex', flexWrap: 'wrap', gap: '4px 12px' }}>
            {fmtDate(quote.date) && <span>{fmtDate(quote.date)}</span>}
            {quote.meeting && <span>{quote.meeting}</span>}
            {quote.url && (
              <a href={quote.url} target="_blank" rel="noopener noreferrer" style={{ color: '#0f766e', fontWeight: 600 }}>
                Hear it ↗
              </a>
            )}
          </p>
        </figure>
      )}

      <p className="mt-1 h-[2.75rem] overflow-hidden text-sm leading-snug text-stone-600" aria-live="off">
        {hover && shown
          ? `${shown.name}: ${fmt(shown.n)} ${shown.n === 1 ? 'meeting' : 'meetings'} where a data center came up. Click to open its story.`
          : `${pins.length} states with at least one meeting where a data center came up. Hover a pin to read what was said; click one to open that state's story.`}
      </p>
    </div>
  )
}
