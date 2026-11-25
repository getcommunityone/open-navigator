import { useMemo, useState, type CSSProperties } from 'react'
import { useQuery } from '@tanstack/react-query'
import { COUNTIES_ALBERS_TOPO, STATES_ALBERS_TOPO, dotsFor, fetchTopo, toFeats } from '../lib/dotMatrix'
import { censusMetricRankDirection } from '../utils/censusDataDictionary'
import { staggerDelayMs } from '../utils/folioMotion'

interface Props {
  slug: string
  vintage: string
  /** state fips (2-digit) -> metric value */
  stateValue: (fips: string) => number | null
  /** state fips -> display name */
  stateName: (fips: string) => string
  /** normalised 0..1 for a state value (null = no data) */
  stateT: (fips: string) => number | null
  color: (t: number | null) => string
  fmt: (slug: string, v: number | null) => string
  /** drill state fips (from URL) */
  drill: string | null
  onDrill: (fips: string | null) => void
}

/**
 * Dot-matrix map: the country (or one state's counties) as a grid of dots clipped to its outline.
 * Each dot takes the colour of the area it sits in, so the map is a real choropleth drawn in dots.
 * Click a state to drill into its counties; use the breadcrumb to broaden back to the nation.
 */
export default function DotMatrixMap({ slug, vintage, stateValue, stateName, stateT, color, fmt, drill, onDrill }: Props) {
  const [hover, setHover] = useState<string | null>(null)
  const { data: statesTopo, isError: statesError } = useQuery({
    queryKey: ['us-atlas-states-albers'],
    queryFn: () => fetchTopo(STATES_ALBERS_TOPO),
    staleTime: 1000 * 60 * 60,
  })
  const { data: countiesTopo, isError: countiesError } = useQuery({
    queryKey: ['us-atlas-counties-albers'],
    queryFn: () => fetchTopo(COUNTIES_ALBERS_TOPO),
    enabled: !!drill,
    staleTime: 1000 * 60 * 60,
  })
  const { data: countyPayload } = useQuery({
    queryKey: ['census-county-metrics', vintage],
    queryFn: async (): Promise<{ values: Record<string, Record<string, number | string | null | undefined>> } | null> => {
      const r = await fetch(`/data/census-map/${vintage}/county_metrics.json`)
      return r.ok ? r.json() : null
    },
    enabled: !!drill && !!vintage,
    retry: false,
    staleTime: 1000 * 60 * 60,
  })

  const national = useMemo(() => {
    if (!statesTopo) return null
    const feats = toFeats(statesTopo, 'states').filter((f) => f.id !== '72')
    return { feats, ...dotsFor(feats, [0, 0, 975, 610], 105) }
  }, [statesTopo])

  const state = useMemo(() => {
    if (!drill || !countiesTopo) return null
    const feats = toFeats(countiesTopo, 'counties').filter((f) => f.id.startsWith(drill))
    if (!feats.length) return null
    const bbox: [number, number, number, number] = [
      Math.min(...feats.map((f) => f.bbox[0])),
      Math.min(...feats.map((f) => f.bbox[1])),
      Math.max(...feats.map((f) => f.bbox[2])),
      Math.max(...feats.map((f) => f.bbox[3])),
    ]
    return { feats, bbox, ...dotsFor(feats, bbox, 60) }
  }, [drill, countiesTopo])

  const countyVal = (gid: string): number | null => {
    const v = countyPayload?.values?.[gid]?.[slug]
    return typeof v === 'number' && Number.isFinite(v) ? v : null
  }
  const countyT = useMemo(() => {
    if (!state) return () => null
    const xs = state.feats.map((f) => countyVal(f.id)).filter((x): x is number => x != null)
    if (!xs.length) return () => null
    const lo = Math.min(...xs)
    const hi = Math.max(...xs)
    const flip = censusMetricRankDirection(slug) === 'lower'
    return (gid: string) => {
      const v = countyVal(gid)
      return v == null || hi === lo ? null : flip ? 1 - (v - lo) / (hi - lo) : (v - lo) / (hi - lo)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, countyPayload, slug])

  const inCounty = !!drill
  const model = inCounty ? state : national
  const scope = inCounty ? stateName(drill!) : 'United States'
  if (statesError || (inCounty && countiesError)) {
    return (
      <p className="folio-muted" role="status">
        No data available — the map shapes could not be loaded. The Tiles and Pivot layouts show the same values without a map.
      </p>
    )
  }
  if (!model) {
    return <p className="folio-muted">{inCounty && countiesTopo ? 'No data available — no county shapes for this state.' : 'Loading map…'}</p>
  }
  const bbox = inCounty ? (state as NonNullable<typeof state>).bbox : ([0, 0, 975, 610] as const)
  const pad = 6
  const vb = `${bbox[0] - pad} ${bbox[1] - pad} ${bbox[2] - bbox[0] + pad * 2} ${bbox[3] - bbox[1] + pad * 2}`
  const r = model.step * 0.4
  const nameOf = (id: string) => (inCounty ? model.feats.find((f) => f.id === id)?.name ?? id : stateName(id))
  const tOf = (id: string) => (inCounty ? countyT(id) : stateT(id))
  const valOf = (id: string) => (inCounty ? countyVal(id) : stateValue(id))
  const noCounty = inCounty && countyPayload === null

  return (
    <div>
      <nav className="mb-2 flex flex-wrap items-center gap-1 text-xs" style={{ color: 'var(--ink)' }} aria-label="Map scope">
        <button type="button" className={inCounty ? 'folio-link-btn' : 'folio-link-btn font-semibold'} onClick={() => onDrill(null)} disabled={!inCounty}>
          United States
        </button>
        {inCounty && (
          <>
            <span aria-hidden>›</span>
            <span className="font-semibold">{scope} · counties</span>
          </>
        )}
        <span className="folio-note ml-2">
          {inCounty ? 'One dot ≈ a patch of the state, coloured by its county (scaled within this state).' : 'Click a state, or choose one:'}
        </span>
        {!inCounty && (
          <select
            aria-label="Drill into a state's counties"
            className="folio-select"
            value=""
            onChange={(e) => e.target.value && onDrill(e.target.value)}
          >
            <option value="">State…</option>
            {[...model.feats]
              .map((f) => ({ id: f.id, name: stateName(f.id) }))
              .sort((a, b) => a.name.localeCompare(b.name))
              .map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
          </select>
        )}
      </nav>
      {noCounty && (
        <p className="folio-note mb-1" role="status">
          No data available — county_metrics.json for this vintage is not published, so the dots are gray.
        </p>
      )}
      <svg viewBox={vb} className="w-full" role="img" aria-label={`Dot-matrix map of ${scope}`} onMouseLeave={() => setHover(null)}>
        <g key={inCounty ? `c:${drill}` : 'us'}>
          {model.dots.map((d, i) => (
            <circle
              key={i}
              className="folio-svg-dot folio-pop"
              cx={d.x}
              cy={d.y}
              r={r}
              style={{
                fill: color(tOf(d.id)),
                opacity: hover && hover !== d.id ? 0.35 : 1,
                cursor: inCounty ? 'default' : 'pointer',
                ...({ '--delay': `${Math.round(staggerDelayMs((d.x - bbox[0]) / model.step, (d.y - bbox[1]) / model.step, (bbox[2] - bbox[0] + bbox[3] - bbox[1]) / model.step, 800))}ms` } as CSSProperties),
              }}
              onMouseEnter={() => setHover(d.id)}
              onClick={() => !inCounty && onDrill(d.id)}
            />
          ))}
        </g>
      </svg>
      <p className="folio-row-val mt-1 min-h-[1.25rem]" style={{ color: 'var(--ink)' }} aria-live="polite">
        {hover ? `${nameOf(hover)}: ${fmt(slug, valOf(hover))}` : ' '}
      </p>
    </div>
  )
}
