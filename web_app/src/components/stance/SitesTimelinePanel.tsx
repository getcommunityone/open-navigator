import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { SitesTimelineResponse, TimelineSite } from '../../api/sitesTimeline'
import { STATES_ALBERS_TOPO, NATIONAL_BBOX, albersPoint, bboxOf, fetchTopo, toFeats } from '../../lib/dotMatrix'
import { featPath } from '../home/StoryStatesMap'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'
import { GROUP_COLORS, HOUSE_THEME } from '../../utils/houseTheme'
import {
  PHASES,
  PHASE_LABEL,
  appearText,
  capacityText,
  frameLegend,
  operatingText,
  sitesInYear,
  stripColumns,
  timelineDisplay,
  timelineYears,
  undatedCaption,
  yearRow,
  type Phase,
} from '../../utils/siteTimeline'
import './SitesTimelinePanel.css'

const FIPS_OF_CODE: Record<string, string> = Object.fromEntries(Object.entries(STATE_FIPS_TO_CODE).map(([f, c]) => [c, f]))
const NEUTRAL = HOUSE_THEME.neutral ?? '#8a8f93'

/** One colour per phase; "proposed" (planned) is drawn outlined in its colour, never filled. */
const PHASE_COLOR: Record<Phase, string> = {
  operating: GROUP_COLORS[0]!,
  under_construction: GROUP_COLORS[1]!,
  planned: GROUP_COLORS[2]!,
  cancelled: NEUTRAL,
  no_longer_listed: NEUTRAL,
  status_not_published: NEUTRAL,
}

interface Props {
  res: SitesTimelineResponse | undefined
  /** The scope the sites really show (a city's state), for labels. */
  scopeLabel: string
  stateCode?: string
  /** The screen is on view: autoplay starts once per visit (never under reduced motion). */
  active: boolean
  reduced: boolean
}

const fmt = (n: number) => n.toLocaleString('en-US')

/**
 * The "Over time" screen's figure (#1348, #1428): a map of every data center site with coordinates. A site with a start
 * date appears in that year as a dot; a site with no start date appears in the year a source first listed it as a small
 * outlined square ("start date not on record"); a site with no date at all fades in at today. A year slider (autoplay from
 * the first year to the last projected one; step-through only under reduced motion), a legend that sums to the mapped sites
 * in the frame plus a "not mapped" line, a stacked strip of the API's per-year totals (undated sites as an outlined block,
 * never as growth), and a card for the site tapped. 1–5 sites are listed instead (utils/displayFit, the shared rule).
 */
