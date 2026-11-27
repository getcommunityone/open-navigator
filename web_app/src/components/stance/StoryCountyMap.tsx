import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { COUNTIES_ALBERS_TOPO, albersPoint, bboxOf, dotsFor, featAt, fetchTopo, meetingColor, toFeats } from '../../lib/dotMatrix'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { HOUSE_THEME } from '../../utils/houseTheme'
import { dotSides, speakersOf, sumStances, type StanceCounts } from '../../utils/boxSplit'
import { BOX_COLORS, LEGEND_LABEL, LEGEND_STANCES, MEETING_GREYS, featPath, stanceLine } from '../home/StoryStatesMap'
import {
  PUBLIC_AGAINST_COLOR,
  PUBLIC_AGAINST_LABEL,
  hasDisagreement,
  leanFill,
  leanLine,
  type LeanCounts,
} from '../home/storyColors'
import { excerptAroundMark } from '../../lib/highlight'
import QuoteCard from './QuoteCard'
import { dataCenterQuoteNote } from '../../utils/topicPositions'
import { resolveVideoId, startFromUrl } from './quoteCardUtils'
import type { MapPassage } from './StoryDotMap'
import { isTouchOnly, prefersStillMedia } from '../../utils/touchOnly'
import { useMapKeyboard, westToEast } from '../../hooks/useMapKeyboard'

/** Meetings for one government in the scoped state (meeting-mentions `counts.by_place`, #1039). */
export interface PlaceCount extends LeanCounts {
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
    // #1117: Jev's public-against / disagreement meetings summed over the county's governments.
    const leans = new Map<string, { public_against_meetings: number; disagreement_meetings: number }>()
    for (const [id, ps] of byCounty) {
      const l = ps.reduce(
        (a, p) => ({
          public_against_meetings: a.public_against_meetings + Math.max(0, p.public_against_meetings || 0),
          disagreement_meetings: a.disagreement_meetings + Math.max(0, p.disagreement_meetings || 0),
        }),
        { public_against_meetings: 0, disagreement_meetings: 0 },
      )
      if (l.public_against_meetings > 0 || l.disagreement_meetings > 0) leans.set(id, l)
    }
    return { byCounty, counts, stances, leans, rings, unplaced }
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
  // Keyboard (#1146): one tab stop, the arrows move west to east between the counties with meetings (all, when none).
  const order = useMemo(() => {
    if (!grid || !placed) return []
    const withMeetings = westToEast(grid.dots, (i) => ((placed.counts.get(grid.dots[i]!.id) ?? 0) > 0 ? grid.dots[i]!.id : null))
    return withMeetings.length ? withMeetings : westToEast(grid.dots, (i) => grid.dots[i]!.id)
  }, [grid, placed])
  const touch = isTouchOnly()
  const keyNav = useMapKeyboard<string>({
    keys: order,
    active: hover,
    setActive: setHover,
    noun: 'county',
    describe: (id) => {
      const name = grid?.feats.find((f) => f.id === id)?.name ?? id
      const n = placed?.counts.get(id) ?? 0
      return `${/county|parish|borough|city/i.test(name) ? name : `${name} County`}: ${n ? plural(n) : 'no meetings on record'}.`
    },
  })

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

