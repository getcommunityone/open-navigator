import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { COUNTIES_ALBERS_TOPO, albersPoint, bboxOf, dotsFor, featAt, fetchTopo, meetingColor, toFeats } from '../../lib/dotMatrix'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { HOUSE_THEME } from '../../utils/houseTheme'
import { dotSides, speakersOf, sumStances, type StanceCounts } from '../../utils/boxSplit'
import { BOX_COLORS, LEGEND_LABEL, LEGEND_STANCES, MEETING_GREYS, stanceLine } from '../home/StoryStatesMap'
import { excerptAroundMark } from '../../lib/highlight'
import QuoteCard from './QuoteCard'
import { resolveVideoId, startFromUrl } from './quoteCardUtils'
import type { MapPassage } from './StoryDotMap'
import { isTouchOnly } from '../../utils/touchOnly'

/** Meetings for one government in the scoped state (meeting-mentions `counts.by_place`, #1039). */
export interface PlaceCount {
  jurisdiction_id: string
  jurisdiction_name?: string | null
  jurisdiction_type?: string | null
  geoid?: string | null
  latitude?: number | null
  longitude?: number | null
  meetings: number
  /** Real speaker sums for this government's meetings (#1106); 0 or missing when none are on record. */
  speakers_for?: number
  speakers_against?: number
  speakers_question?: number
  speakers_neutral?: number
}

interface Props {
  stateCode: string
  /** The city the story is scoped to, if any: the county holding it stands out. */
  scopeCity?: string | null
  /** The scope label, for the figure's accessible name. */
  scopeLabel: string
  byPlace: PlaceCount[]
  /** Narrow the story to another state, or broaden it to the whole country (null). */
  onPickState: (stateCode: string | null) => void
  labelledBy?: string
  /** The scope's meeting passages, newest first. One is quoted while a county is hovered; nothing at rest (#1002). */
  passages?: MapPassage[] | null
}

const fmt = (n: number) => n.toLocaleString('en-US')
const plural = (n: number) => `${fmt(n)} ${n === 1 ? 'meeting' : 'meetings'}`
const FIPS_OF_CODE: Record<string, string> = Object.fromEntries(Object.entries(STATE_FIPS_TO_CODE).map(([f, c]) => [c, f]))
const norm = (s?: string | null) => (s ?? '').trim().toLowerCase()

/**
 * The Where? map at state scope (#1039), like the Census map's state drill-down: the state's counties as a grid of dots, in the
 * home box map's colours (#1106). Where its governments have speakers on record, a county's dots are split in bands by the real
 * counts of those who spoke against, for, asked a question or took no side; a county with meetings but no stance is grey, light
 * to dark by its real meeting count; a county with none stays the empty colour. A county government counts by its geoid; a
 * city, town or school district is placed in the county its coordinates fall in, and drawn as a ring. United States broadens
 * back to the national map.
 */
