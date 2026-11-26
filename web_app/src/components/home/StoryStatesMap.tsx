import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { NATIONAL_BBOX, STATES_ALBERS_TOPO, dotsFor, fetchTopo, meetingColor, toFeats, type Feat } from '../../lib/dotMatrix'
import { excerptAroundMark, highlightSnippet } from '../../lib/highlight'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { HOUSE_THEME } from '../../utils/houseTheme'
import { isTouchOnly } from '../../utils/touchOnly'
import { STANCE_ORDER, bandSides, speakersOf, stanceCount, type Stance, type StanceCounts } from '../../utils/boxSplit'

export interface StateMarker {
  state_code: string
  state?: string | null
  meetings: number
}

/** One state's real speaker counts (positions `by_state`, #1087). */
export interface StateStance extends StanceCounts {
  state_code: string
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
  /** Each state's real passages, by state code (speakers' own words first, then meeting passages). Its boxes cycle through
   *  them; a state without one has no card. */
  quotes?: Map<string, StateQuote[]>
  /** Real speaker counts per state, national (#1087). Absent (the rentals story): boxes show meetings only. */
  stance?: StateStance[] | null
  /** The state the page is scoped to: its boxes at full strength, the rest muted. */
  highlight?: string | null
  /** Where a state's boxes go: the story for that state. */
  href: (stateCode: string) => string
  /** What came up, for the captions ("a data center", "short-term rentals"); the data center story by default (#1013). */
  subject?: string
}

const fmt = (n: number) => n.toLocaleString('en-US')
const plural = (n: number, one: string, many: string) => `${fmt(n)} ${n === 1 ? one : many}`
const W = NATIONAL_BBOX[2]
const H = NATIONAL_BBOX[3]
const COLS = 80

/** Box colours: the house theme's segment colours (no red/green pair), a grey for meetings without a stance, the empty tint. */
export const BOX_COLORS: Record<Stance | 'meetings' | 'none', string> = {
  against: HOUSE_THEME.seg[3]!, // muted red
  for: HOUSE_THEME.seg[0]!, // teal
  question: HOUSE_THEME.seg[2]!, // blue
  neutral: HOUSE_THEME.seg[6]!, // plum
  meetings: '#9AA5A9',
  none: HOUSE_THEME.neutral,
}
/** States with meetings but no stance on record, light to dark by their real meeting count (#1103). */
export const MEETING_GREYS = ['#D2D8DA', '#B3BCC0', '#8F9A9F', '#6B777D'] as const

/** An SVG path for a state's outline (albers coordinates, as drawn by us-atlas). */
export function featPath(f: Feat): string {
  return f.polys
    .map((rings) => rings.map((ring) => 'M' + ring.map(([x, y]) => `${x!.toFixed(1)},${y!.toFixed(1)}`).join('L') + 'Z').join(''))
    .join('')
}

/** Without stance data (the rentals story) a state with meetings is one teal. */
const MEETINGS_ONLY = HOUSE_THEME.seg[0]!

const STANCE_LABEL: Record<Stance, string> = {
  against: 'Spoke against',
  for: 'Spoke for',
  question: 'Asked a question',
  neutral: 'No side',
}

