import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import MapSkeleton, { NATIONAL_MAP_ASPECT } from './MapSkeleton'
import { COUNTIES_ALBERS_TOPO, NATIONAL_BBOX, STATES_ALBERS_TOPO, fetchTopo, meetingColor } from '../../lib/dotMatrix'
import { NATIONAL_PAD, RAMP, nationalGrid } from './nationalDots'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { HOUSE_THEME } from '../../utils/houseTheme'
import { excerptAroundMark } from '../../lib/highlight'
import { pickInsight } from '../../utils/chartInsight'
import ChartFrame, { type LegendItem } from '../chart/ChartFrame'
import QuoteCard from './QuoteCard'
import { dataCenterQuoteNote } from '../../utils/topicPositions'
import { resolveVideoId, startFromUrl } from './quoteCardUtils'
import { useMapKeyboard, westToEast } from '../../hooks/useMapKeyboard'
import { isTouchOnly, prefersStillMedia } from '../../utils/touchOnly'
import { pickZoneIndex } from '../../utils/mapQuote'
import { layoutHoverBadge } from '../../utils/mapHoverBadge'
import { featPath } from '../home/StoryStatesMap'

/** A meeting passage to quote on the map: verbatim from the record, with where and when it was said. */
export interface MapPassage {
  state_code?: string | null
  jurisdiction_name?: string | null
  meeting_date?: string | null
  meeting_title?: string | null
  /** Verbatim excerpt; matched words in <mark>. */
  evidence?: string | null
  jump_url?: string | null
  video_url?: string | null
  /** The recording's YouTube id and the passage's start, when known (#1108). */
  video_id?: string | null
  start_seconds?: number | null
  /** The meeting's AI summary and its page in the app, when on record (#1124). */
  meeting_summary?: string | null
  meeting_url?: string | null
  /** "First L." and role, only when the record attributes the quoted words to a person (#1124). */
  speaker_display_name?: string | null
  speaker_role?: string | null
  /** Jev's reading of the public at that meeting (data_center_meeting_lean, #1230): the card's stance line. */
  ai_public_lean?: string | null
}

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
  /** The scope's meeting passages, newest first (meeting-mentions `items`). One is quoted on the map while the reader
   *  hovers a state: that state's newest, where the scope has one. Nothing is quoted at rest (#1002). */
  passages?: MapPassage[] | null
}

const fmt = (n: number) => n.toLocaleString('en-US')
/**
 * Overview dot map (#970): the country as a grid of dots, each state's dots shaded by the real number of its meetings where a
 * data center came up, nationally. A state with none stays the empty colour. When the story is scoped to a state, that state
 * stands out and the others are muted, still shaded by their own counts, so no state reads as empty because it wasn't counted.
 * Clicking or choosing a state narrows the whole story to it (the scope in the URL); from a city, clicking its state broadens
 * to the state, and United States broadens to the country. On a desktop, hovering a state outlines it and shows its newest
 * passage in a card at the map's bottom-left, the recording playing muted at the quoted moment (#1277); on a phone there is
 * no card, and a tap narrows the story at once.
 */
