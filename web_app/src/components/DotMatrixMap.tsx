import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { geoPath } from 'd3-geo'
import { feature } from 'topojson-client'
import { censusMetricRankDirection } from '../utils/censusDataDictionary'

const STATES_ALBERS_TOPO = 'https://cdn.jsdelivr.net/npm/us-atlas@3/states-albers-10m.json'
const COUNTIES_ALBERS_TOPO = 'https://cdn.jsdelivr.net/npm/us-atlas@3/counties-albers-10m.json'

type Ring = number[][]
interface Feat {
  id: string
  name: string
  polys: Ring[][] // polygon -> rings
  bbox: [number, number, number, number]
}
interface Dot {
  x: number
  y: number
  id: string
}

const inRing = (x: number, y: number, ring: Ring): boolean => {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]!
    const [xj, yj] = ring[j]!
    if (yi > y !== yj > y && x < ((xj! - xi!) * (y - yi!)) / (yj! - yi!) + xi!) inside = !inside
  }
  return inside
}
const inFeat = (x: number, y: number, f: Feat): boolean => {
  const [x0, y0, x1, y1] = f.bbox
  if (x < x0 || x > x1 || y < y0 || y > y1) return false
  return f.polys.some((rings) => rings.reduce((n, r) => n + (inRing(x, y, r) ? 1 : 0), 0) % 2 === 1)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toFeats(topo: any, objName: string): Feat[] {
  const fc = feature(topo, topo.objects[objName]) as unknown as {
    features: { id?: string | number; properties?: { name?: string }; geometry: { type: string; coordinates: unknown } | null }[]
  }
  const path = geoPath()
  return fc.features
    .filter((f) => f.geometry)
    .map((f) => {
      const g = f.geometry!
      const polys = (g.type === 'Polygon' ? [g.coordinates] : g.coordinates) as Ring[][]
      const b = path.bounds(f as never)
      return { id: String(f.id ?? '').padStart(g.type ? (objName === 'states' ? 2 : 5) : 2, '0'), name: f.properties?.name ?? '', polys, bbox: [b[0]![0], b[0]![1], b[1]![0], b[1]![1]] as [number, number, number, number] }
    })
}

function dotsFor(feats: Feat[], bbox: [number, number, number, number], cols: number): { dots: Dot[]; step: number } {
  const step = (bbox[2] - bbox[0]) / cols
  const dots: Dot[] = []
  for (let y = bbox[1] + step / 2; y < bbox[3]; y += step) {
    for (let x = bbox[0] + step / 2; x < bbox[2]; x += step) {
      const hit = feats.find((f) => inFeat(x, y, f))
      if (hit) dots.push({ x, y, id: hit.id })
    }
  }
  return { dots, step }
}

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
  const { data: statesTopo } = useQuery({
    queryKey: ['us-atlas-states-albers'],
    queryFn: async () => (await fetch(STATES_ALBERS_TOPO)).json(),
    staleTime: 1000 * 60 * 60,
  })
  const { data: countiesTopo } = useQuery({
    queryKey: ['us-atlas-counties-albers'],
    queryFn: async () => (await fetch(COUNTIES_ALBERS_TOPO)).json(),
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
  if (!model) {
    return <p className="p-2 text-xs text-slate-600">{inCounty && countiesTopo ? 'No data available — no county shapes for this state.' : 'Loading map…'}</p>
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
      <nav className="mb-1 flex flex-wrap items-center gap-1 text-xs text-slate-700" aria-label="Map scope">
        <button type="button" className={inCounty ? 'text-teal-800 hover:underline' : 'font-semibold'} onClick={() => onDrill(null)} disabled={!inCounty}>
          United States
        </button>
        {inCounty && (
          <>
            <span aria-hidden>›</span>
            <span className="font-semibold">{scope} · counties</span>
          </>
        )}
        <span className="ml-2 text-slate-500">{inCounty ? 'One dot ≈ a patch of the state, coloured by its county.' : 'Click a state to drill into its counties.'}</span>
      </nav>
      {noCounty && (
        <p className="mb-1 text-xs text-slate-600" role="status">
          No data available — county_metrics.json for this vintage is not published, so the dots are gray.
        </p>
      )}
      <svg viewBox={vb} className="w-full" role="img" aria-label={`Dot-matrix map of ${scope}`} onMouseLeave={() => setHover(null)}>
        {model.dots.map((d, i) => (
          <circle
            key={i}
            cx={d.x}
            cy={d.y}
            r={r}
            fill={color(tOf(d.id))}
            opacity={hover && hover !== d.id ? 0.35 : 1}
            style={{ cursor: inCounty ? 'default' : 'pointer' }}
            onMouseEnter={() => setHover(d.id)}
            onClick={() => !inCounty && onDrill(d.id)}
          />
        ))}
      </svg>
      <p className="mt-1 min-h-[1.25rem] text-xs text-slate-800" aria-live="polite">
        {hover ? `${nameOf(hover)}: ${fmt(slug, valOf(hover))}` : ' '}
      </p>
    </div>
  )
}