function fmtDate(iso: string | null): string | null {
  if (!iso) return null
  const d = new Date(`${iso.slice(0, 10)}T12:00:00`)
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function stanceLine(s: StanceCounts | undefined): string | null {
  if (!s || speakersOf(s) === 0) return null
  return STANCE_ORDER.filter((k) => stanceCount(s, k) > 0)
    .map((k) => `${fmt(stanceCount(s, k))} ${STANCE_LABEL[k].toLowerCase()}`)
    .join(' · ')
}

interface Box {
  x: number
  y: number
  code: string | null
  /** Index among its state's boxes, sorted left to right. */
  rank: number
  side: Stance | null
  /** Index among its state's boxes in the same side's band. */
  bandRank: number
}

/**
 * The home page's story map (#985, #995, #1087): the country as a grid of small square boxes in each state's shape (the
 * Explore map's geometry). Where speakers are on record, a state's boxes are split in bands by the real counts of those who
 * spoke against, for, asked a question or took no side; a state with meetings but no speaker on record is one grey; a state
 * with none is the empty tint. Hovering (tapping, on a phone) a box shows one of that state's real passages, cycling through
 * them across its boxes; clicking opens that state's story. Nothing is drawn from a guess: no counts, no split.
 */
export default function StoryStatesMap({ byState, quotes, stance, highlight, href, subject = 'a data center' }: Props) {
  const navigate = useNavigate()
  const [hover, setHover] = useState<number | null>(null)
  const touch = isTouchOnly()
  const { data: topo, isError } = useQuery({
    queryKey: ['us-atlas-states-albers'],
    queryFn: () => fetchTopo(STATES_ALBERS_TOPO),
    staleTime: 1000 * 60 * 60,
  })
  const grid = useMemo(() => {
    if (!topo) return null
    const feats = toFeats(topo, 'states').filter((f) => f.id !== '72')
    const { dots, step } = dotsFor(feats, NATIONAL_BBOX, COLS)
    // A state too small for a grid point (DC, at this grid) still gets one box, at its centre.
    const seen = new Set(dots.map((d) => d.id))
    for (const f of feats) {
      if (!seen.has(f.id)) dots.push({ x: (f.bbox[0] + f.bbox[2]) / 2, y: (f.bbox[1] + f.bbox[3]) / 2, id: f.id })
    }
    return { feats, dots, step }
  }, [topo])

  const stanceBy = useMemo(() => new Map((stance ?? []).map((s) => [s.state_code, s])), [stance])
  const boxes = useMemo<Box[] | null>(() => {
    if (!grid) return null
    const byFips = new Map<string, typeof grid.dots>()
    for (const d of grid.dots) {
      const list = byFips.get(d.id)
      if (list) list.push(d)
      else byFips.set(d.id, [d])
    }
    const out: Box[] = []
    for (const [fips, ds] of byFips) {
      const code = STATE_FIPS_TO_CODE[fips] ?? null
      // Left to right, then top to bottom, so each side fills one contiguous band of the state.
      const sorted = [...ds].sort((a, b) => a.x - b.x || a.y - b.y)
      const sides = bandSides(code ? stanceBy.get(code) : undefined, sorted.length)
      const seen: Partial<Record<Stance, number>> = {}
      sorted.forEach((d, rank) => {
        const side = sides[rank] ?? null
        const bandRank = side ? (seen[side] = (seen[side] ?? -1) + 1) : rank
        out.push({ x: d.x, y: d.y, code, rank, side, bandRank })
      })
    }
    return out
  }, [grid, stanceBy])

  if (isError) return <p className="text-sm text-stone-500">The map could not be loaded.</p>
  if (!grid || !boxes || byState == null) return <p className="text-sm text-stone-500" role="status">Loading the map…</p>

  const meetings = new Map(byState.map((s) => [s.state_code, s.meetings]))
  const maxMeetings = Math.max(0, ...byState.map((s) => s.meetings))
  const hasStance = stance != null
  const split = (stance ?? []).filter((s) => speakersOf(s) > 0)
  const speakersTotal = split.reduce((n, s) => n + speakersOf(s), 0)
  const stateName = (code: string) => byState.find((s) => s.state_code === code)?.state ?? STATE_CODE_TO_NAME[code] ?? code
  const colorOf = (b: Box): string => {
    if (!b.code) return BOX_COLORS.none
    if (b.side) return BOX_COLORS[b.side]
    const n = meetings.get(b.code) ?? 0
    if (n > 0) return hasStance ? meetingColor(n, maxMeetings, MEETING_GREYS, BOX_COLORS.meetings) : MEETINGS_ONLY
    return BOX_COLORS.none
  }

  const listed = [...new Set([...byState.filter((s) => s.meetings > 0).map((s) => s.state_code), ...split.map((s) => s.state_code)])]
    .map((code) => ({ code, name: stateName(code), meetings: meetings.get(code) ?? 0, st: stanceBy.get(code) }))
    .sort((a, b) => speakersOf(b.st) - speakersOf(a.st) || b.meetings - a.meetings || a.name.localeCompare(b.name))
  const withMeetings = byState.filter((s) => s.meetings > 0).length

  const shown = hover != null ? boxes[hover] : undefined
  const shownCode = shown?.code ?? null
  // The card: one of the state's passages, cycling across its boxes (box index mod passages). A box in a side's band shows
  // that side's own words when the state has some; otherwise the state's passages in turn.
  let quote: StateQuote | undefined
  if (shown && shownCode) {
    const all = quotes?.get(shownCode) ?? []
    const own = shown.side ? all.filter((q) => q.side === shown.side) : []
    if (own.length) quote = own[shown.bandRank % own.length]
    else if (all.length) quote = all[shown.rank % all.length]
  }
  const shownStance = shownCode ? stanceLine(stanceBy.get(shownCode)) : null
  const shownMeetings = shownCode ? meetings.get(shownCode) ?? 0 : 0
  const left = shown ? (shown.x / W) * 100 : 0
  const size = grid.step * 0.8
  const pad = 4

  const summary =
    `Map of the United States drawn as small boxes in each state's shape. ${plural(withMeetings, 'state has', 'states have')} at least one meeting where ${subject} came up.` +
    (hasStance && split.length
      ? ` In ${plural(split.length, 'state', 'states')} the boxes are split by ${plural(speakersTotal, 'speaker', 'speakers')} on record: ` +
        split.map((s) => `${stateName(s.state_code)}, ${stanceLine(s)}`).join('; ') +
        '.'
      : '') +
    ' The data table below lists every state; its links open each state’s story.'

  const onBox = (i: number) => {
    const b = boxes[i]
    if (!b?.code) return
    // On a phone the first tap shows the card (there is no hover); a second tap on the same state opens its story.
    if (touch && shownCode !== b.code) {
      setHover(i)
      return
    }
    navigate(href(b.code))
  }

  return (
    <div style={{ position: 'relative' }} onMouseLeave={() => setHover(null)}>
      <svg viewBox={`${-pad} ${-pad} ${W + pad * 2} ${H + pad * 2}`} className="block h-auto w-full" role="img" aria-label={summary}>
        {boxes.map((b, i) => {
          const muted = shownCode ? b.code !== shownCode : !!highlight && b.code !== highlight
          const on = (meetings.get(b.code ?? '') ?? 0) > 0 || !!b.side
          const s = on ? size : size * 0.6
          return (
            <rect
              key={i}
              x={b.x - s / 2}
              y={b.y - s / 2}
              width={s}
              height={s}
              rx={s * 0.12}
              fill={colorOf(b)}
              opacity={muted ? 0.7 : 1}
              stroke={i === hover ? '#1c1917' : undefined}
              strokeWidth={i === hover ? 1.5 : undefined}
              style={{ cursor: b.code ? 'pointer' : 'default' }}
              onMouseEnter={touch ? undefined : () => setHover(i)}
              onClick={() => onBox(i)}
            />
          )
        })}
        {/* State outlines over the boxes (#1103), so neighbouring states read as separate shapes. */}
        <g fill="none" stroke="#57534e" strokeOpacity={0.55} strokeWidth={0.8} strokeLinejoin="round" pointerEvents="none">
          {grid.feats.map((f) => (
            <path key={f.id} d={featPath(f)} />
          ))}
        </g>
      </svg>

      {shown && shownCode && quote && (
        // At the top of the map, on the side away from the box, so it never covers the box it describes.
        <figure className="home-map-card" style={left < 55 ? { right: 0, top: '2%' } : { left: 0, top: '2%' }}>
          <figcaption style={{ fontWeight: 700, fontSize: 15, color: '#1c1917', margin: '0 0 2px' }}>{quote.place}</figcaption>
          <p style={{ margin: '0 0 6px', fontSize: 12, color: '#57534e' }}>
            {quote.side ? `${STANCE_LABEL[quote.side]}${quote.who ? ` · ${quote.who}` : ''}` : 'In the meeting'}
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
          <p style={{ margin: '6px 0 0', fontSize: 12, color: '#57534e' }}>
            {stateName(shownCode)}: {plural(shownMeetings, 'meeting', 'meetings')}
            {shownStance ? ` · ${shownStance}` : hasStance ? ' · no stance on record' : ''}
          </p>
          {touch && (
            <p style={{ margin: '6px 0 0', fontSize: 13 }}>
              <Link to={href(shownCode)} style={{ color: '#0f766e', fontWeight: 600 }}>
                Open the story for {stateName(shownCode)} →
              </Link>
            </p>
          )}
        </figure>
      )}

      {/* Not a live region: it changes on every pointer move. Keyboard and screen readers use the data table. */}
      <p className="mt-1 min-h-[2.75rem] text-sm leading-snug text-stone-600" aria-live="off">
        {shown && shownCode
          ? `${stateName(shownCode)}: ${plural(shownMeetings, 'meeting', 'meetings')} where ${subject} came up${shownStance ? `; ${shownStance}` : hasStance ? '; no stance on record' : ''}. ${touch ? 'Tap again to open its story.' : 'Click to open its story.'}`
          : `${plural(withMeetings, 'state', 'states')} with at least one meeting where ${subject} came up. ${touch ? 'Tap a state to read what was said; tap again to open its story.' : 'Hover a box to read what was said; click to open that state’s story.'}`}
      </p>

      <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-stone-600" aria-label="Legend" style={{ listStyle: 'none', padding: 0 }}>
        {hasStance &&
          split.length > 0 &&
          STANCE_ORDER.map((k) => (
            <li key={k} className="inline-flex items-center gap-1">
              <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 2, background: BOX_COLORS[k], display: 'inline-block' }} />
              {STANCE_LABEL[k]}
            </li>
          ))}
        <li className="inline-flex items-center gap-1">
          {hasStance ? (
            <span aria-hidden="true" style={{ display: 'inline-flex', gap: 1 }}>
              {MEETING_GREYS.map((c) => (
                <span key={c} style={{ width: 10, height: 10, borderRadius: 2, background: c, display: 'inline-block' }} />
              ))}
            </span>
          ) : (
            <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 2, background: MEETINGS_ONLY, display: 'inline-block' }} />
          )}
          {hasStance ? 'Meetings, no stance on record (darker = more meetings)' : `Meetings where ${subject} came up`}
        </li>
        <li className="inline-flex items-center gap-1">
          <span aria-hidden="true" style={{ width: 7, height: 7, borderRadius: 2, background: BOX_COLORS.none, display: 'inline-block' }} />
          No meetings on record
        </li>
      </ul>
      {hasStance && (
        <p className="mt-1 text-xs text-stone-500">
          {split.length > 0
            ? `Split by ${plural(speakersTotal, 'speaker', 'speakers')} on record in ${plural(split.length, 'state', 'states')}; other states show meetings only.`
            : 'No speaker positions on record yet; states show meetings only.'}
        </p>
      )}

      <details className="mt-2 text-sm text-stone-700">
        <summary className="cursor-pointer text-stone-600">Show data table</summary>
        {listed.length === 0 ? (
          <p className="mt-1 text-stone-500">No meetings on record.</p>
        ) : (
          <div className="mt-1 max-h-64 overflow-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr>
                  <th scope="col" className="py-1 pr-2">State</th>
                  <th scope="col" className="py-1 pr-2">Meetings</th>
                  {hasStance &&
                    STANCE_ORDER.map((k) => (
                      <th key={k} scope="col" className="py-1 pr-2">
                        {STANCE_LABEL[k]}
                      </th>
                    ))}
                </tr>
              </thead>
              <tbody>
                {listed.map((r) => (
                  <tr key={r.code} className="border-t border-stone-200">
                    <td className="py-1 pr-2">
                      <Link to={href(r.code)} className="text-teal-800 underline">
                        {r.name}
                      </Link>
                    </td>
                    <td className="py-1 pr-2">{fmt(r.meetings)}</td>
                    {hasStance &&
                      STANCE_ORDER.map((k) => (
                        <td key={k} className="py-1 pr-2">
                          {r.st ? fmt(stanceCount(r.st, k)) : '—'}
                        </td>
                      ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>
    </div>
  )
}