  const { byCounty, counts, stances, leans, rings, unplaced } = placed
  const max = Math.max(0, ...counts.values())
  // Home map colours (#1106): a side's colour, else grey by real meetings, else the empty colour.
  const colorFor = (i: number, n: number | undefined): string => {
    const side = sides[i]
    if (side) return BOX_COLORS[side]
    // #1117: no speakers on record but the AI reading found the public mostly opposed: the lighter red.
    return n && n > 0 ? leanFill(leans.get(grid.dots[i]!.id), meetingColor(n, max, MEETING_GREYS, BOX_COLORS.meetings)) : HOUSE_THEME.neutral
  }
  const leanCounties = [...leans].filter(([id, l]) => l.public_against_meetings > 0 && !stances.has(id)).length
  const disagreeCounties = new Set([...leans].filter(([, l]) => hasDisagreement(l)).map(([id]) => id))
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
    const lean = leanLine(leans.get(id))
    return `${countyLabel(id)}: ${plural(n)} (${parts.join(', ')})${st ? `; ${st}` : '; no stance on record'}.${lean ? ` ${lean}` : ''}`
  }

  // Only while a county is hovered, on a desktop: the newest passage from one of its governments, if the scope has one. A
  // phone has no card (#1277): a tap only selects the county (its outline and the line under the map).
  const hoverNames = new Set((hover ? byCounty.get(hover) ?? [] : []).map((p) => norm(p.jurisdiction_name)))
  const passage = hover && !touch ? (passages ?? []).find((m) => m.evidence && hoverNames.has(norm(m.jurisdiction_name))) : undefined
  const [bx0, by0, bx1, by1] = grid.bbox
  const hoverFeat = hover ? grid.feats.find((f) => f.id === hover) : undefined
  const inlineVideo = keyNav.keyed || prefersStillMedia() ? 'click' : 'autoplay'
  const hoverIn = (id: string) =>
    touch
      ? undefined
      : () => {
          keyNav.pointed()
          setHover(id)
        }

  const r = grid.step * 0.38
  const pad = 4
  const vb = `${bx0 - pad} ${by0 - pad} ${bx1 - bx0 + pad * 2} ${by1 - by0 + pad * 2}`
  // Town labels (#1115), in the Data Explorer's label style: each ring's government named beside it, largest meetings first,
  // skipping any label whose box would overlap one already placed. County governments have no ring; one is named at its
  // county's centre only when that spot is free, after every town (#1117), in the cartographic county style: small,
  // uppercase, letter-spaced, lighter ("MARICOPA COUNTY"). Sizes follow the grid step so the labels scale with the map.
  const labelSize = grid.step * 1.5
  const countySize = labelSize * 0.82
  const labels = (() => {
    const x0 = bx0 - pad
    const x1 = bx1 + pad
    const boxes: [number, number, number, number][] = []
    const free = (b: [number, number, number, number]) =>
      b[0] >= x0 && b[2] <= x1 && !boxes.some((o) => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1])
    const out: { key: string; x: number; y: number; anchor: 'start' | 'middle' | 'end'; text: string; county: string; ring: boolean }[] = []
    const cands = [
      ...rings.map((g) => ({ place: g.place, x: g.x, y: g.y, county: g.county, ring: true })),
      ...[...byCounty].flatMap(([county, ps]) => {
        const ds = grid.dots.filter((d) => d.id === county)
        if (!ds.length) return []
        const cx = ds.reduce((a, d) => a + d.x, 0) / ds.length
        const cy = ds.reduce((a, d) => a + d.y, 0) / ds.length
        return ps
          .filter((p) => p.jurisdiction_type === 'county' && p.geoid === county)
          .map((p) => ({ place: p, x: cx, y: cy, county, ring: false }))
      }),
    ].sort((a, b) => Number(b.ring) - Number(a.ring) || b.place.meetings - a.place.meetings)
    for (const c of cands) {
      // Shown as people say it (#1115): "Casa Grande", not "Casa Grande city" (the Data Explorer's rule). Only the Census's
      // lowercase suffix is dropped, so a name that ends in a capitalised word keeps it ("Garden City", #1117).
      const name = (c.place.jurisdiction_name ?? '').trim()
      const text = c.ring ? name.replace(/\s+(city|town|village|borough|CDP)$/, '') : name.toUpperCase()
      if (!text) continue
      // Uppercase with 0.08em letter-spacing runs wider per character than mixed-case town names.
      const w = c.ring ? text.length * labelSize * 0.55 : text.length * countySize * (0.68 + 0.08)
      const h = (c.ring ? labelSize : countySize) * 1.1
      const top = c.y - h / 2
      const gap = grid.step * 0.95
      const tries: { anchor: 'start' | 'middle' | 'end'; x: number; box: [number, number, number, number] }[] = c.ring
        ? [
            { anchor: 'start', x: c.x + gap, box: [c.x + gap, top, c.x + gap + w, top + h] },
            { anchor: 'end', x: c.x - gap, box: [c.x - gap - w, top, c.x - gap, top + h] },
          ]
        : [{ anchor: 'middle', x: c.x, box: [c.x - w / 2, top, c.x + w / 2, top + h] }]
      const hit = tries.find((t) => free(t.box))
      if (!hit) continue
      boxes.push(hit.box)
      out.push({ key: c.place.jurisdiction_id, x: hit.x, y: c.y, anchor: hit.anchor, text, county: c.county, ring: c.ring })
    }
    return out
  })()

  const listed = [...counts]
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1] || countyLabel(a[0]).localeCompare(countyLabel(b[0])))
  const states = Object.entries(STATE_CODE_TO_NAME)
    .filter(([c]) => FIPS_OF_CODE[c] && FIPS_OF_CODE[c] !== '72')
    .sort((a, b) => a[1].localeCompare(b[1]))
  const unplacedMeetings = unplaced.reduce((a, p) => a + p.meetings, 0)

  return (
    // Leaving the figure (map, lines and card), not moving between them, hides the card (#1277).
    <figure className="stance-map" aria-labelledby={labelledBy} onMouseLeave={() => setHover(null)} {...keyNav.stageProps}>
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
      <div className="stance-map-stage">
        {keyNav.sr}
        <svg
          viewBox={vb}
          className="stance-map-svg"
          data-map="county"
          aria-label={`Dot map of ${stateName}'s counties, split by speakers' stance where any are on record and otherwise shaded by meetings where a data center came up (the story is scoped to ${scopeLabel}). ${listed.length} ${listed.length === 1 ? 'county has' : 'counties have'} at least one.${leanCounties ? ` ${leanCounties} ${leanCounties === 1 ? 'county is' : 'counties are'} tinted light red where a reading of the meetings found the public mostly opposed.` : ''}${disagreeCounties.size ? ` ${disagreeCounties.size} ${disagreeCounties.size === 1 ? 'county is' : 'counties are'} where a reading of the meetings found officials sided against the public (see the data table).` : ''}`}
          {...keyNav.svgProps}
        >
          {grid.dots.map((d, i) => {
            const n = counts.get(d.id)
            const mine = !cityCounties || cityCounties.has(d.id)
            return (
              <circle
                key={i}
                data-box=""
                data-active={hover === d.id ? '' : undefined}
                cx={d.x}
                cy={d.y}
                r={n ? r : r * 0.55}
                fill={colorFor(i, n)}
                opacity={(hover && hover !== d.id) || !mine ? 0.3 : 1}
                style={{ cursor: 'pointer' }}
                onMouseEnter={hoverIn(d.id)}
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
              onMouseEnter={hoverIn(g.county)}
              onClick={() => setHover(g.county)}
            >
              <title>{`${g.place.jurisdiction_name ?? g.place.jurisdiction_id}: ${plural(g.place.meetings)}`}</title>
            </circle>
          ))}
          {/* County borders over the dots (#1117), like the home map's state outlines, so neighbouring counties read apart. */}
          <g fill="none" stroke="#57534e" strokeOpacity={0.45} strokeWidth={grid.step * 0.06} strokeLinejoin="round" pointerEvents="none">
            {grid.feats.map((f) => (
              <path key={f.id} d={featPath(f)} />
            ))}
          </g>
          {/* The hovered (tapped) county's outline, raised (#1277). */}
          {hoverFeat && (
            <path
              d={featPath(hoverFeat)}
              fill="none"
              stroke="#1c1917"
              strokeWidth={grid.step * 0.32}
              strokeLinejoin="round"
              pointerEvents="none"
              data-active-outline=""
            />
          )}
          <g className="stance-map-labels" pointerEvents="none" aria-hidden="true">
            {labels.map((l) => (
              <text
                key={l.key}
                x={l.x}
                y={l.y}
                textAnchor={l.anchor}
                dominantBaseline="central"
                opacity={hover && hover !== l.county ? 0.3 : 1}
                style={
                  l.ring
                    ? {
                        fontSize: labelSize,
                        fontFamily: 'inherit',
                        fontWeight: 600,
                        fill: '#0f172a',
                        stroke: '#ffffff',
                        strokeWidth: labelSize * 0.32,
                        strokeLinejoin: 'round',
                        paintOrder: 'stroke',
                      }
                    : {
                        fontSize: countySize,
                        fontFamily: 'inherit',
                        fontWeight: 500,
                        letterSpacing: '0.08em',
                        fill: '#78716c',
                        stroke: '#ffffff',
                        strokeWidth: countySize * 0.32,
                        strokeLinejoin: 'round',
                        paintOrder: 'stroke',
                      }
                }
              >
                {l.text}
              </text>
            ))}
          </g>
        </svg>
      </div>
      <p className="stance-map-readout">
        {hover ? readout(hover) : `${touch ? 'Tap' : 'Hover'} a county to see its count${touch ? '' : ' and hear what was said'}. Rings mark the cities, towns and school districts on record.`}
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
            {leanCounties > 0 && (
              <span className="stance-map-none">
                <span style={{ background: PUBLIC_AGAINST_COLOR }} /> {PUBLIC_AGAINST_LABEL}
              </span>
            )}
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
            {leans.size > 0
              ? ' Each meeting is read by a classifier from its transcript; these are not counted speakers. Only “the public mostly opposed” and “officials sided against the public” are shown.'
              : ''}
          </p>
        </>
      )}
      {unplacedMeetings > 0 && (
        <p className="stance-note">
          {plural(unplacedMeetings)} from {unplaced.map((p) => p.jurisdiction_name ?? p.jurisdiction_id).join(', ')} could not be placed in a
          county and {unplacedMeetings === 1 ? 'is' : 'are'} not shaded.
        </p>
      )}
      {passage && (
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
        />
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
                {leans.size > 0 && (
                  <>
                    <th scope="col">Public mostly opposed (meetings)</th>
                    <th scope="col">Officials sided against the public (meetings)</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {listed.map(([id, n]) => (
                <tr key={id}>
                  <td>{countyLabel(id)}</td>
                  <td>{fmt(n)}</td>
                  <td>{(byCounty.get(id) ?? []).map((p) => `${p.jurisdiction_name ?? p.jurisdiction_id} (${fmt(p.meetings)})`).join(', ')}</td>
                  {leans.size > 0 && (
                    <>
                      <td>{fmt(leans.get(id)?.public_against_meetings ?? 0)}</td>
                      <td>{fmt(leans.get(id)?.disagreement_meetings ?? 0)}</td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </details>
    </figure>
  )
}