export default function SitesTimelinePanel({ res, scopeLabel, stateCode, active, reduced }: Props) {
  const years = useMemo(() => timelineYears(res), [res])
  const current = Number.parseInt(res?.current_year ?? '', 10)
  const lastYear = years[years.length - 1]
  const firstYear = years[0]
  // At rest the map shows this year (or the last year on record before it).
  const restYear = years.length ? Math.min(lastYear!, Number.isFinite(current) ? Math.max(current, firstYear!) : lastYear!) : 0
  const [year, setYear] = useState(restYear)
  const [playing, setPlaying] = useState(false)
  const [picked, setPicked] = useState<TimelineSite | null>(null)
  useEffect(() => {
    setYear(restYear)
    setPicked(null)
  }, [restYear, res])

  // Autoplay once each time the screen comes on view, from the first year to the last.
  const played = useRef(false)
  useEffect(() => {
    if (!active) {
      played.current = false
      setPlaying(false)
      return
    }
    if (reduced || played.current || years.length < 2) return
    played.current = true
    setYear(firstYear!)
    setPlaying(true)
  }, [active, reduced, years.length, firstYear])
  useEffect(() => {
    if (!playing) return
    const tick = Math.max(160, Math.min(650, 7000 / Math.max(1, years.length)))
    const t = window.setInterval(() => {
      setYear((y) => {
        if (y >= lastYear!) {
          setPlaying(false)
          return y
        }
        return y + 1
      })
    }, tick)
    return () => window.clearInterval(t)
  }, [playing, years.length, lastYear])

  const topo = useQuery({ queryKey: ['us-atlas-states-albers'], queryFn: () => fetchTopo(STATES_ALBERS_TOPO), staleTime: 60 * 60_000 })
  const geo = useMemo(() => {
    if (!topo.data) return null
    const all = toFeats(topo.data, 'states').filter((f) => f.id !== '72')
    const fips = stateCode ? FIPS_OF_CODE[stateCode] : null
    const feats = fips ? all.filter((f) => f.id === fips) : all
    if (!feats.length) return null
    const bbox = fips ? bboxOf(feats) : NATIONAL_BBOX
    const pad = (bbox[2] - bbox[0]) * 0.04
    return { feats, vb: [bbox[0] - pad, bbox[1] - pad, bbox[2] - bbox[0] + 2 * pad, bbox[3] - bbox[1] + 2 * pad] as const }
  }, [topo.data, stateCode])

  const placed = useMemo(() => {
    const out: { site: TimelineSite; x: number; y: number }[] = []
    for (const s of res?.sites ?? []) {
      if (s.latitude == null || s.longitude == null) continue
      const p = albersPoint(s.longitude, s.latitude)
      if (p) out.push({ site: s, x: p[0], y: p[1] })
    }
    return out
  }, [res])
  const today = Number.isFinite(current) ? current : null
  const inYear = useMemo(() => sitesInYear(res?.sites ?? [], year, today), [res, year, today])
  const atYear = useMemo(() => {
    const byId = new Map(inYear.map((s) => [s.site.data_center_site_id, s]))
    return placed.flatMap((p) => {
      const s = byId.get(p.site.data_center_site_id)
      return s ? [{ ...p, phase: s.phase, isNew: s.isNew, undated: s.undated }] : []
    })
  }, [placed, inYear])
  const legend = useMemo(() => frameLegend(inYear), [inYear])
  const columns = useMemo(() => stripColumns(res), [res])

  const display = timelineDisplay(res)
  const note = undatedCaption(res, year)
  const source = (
    <p className="dc-tl-source">
      Sources:{' '}
      <a href="https://epoch.ai/data/data-centers" target="_blank" rel="noopener noreferrer">
        Epoch AI
      </a>{' '}
      and the{' '}
      <a href="https://suedatacenters.org/data-centers/data" target="_blank" rel="noopener noreferrer">
        US Data Center Registry
      </a>{' '}
      (CC BY 4.0).
    </p>
  )

  if (!res) return <p className="dc-tl-status">Loading data center sites…</p>
  if (!res.available) return <p className="dc-tl-status">Data center site dates aren't available right now.</p>
  if (display === 'empty') {
    return (
      <div className="dc-tl" data-display="empty">
        <p className="dc-tl-status">No data center site in {scopeLabel === 'National' ? 'the country' : scopeLabel} is on record.</p>
        {source}
      </div>
    )
  }
  if (display === 'list') {
    return (
      <div className="dc-tl" data-display="list">
        <ul className="stance-fit-list">
          {(res.sites ?? []).map((s) => (
            <li key={s.data_center_site_id}>
              {s.source_url ? (
                <a href={s.source_url} target="_blank" rel="noopener noreferrer">
                  {s.site_name}
                </a>
              ) : (
                <span>{s.site_name}</span>
              )}
              <span className="stance-fit-meta">{[PHASE_LABEL[(s.status as Phase) ?? 'status_not_published'], appearText(s), s.source_name].join(' · ')}</span>
            </li>
          ))}
        </ul>
        {source}
      </div>
    )
  }

  const row = yearRow(res, year)
  const isFuture = Boolean(row?.is_future)
  const r = geo ? geo.vb[2] / (stateCode ? 70 : 150) : 3
  const maxTotal = Math.max(1, ...columns.map((c) => c.total))

  return (
    <div className="dc-tl" data-display="animated" data-future={isFuture ? '' : undefined}>
      <div className="dc-tl-map">
        {geo ? (
          <svg viewBox={geo.vb.join(' ')} role="img" aria-label={`Map of ${fmt(atYear.length)} mapped data center sites on record in ${scopeLabel === 'National' ? 'the country' : scopeLabel} by ${year}`}>
            {/* The year on the map itself, so the map and its year are one block. */}
            <text className="dc-tl-year" x={geo.vb[0] + geo.vb[2] * 0.98} y={geo.vb[1] + geo.vb[2] * 0.1} textAnchor="end" fontSize={geo.vb[2] * 0.1} aria-hidden="true">
              {year}
            </text>
            {isFuture && (
              <text className="dc-tl-projected" x={geo.vb[0] + geo.vb[2] * 0.98} y={geo.vb[1] + geo.vb[2] * 0.15} textAnchor="end" fontSize={geo.vb[2] * 0.035} aria-hidden="true">
                PROJECTED
              </text>
            )}
            <g className="dc-tl-land">
              {geo.feats.map((f) => (
                <path key={f.id} d={featPath(f)} />
              ))}
            </g>
            <g>
              {atYear.map((d) => {
                const proposed = d.phase === 'planned'
                const isPicked = picked?.data_center_site_id === d.site.data_center_site_id
                const pick = () => setPicked(d.site)
                const onKey = (e: KeyboardEvent) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    pick()
                  }
                }
                if (d.undated) {
                  // Start date not on record: a small outlined square, so the site is on the map but not placed as an opening.
                  const side = (isPicked ? r * 1.6 : r) * 1.3
                  return (
                    <rect
                      key={d.site.data_center_site_id}
                      className={`dc-tl-dot dc-tl-sq${d.isNew && !reduced ? ' is-fade' : ''}${isPicked ? ' is-picked' : ''}`}
                      x={d.x - side / 2}
                      y={d.y - side / 2}
                      width={side}
                      height={side}
                      fill="none"
                      stroke={PHASE_COLOR[d.phase]}
                      strokeWidth={r * 0.32}
                      strokeDasharray={proposed ? `${r * 0.5} ${r * 0.35}` : undefined}
                      onClick={pick}
                      tabIndex={stateCode ? 0 : -1}
                      role="button"
                      aria-label={`${d.site.site_name}: ${PHASE_LABEL[d.phase]}, start date not on record`}
                      onKeyDown={onKey}
                    />
                  )
                }
                return (
                  <circle
                    key={d.site.data_center_site_id}
                    className={`dc-tl-dot${d.isNew && !reduced ? ' is-new' : ''}${isPicked ? ' is-picked' : ''}`}
                    cx={d.x}
                    cy={d.y}
                    r={isPicked ? r * 1.6 : r}
                    fill={proposed ? 'var(--paper, #fff)' : PHASE_COLOR[d.phase]}
                    stroke={PHASE_COLOR[d.phase]}
                    strokeWidth={proposed ? r * 0.55 : r * 0.25}
                    strokeDasharray={proposed ? `${r * 0.7} ${r * 0.45}` : undefined}
                    onClick={pick}
                    tabIndex={stateCode ? 0 : -1}
                    role="button"
                    aria-label={`${d.site.site_name}: ${PHASE_LABEL[d.phase]}`}
                    onKeyDown={onKey}
                  />
                )
              })}
            </g>
          </svg>
        ) : topo.isError ? (
          <p className="dc-tl-status">The map could not be loaded right now.</p>
        ) : (
          <div className="dc-tl-map-skeleton" aria-label="Loading the map" />
        )}
      </div>

      {/* The counts sit under the map: on a phone the map is the panel's first block, so it stays in view (useScreenFit). */}
      <div className="dc-tl-head">
        <span className="folio-sr-only" aria-live={playing ? 'off' : 'polite'}>
          {year}
          {isFuture ? ', projected' : ''}
        </span>
        <ul className="dc-tl-counts" aria-label={`Mapped sites on record by ${year}: ${fmt(legend.mapped)}`} data-mapped={legend.mapped}>
          {PHASES.filter((p) => legend.byPhase[p] > 0).map((p) => (
            <li key={p} data-phase={p} data-count={legend.byPhase[p]}>
              <span className="dc-tl-key" style={p === 'planned' ? { borderColor: PHASE_COLOR[p] } : { background: PHASE_COLOR[p] }} aria-hidden="true" />
              {PHASE_LABEL[p]} <strong>{fmt(legend.byPhase[p])}</strong>
            </li>
          ))}
          {legend.undatedMapped > 0 && (
            <li data-key="undated" data-count={legend.undatedMapped}>
              <span className="dc-tl-key dc-tl-key-sq" aria-hidden="true" />
              of these, start date not on record <strong>{fmt(legend.undatedMapped)}</strong>
            </li>
          )}
          {legend.notMapped > 0 && (
            <li data-key="not-mapped" data-count={legend.notMapped}>
              Not mapped <strong>{fmt(legend.notMapped)}</strong>
            </li>
          )}
        </ul>
      </div>

      <div className="dc-tl-controls">
        {!reduced && (
          <button
            type="button"
            className="dc-tl-btn"
            onClick={() => {
              if (playing) setPlaying(false)
              else {
                if (year >= lastYear!) setYear(firstYear!)
                setPlaying(true)
              }
            }}
            aria-label={playing ? 'Pause' : 'Play the years'}
          >
            {playing ? '❚❚' : '▶'}
          </button>
        )}
        <button type="button" className="dc-tl-btn" onClick={() => (setPlaying(false), setYear((y) => Math.max(firstYear!, y - 1)))} disabled={year <= firstYear!} aria-label="Previous year">
          ‹
        </button>
        <input
          type="range"
          className="dc-tl-range"
          min={firstYear}
          max={lastYear}
          step={1}
          value={year}
          onChange={(e) => {
            setPlaying(false)
            setYear(Number(e.target.value))
          }}
          aria-label="Year"
          aria-valuetext={`${year}${isFuture ? ', projected' : ''}`}
        />
        <button type="button" className="dc-tl-btn" onClick={() => (setPlaying(false), setYear((y) => Math.min(lastYear!, y + 1)))} disabled={year >= lastYear!} aria-label="Next year">
          ›
        </button>
      </div>

      <svg className="dc-tl-strip" viewBox={`0 0 ${years.length * 10} 36`} preserveAspectRatio="none" role="img" aria-label={`Running total of sites on record per year, ${firstYear} to ${lastYear}; sites with no start date drawn as an outlined block`}>
        <defs>
          <pattern id="dc-tl-hatch" width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="3" height="3" fill="var(--paper, #fff)" />
            <line x1="0" y1="0" x2="0" y2="3" stroke={PHASE_COLOR.planned} strokeWidth="1.6" />
          </pattern>
        </defs>
        {columns.map((c, i) => {
          let top = 36
          const yv = c.year
          const uh = (34 * c.undated) / maxTotal
          return (
            <g key={yv} onClick={() => (setPlaying(false), setYear(yv))} opacity={c.isFuture ? 0.6 : 1} className={yv === year ? 'is-year' : undefined}>
              <rect x={i * 10} y={0} width={10} height={36} fill="transparent" />
              {PHASES.map((p) => {
                const n = c.dated[p]
                if (!n) return null
                const h = (34 * n) / maxTotal
                top -= h
                return <rect key={p} x={i * 10 + 1} y={top} width={8} height={h} fill={p === 'planned' ? 'url(#dc-tl-hatch)' : PHASE_COLOR[p]} />
              })}
              {c.undated > 0 && (
                <rect className="dc-tl-strip-undated" x={i * 10 + 1.3} y={top - uh + 0.3} width={7.4} height={Math.max(0, uh - 0.6)} fill="none" stroke={NEUTRAL} strokeWidth="0.6" />
              )}
              {yv === year && <rect x={i * 10 + 0.3} y={0.3} width={9.4} height={35.4} fill="none" stroke="var(--ink, #222)" strokeWidth="0.6" />}
            </g>
          )
        })}
      </svg>
      <p className="dc-tl-axis">
        <span>{firstYear}</span>
        {Number.isFinite(current) && lastYear! > current && <span className="dc-tl-axis-future">after {current}: projected</span>}
        <span>{lastYear}</span>
      </p>

      {picked && (
        <div className="dc-tl-card" role="dialog" aria-label={picked.site_name}>
          <button type="button" className="dc-tl-card-close" onClick={() => setPicked(null)} aria-label="Close">
            ×
          </button>
          <p className="dc-tl-card-name">{picked.site_name}</p>
          <p className="dc-tl-card-meta">
            {[picked.operator ?? picked.owner, `Status today: ${PHASE_LABEL[(picked.status as Phase) ?? 'status_not_published']}`].filter(Boolean).join(' · ')}
          </p>
          <p className="dc-tl-card-meta">{[appearText(picked), operatingText(picked), capacityText(picked)].filter(Boolean).join(' · ')}</p>
          <p className="dc-tl-card-meta">
            Source:{' '}
            {picked.source_url ? (
              <a href={picked.source_url} target="_blank" rel="noopener noreferrer">
                {picked.source_name}
              </a>
            ) : (
              picked.source_name
            )}
          </p>
        </div>
      )}

      <p className="dc-tl-note" data-undated={row?.undated ?? 0}>
        {[note, legend.notMapped > 0 ? `${fmt(legend.notMapped)} ${legend.notMapped === 1 ? 'site has' : 'sites have'} no map location and ${legend.notMapped === 1 ? 'is' : 'are'} counted only.` : null]
          .filter(Boolean)
          .join(' ')}{' '}
        Dashed outlines are proposed. Tap a site for its record.
      </p>
      {source}
    </div>
  )
}