export default function StoryCountyMap({ stateCode, scopeCity = null, scopeLabel, byPlace, onPickState, labelledBy, passages }: Props) {
  const [hover, setHover] = useState<string | null>(null)
  const stateFips = FIPS_OF_CODE[stateCode] ?? null
  const stateName = STATE_CODE_TO_NAME[stateCode] ?? stateCode
  const { data: topo, isError } = useQuery({
    queryKey: ['us-atlas-counties-albers'],
    queryFn: () => fetchTopo(COUNTIES_ALBERS_TOPO),
    staleTime: 1000 * 60 * 60,
  })

  const grid = useMemo(() => {
    if (!topo || !stateFips) return null
    const feats = toFeats(topo, 'counties').filter((f) => f.id.startsWith(stateFips))
    if (!feats.length) return null
    const bbox = bboxOf(feats)
    return { feats, bbox, ...dotsFor(feats, bbox, 60) }
  }, [topo, stateFips])

  // Each government's county, and its ring position when it isn't a county itself.
  const placed = useMemo(() => {
    if (!grid) return null
    const ids = new Set(grid.feats.map((f) => f.id))
    const byCounty = new Map<string, PlaceCount[]>()
    const rings: { x: number; y: number; place: PlaceCount; county: string }[] = []
    const unplaced: PlaceCount[] = []
    for (const p of byPlace) {
      let county: string | null = null
      let pt: [number, number] | null = null
      if (p.jurisdiction_type === 'county' && p.geoid && ids.has(p.geoid)) county = p.geoid
      else if (p.latitude != null && p.longitude != null) {
        pt = albersPoint(p.longitude, p.latitude)
        county = pt ? featAt(pt[0], pt[1], grid.feats)?.id ?? null : null
      }
      if (!county) {
        unplaced.push(p)
        continue
      }
      byCounty.set(county, [...(byCounty.get(county) ?? []), p])
      if (pt) rings.push({ x: pt[0], y: pt[1], place: p, county })
    }
    const counts = new Map([...byCounty].map(([id, ps]) => [id, ps.reduce((a, p) => a + p.meetings, 0)]))
    const stances = new Map<string, StanceCounts>()
    for (const [id, ps] of byCounty) {
      const st = sumStances(ps)
      if (speakersOf(st) > 0) stances.set(id, st)
    }
    return { byCounty, counts, stances, rings, unplaced }
  }, [grid, byPlace])

  // Each dot's side (grid order): a county with speakers on record is banded left to right by its real counts, as on the home map.
  const sides = useMemo(() => {
    if (!grid || !placed) return null
    const idx = new Map<string, number[]>()
    grid.dots.forEach((d, i) => idx.set(d.id, [...(idx.get(d.id) ?? []), i]))
    const out = new Array<ReturnType<typeof dotSides>[number]>(grid.dots.length).fill(null)
    for (const [id, st] of placed.stances) {
      const is = idx.get(id) ?? []
      dotSides(is.map((i) => grid.dots[i]!), st).forEach((side, k) => {
        out[is[k]!] = side
      })
    }
    return out
  }, [grid, placed])

  if (isError) {
    return (
      <p className="stance-nodata" role="status">
        The county shapes could not be loaded. The counts below still show every place.
      </p>
    )
  }
  if (!grid || !placed || !sides) {
    return (
      <p className="stance-note" role="status">
        {topo && !grid ? `No county shapes for ${stateName}.` : 'Loading the map…'}
      </p>
    )
  }

  const { byCounty, counts, stances, rings, unplaced } = placed
  const max = Math.max(0, ...counts.values())
  // Home map colours (#1106): a side's colour, else grey by real meetings, else the empty colour.
  const colorFor = (i: number, n: number | undefined): string => {
    const side = sides[i]
    if (side) return BOX_COLORS[side]
    return n && n > 0 ? meetingColor(n, max, MEETING_GREYS, BOX_COLORS.meetings) : HOUSE_THEME.neutral
  }
  const speakersTotal = [...stances.values()].reduce((a, st) => a + speakersOf(st), 0)
  const nameOf = (id: string) => grid.feats.find((f) => f.id === id)?.name ?? id
  const countyLabel = (id: string) => {
    const n = nameOf(id)
    return /county|parish|borough|city/i.test(n) ? n : `${n} County`
  }
  const cityCounties = scopeCity
    ? new Set([...byCounty].filter(([, ps]) => ps.some((p) => norm(p.jurisdiction_name).includes(norm(scopeCity)))).map(([id]) => id))
    : null
  const readout = (id: string) => {
    const n = counts.get(id) ?? 0
    if (!n) return `${countyLabel(id)}: no meetings on record`
    const parts = (byCounty.get(id) ?? []).map((p) => `${p.jurisdiction_name ?? p.jurisdiction_id} ${fmt(p.meetings)}`)
    const st = stanceLine(stances.get(id))
    return `${countyLabel(id)}: ${plural(n)} (${parts.join(', ')})${st ? `; ${st}` : '; no stance on record'}`
  }

  // Only while a county is hovered: the newest passage from one of its governments, if the scope has one.
  const hoverNames = new Set((hover ? byCounty.get(hover) ?? [] : []).map((p) => norm(p.jurisdiction_name)))
  const passage = hover ? (passages ?? []).find((m) => m.evidence && hoverNames.has(norm(m.jurisdiction_name))) : undefined
  const [bx0, by0, bx1, by1] = grid.bbox
  const hoverDots = hover ? grid.dots.filter((d) => d.id === hover) : []
  const hoverX = hoverDots.length ? (hoverDots.reduce((a, d) => a + d.x, 0) / hoverDots.length - bx0) / (bx1 - bx0) : 0
  const cardSide = hoverX < 0.5 ? 'stance-map-card is-right' : 'stance-map-card'

  const r = grid.step * 0.38
  const pad = 4
  const vb = `${bx0 - pad} ${by0 - pad} ${bx1 - bx0 + pad * 2} ${by1 - by0 + pad * 2}`
  const listed = [...counts]
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1] || countyLabel(a[0]).localeCompare(countyLabel(b[0])))
  const states = Object.entries(STATE_CODE_TO_NAME)
    .filter(([c]) => FIPS_OF_CODE[c] && FIPS_OF_CODE[c] !== '72')
    .sort((a, b) => a[1].localeCompare(b[1]))
  const unplacedMeetings = unplaced.reduce((a, p) => a + p.meetings, 0)

  return (
    <figure className="stance-map" aria-labelledby={labelledBy}>
      <figcaption className="stance-map-head">
        <span>
          Meetings where a data center came up, by county · {stateName}
          {scopeCity ? ` (the county containing ${scopeCity} highlighted)` : ''}
        </span>
        <span className="stance-map-controls">
          <button type="button" className="folio-link-btn" onClick={() => onPickState(null)}>
            United States
          </button>
          <select aria-label="Show one state" className="folio-select" value={stateCode} onChange={(e) => onPickState(e.target.value || null)}>
            <option value="">All states</option>
            {states.map(([c, n]) => (
              <option key={c} value={c}>
                {n}
              </option>
            ))}
          </select>
        </span>
      </figcaption>
      <div className="stance-map-stage" onMouseLeave={() => setHover(null)}>
        <svg
          viewBox={vb}
          className="stance-map-svg"
          role="img"
          aria-label={`Dot map of ${stateName}'s counties, split by speakers' stance where any are on record and otherwise shaded by meetings where a data center came up (the story is scoped to ${scopeLabel}). ${listed.length} ${listed.length === 1 ? 'county has' : 'counties have'} at least one.`}
        >
          {grid.dots.map((d, i) => {
            const n = counts.get(d.id)
            const mine = !cityCounties || cityCounties.has(d.id)
            return (
              <circle
                key={i}
                cx={d.x}
                cy={d.y}
                r={n ? r : r * 0.55}
                fill={colorFor(i, n)}
                opacity={(hover && hover !== d.id) || !mine ? 0.3 : 1}
                onMouseEnter={() => setHover(d.id)}
                onClick={() => setHover(d.id)}
              />
            )
          })}
          {rings.map((g) => (
            <circle
              key={g.place.jurisdiction_id}
              className="stance-map-place"
              cx={g.x}
              cy={g.y}
              r={grid.step * 0.7}
              fill="none"
              stroke={HOUSE_THEME.ramp[5] ?? 'currentColor'}
              strokeWidth={grid.step * 0.18}
              opacity={hover && hover !== g.county ? 0.3 : 1}
              onMouseEnter={() => setHover(g.county)}
              onClick={() => setHover(g.county)}
            >
              <title>{`${g.place.jurisdiction_name ?? g.place.jurisdiction_id}: ${plural(g.place.meetings)}`}</title>
            </circle>
          ))}
        </svg>
        {passage && (
          <QuoteCard
            className={cardSide}
            place={[passage.jurisdiction_name, passage.state_code].filter(Boolean).join(', ')}
            date={passage.meeting_date}
            quote={excerptAroundMark(passage.evidence ?? '')}
            meeting={passage.meeting_title}
            videoId={resolveVideoId(passage.video_id, passage.jump_url, passage.video_url)}
            startSeconds={passage.start_seconds ?? startFromUrl(passage.jump_url)}
            url={passage.jump_url ?? passage.video_url}
          />
        )}
      </div>
      <p className="stance-map-readout">
        {hover ? readout(hover) : `${isTouchOnly() ? 'Tap' : 'Hover'} a county to see its count. Rings mark the cities, towns and school districts on record.`}
      </p>
      {max > 0 && (
        <>
          <div className="stance-map-legend" aria-hidden="true">
            {stances.size > 0 &&
              LEGEND_STANCES.map((k) => (
                <span key={k} className="stance-map-none">
                  <span style={{ background: BOX_COLORS[k] }} /> {LEGEND_LABEL[k]}
                </span>
              ))}
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginLeft: 8 }}>
              <span className="stance-map-ramp">
                <span style={{ background: MEETING_GREYS[2] }} />
              </span>
              Meetings, no stance on record (darker = more meetings)
            </span>
          </div>
          <p className="stance-note">
            {stances.size > 0
              ? `Split by ${fmt(speakersTotal)} ${speakersTotal === 1 ? 'speaker' : 'speakers'} on record in ${fmt(stances.size)} ${stances.size === 1 ? 'county' : 'counties'}; other counties show meetings only.`
              : `No speaker positions on record in ${stateName} yet; counties show meetings only.`}
          </p>
        </>
      )}
      {unplacedMeetings > 0 && (
        <p className="stance-note">
          {plural(unplacedMeetings)} from {unplaced.map((p) => p.jurisdiction_name ?? p.jurisdiction_id).join(', ')} could not be placed in a
          county and {unplacedMeetings === 1 ? 'is' : 'are'} not shaded.
        </p>
      )}
      <details className="stance-map-table">
        <summary>Show data table</summary>
        {listed.length === 0 ? (
          <p className="stance-note">No meetings on record.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th scope="col">County</th>
                <th scope="col">Meetings</th>
                <th scope="col">Governments</th>
              </tr>
            </thead>
            <tbody>
              {listed.map(([id, n]) => (
                <tr key={id}>
                  <td>{countyLabel(id)}</td>
                  <td>{fmt(n)}</td>
                  <td>{(byCounty.get(id) ?? []).map((p) => `${p.jurisdiction_name ?? p.jurisdiction_id} (${fmt(p.meetings)})`).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </details>
    </figure>
  )
}