export default function StoryDotMap({ byState, scopeStateCode, scopeCity = null, scopeLabel, onPickState, labelledBy, passages }: Props) {
  const [hover, setHover] = useState<string | null>(null)
  const [hoverDot, setHoverDot] = useState<number | null>(null)
  const quoted = useMemo(() => (passages ?? []).filter((m) => m.evidence), [passages])
  const qc = useQueryClient()
  const { data: topo, isError, refetch } = useQuery({
    queryKey: ['us-atlas-states-albers'],
    queryFn: () => fetchTopo(STATES_ALBERS_TOPO),
    staleTime: 1000 * 60 * 60,
  })
  const grid = useMemo(() => (topo ? nationalGrid(topo) : null), [topo])
  // Per-dot left-to-right rank inside its state so hovering different parts of a state cycles across its passages (#1357).
  const dotMeta = useMemo(() => {
    if (!grid) return null
    const byFips = new Map<string, Array<{ i: number; x: number; y: number }>>()
    grid.dots.forEach((d, i) => {
      const list = byFips.get(d.id)
      if (list) list.push({ i, x: d.x, y: d.y })
      else byFips.set(d.id, [{ i, x: d.x, y: d.y }])
    })
    const meta = new Array<{ rank: number; total: number }>(grid.dots.length)
    for (const list of byFips.values()) {
      list.sort((a, b) => a.x - b.x || a.y - b.y)
      list.forEach((item, rank) => {
        meta[item.i] = { rank, total: list.length }
      })
    }
    return meta
  }, [grid])

  const counts = useMemo(() => new Map((byState ?? []).map((s) => [s.state_code, s])), [byState])
  const max = Math.max(0, ...(byState ?? []).map((s) => s.meetings))
  const min = Math.min(...(byState ?? []).map((s) => s.meetings).filter((n) => n > 0), max)
  const ramp = RAMP
  const colorFor = (n: number | undefined): string => meetingColor(n, max, ramp, HOUSE_THEME.neutral)
  const codeOf = (fips: string) => STATE_FIPS_TO_CODE[fips] ?? null
  const stateNameOf = (code: string) => byState?.find((s) => s.state_code === code)?.state ?? STATE_CODE_TO_NAME[code] ?? code
  const nameOf = (fips: string) => grid?.feats.find((f) => f.id === fips)?.name ?? fips
  const readout = (fips: string) => {
    const code = codeOf(fips)
    const n = code ? counts.get(code)?.meetings ?? 0 : 0
    return `${nameOf(fips)}: ${n ? `${fmt(n)} ${n === 1 ? 'meeting' : 'meetings'}` : 'no meetings on record'}`
  }
  const pick = (fips: string) => {
    const code = codeOf(fips)
    if (!code) return
    // The scoped state again: from a city, up to the state; from the state, up to the country.
    if (code === scopeStateCode) onPickState(scopeCity ? code : null)
    else onPickState(code)
  }
  // Keyboard (#1146): one tab stop, the arrows move state to state west to east, Enter tells that state's story.
  const order = useMemo(() => (grid ? westToEast(grid.dots, (i) => (codeOf(grid.dots[i]!.id) ? grid.dots[i]!.id : null)) : []), [grid])
  const scopeFips = scopeStateCode ? grid?.feats.find((f) => codeOf(f.id) === scopeStateCode)?.id ?? null : null
  const keyNav = useMapKeyboard<string>({
    keys: order,
    active: hover,
    setActive: (fips) => {
      setHoverDot(null)
      setHover(fips)
    },
    initial: scopeFips,
    noun: 'state',
    describe: readout,
    onActivate: pick,
  })
  const touch = isTouchOnly()
  // A click, or a tap on a phone (no card there, #1277), tells the state's story at once.
  const onDot = (fips: string) => pick(fips)

  // Loading (#1328): the map's own box and a quiet shimmer; a failure says so with Try again.
  if (isError) return <MapSkeleton aspect={NATIONAL_MAP_ASPECT} error onRetry={() => void refetch()} />
  if (!grid || byState == null) return <MapSkeleton aspect={NATIONAL_MAP_ASPECT} />

  const hoverCode = hover ? codeOf(hover) : null
  // Only while a state is hovered, on a desktop: walk across that state's passages by hovered zone (#1357). No card at
  // rest (#1002); none on a phone (#1277).
  const passage = (() => {
    if (!hoverCode || touch) return undefined
    const statePassages = quoted.filter((m) => m.state_code === hoverCode)
    if (statePassages.length === 0) return undefined
    const meta = hoverDot != null ? dotMeta?.[hoverDot] : undefined
    return statePassages[meta ? pickZoneIndex(meta.rank, meta.total, statePassages.length) : 0]
  })()
  const hoverFeat = hover ? grid.feats.find((f) => f.id === hover) : undefined
  const inlineVideo = keyNav.keyed || prefersStillMedia() ? 'click' : 'autoplay'
  const pickLabel = (code: string) =>
    code === scopeStateCode ? (scopeCity ? `Click to show all of ${stateNameOf(code)}` : 'Click to show the whole country') : `Click ${stateNameOf(code)} to open its story`

  const listed = [...(byState ?? [])].sort((a, b) => b.meetings - a.meetings || a.state_code.localeCompare(b.state_code))
  const r = grid.step * 0.38
  const pad = NATIONAL_PAD
  const vbTuple: [number, number, number, number] = [-pad, -pad, NATIONAL_BBOX[2] + pad * 2, NATIONAL_BBOX[3] + pad * 2]
  const vb = vbTuple.join(' ')
  const drillCueLabel =
    !touch && hoverCode && hoverFeat
      ? hoverCode === scopeStateCode
        ? scopeCity
          ? `${stateNameOf(hoverCode)} · Click for whole state →`
          : 'Click for United States →'
        : `${stateNameOf(hoverCode)} · Click to drill down →`
      : null
  const drillCue = drillCueLabel && hoverFeat ? layoutHoverBadge(hoverFeat.bbox, vbTuple, drillCueLabel, grid.step) : null
  const options = [...grid.feats]
    .map((f) => ({ code: codeOf(f.id), name: f.name }))
    .filter((o): o is { code: string; name: string } => !!o.code)
    .sort((a, b) => a.name.localeCompare(b.name))

  // Title and key (#1409): the most impactful finding the real counts support, the description as caption.
  const total = listed.reduce((a, r) => a + Math.max(0, r.meetings), 0)
  const withMtgs = listed.filter((r) => r.meetings > 0)
  const insight = pickInsight({
    subject: 'data centers',
    place: 'the United States',
    totalMeetings: total,
    topPlaces: withMtgs.slice(0, 2).map((r) => stateNameOf(r.state_code)),
  })
  const title = insight.kind === 'none' ? 'Meetings where a data center came up, by state · National' : insight.title
  const caption = `Meetings where a data center came up, by state · National${scopeStateCode ? ` (${stateNameOf(scopeStateCode)} highlighted${scopeCity ? `, which contains ${scopeCity}` : ''})` : ''}`
  const legend: LegendItem[] = [
    max > 0
      ? min < max
        ? { key: 'ramp', label: `${fmt(min)} to ${fmt(max)} meetings (darker = more meetings)`, color: ramp[ramp.length - 1] ?? colorFor(max), shape: 'ramp', ramp }
        : { key: 'ramp', label: `${fmt(max)} ${max === 1 ? 'meeting' : 'meetings'}`, color: colorFor(max) }
      : { key: 'ramp', label: 'Meetings (darker = more meetings)', color: ramp[ramp.length - 1] ?? HOUSE_THEME.neutral, shape: 'ramp', ramp },
    { key: 'none', label: 'No meetings on record', color: HOUSE_THEME.neutral },
  ]

  return (
    // Leaving the figure (map, lines and card), not moving between them, hides the card (#1277).
    <figure
      className="stance-map map-fade-in"
      aria-labelledby={labelledBy}
      onMouseLeave={() => {
        setHover(null)
        setHoverDot(null)
      }}
      // The state's county shapes, fetched on the first hover so the drill-down is ready when a state is picked (#1328).
      onMouseEnter={() => void qc.prefetchQuery({ queryKey: ['us-atlas-counties-albers'], queryFn: () => fetchTopo(COUNTIES_ALBERS_TOPO), staleTime: 1000 * 60 * 60 })}
      {...keyNav.stageProps}
    >
      <ChartFrame
        title={title}
        titleSupport={insight.support}
        caption={insight.kind === 'none' ? undefined : caption}
        legend={legend}
        headClassName="stance-map-head"
        controls={
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
        }
      >
      <div className="stance-map-stage">
      {keyNav.sr}
      <svg
        viewBox={vb}
        className="stance-map-svg"
        data-map="national"
        aria-label={`Dot map of meetings where a data center came up, by state, nationally${scopeStateCode ? `, with ${stateNameOf(scopeStateCode)} highlighted (the story is scoped to ${scopeLabel})` : ''}. ${listed.length} ${listed.length === 1 ? 'state has' : 'states have'} at least one.`}
        {...keyNav.svgProps}
      >
        {grid.dots.map((d, i) => {
          const code = codeOf(d.id)
          const mine = !scopeStateCode || code === scopeStateCode
          const n = code ? counts.get(code)?.meetings : undefined
          const s = (n ? r : r * 0.55) * 1.85
          return (
            <rect
              key={i}
              data-box=""
              data-state={code ?? undefined}
              data-active={hover === d.id ? '' : undefined}
              x={d.x - s / 2}
              y={d.y - s / 2}
              width={s}
              height={s}
              rx={s * 0.14}
              fill={colorFor(n)}
              opacity={(hover && hover !== d.id) || (!hover && !mine) ? 0.3 : 1}
              style={{ cursor: code ? 'pointer' : 'default' }}
              onMouseEnter={
                touch
                  ? undefined
                  : () => {
                      keyNav.pointed()
                      setHover(d.id)
                      setHoverDot(i)
                    }
              }
              onClick={() => onDot(d.id)}
            />
          )
        })}
        {/* The hovered state's outline, raised (#1277), so the whole state reads as one thing to click. */}
        {hoverFeat && (
          <path d={featPath(hoverFeat)} fill="none" stroke="#1c1917" strokeWidth={2.4} strokeLinejoin="round" pointerEvents="none" data-active-outline="" />
        )}
        {/* On-map drill-down cue (#1360): non-blocking teal pill anchored to the hovered state on desktop. */}
        {drillCue && drillCueLabel && (
          <g pointerEvents="none" data-hover-drill-cue="">
            <rect
              x={drillCue.x}
              y={drillCue.y}
              width={drillCue.width}
              height={drillCue.height}
              rx={drillCue.rx}
              fill="#0f766e"
              stroke="#ffffff"
              strokeWidth={Math.max(1.5, grid.step * 0.16)}
            />
            <text
              x={drillCue.textX}
              y={drillCue.textY}
              textAnchor="middle"
              dominantBaseline="central"
              fill="#ffffff"
              style={{ fontSize: drillCue.fontSize, fontWeight: 700, fontFamily: "'Source Sans 3', system-ui, sans-serif" }}
            >
              {drillCueLabel}
            </text>
          </g>
        )}
      </svg>
      </div>
      </ChartFrame>
      {/* Not a live region: it changes on every pointer move. Keyboard and screen readers use the select and the table. */}
      <p className="stance-map-readout">
        {touch
          ? 'Tap a state to open its story, or choose one.'
          : hover
            ? `${readout(hover)}. ${hoverCode ? `${pickLabel(hoverCode)}.` : ''}`
            : 'Hover a state to hear what was said there; click it, or choose one, to open its story.'}
      </p>
      {passage && hover && hoverCode && (
        // Desktop only (#1277): under the legend, never over the map; one recording at a time.
        <QuoteCard
          className="map-hover-card"
          compact
          inlineVideo={inlineVideo}
          place={[passage.jurisdiction_name, passage.state_code].filter(Boolean).join(', ')}
          date={passage.meeting_date}
          quote={excerptAroundMark(passage.evidence ?? '')}
          meeting={passage.meeting_title}
          stanceNote={dataCenterQuoteNote(passage.ai_public_lean)}
          videoId={resolveVideoId(passage.video_id, passage.jump_url, passage.video_url)}
          startSeconds={passage.start_seconds ?? startFromUrl(passage.jump_url)}
          url={passage.jump_url ?? passage.video_url}
          speakerName={passage.speaker_display_name ?? null}
          role={passage.speaker_display_name ? passage.speaker_role ?? null : null}
        >
          {/* The same action as a click on the state (#1277). */}
          <button type="button" className="map-hover-open" onClick={() => pick(hover)}>
            {keyNav.keyed ? 'Press Enter to show it' : pickLabel(hoverCode)} <span aria-hidden="true">→</span>
          </button>
        </QuoteCard>
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
