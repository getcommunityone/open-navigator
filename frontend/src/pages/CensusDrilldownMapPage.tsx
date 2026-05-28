// @ts-nocheck — Census utility functions and react-router types are loose; this file
// follows the same convention as CensusMapPage.tsx.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { feature as topoFeature } from 'topojson-client'
import { geoCentroid, geoContains } from 'd3-geo'
import {
  ArrowLeftIcon,
  PauseIcon,
  PlayIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import {
  CENSUS_SCALES,
  formatMetricValueCompact,
  formatMetricValueDisplay,
  minMaxExtent,
  quantileExtent,
  type CensusScaleId,
} from '../utils/censusMapTransforms'
import {
  type CensusValueMode,
  displayValueForMode,
  nationalBaselineWithFallback,
  pctChangeBetween,
  prevVintageCalendarYearsBack,
  prevVintageInList,
  trendCell,
} from '../utils/censusMapValueMode'
import {
  censusMetricFullHelp,
  censusMetricRankDirection,
  CENSUS_MAP_UI_HELP,
  CENSUS_EXPLORER_HIDDEN_METRIC_SLUGS,
  censusChoroLegendSemantics,
  censusMapShowOfficialCensusLabel,
} from '../utils/censusDataDictionary'
import { ringsOfGeom, ringsOverlap } from '../utils/ringOverlap'
import { ChoroplethLegend, BubbleLegend } from '../components/CensusMapLegends'
import { InfoHelpTrigger } from '../components/InfoHelpTrigger'
import MapAddressSearch, { type MapAddressResult } from '../components/MapAddressSearch'
import CensusMapLeftRail, { type CensusMapRailSection } from '../components/CensusMapLeftRail'
import CensusDrilldownStage, { type DrilldownView } from '../components/CensusDrilldownStage'
import CensusDrilldownLocalView from '../components/CensusDrilldownLocalView'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import { deflate, isDollarMetric, peakYearOf } from '../utils/inflation'
import { useInflationToggle } from '../hooks/useInflationToggle'
import { useCpiAnnual } from '../hooks/useCpiAnnual'
import InflationToggle from '../components/InflationToggle'

const STATES_ALBERS_TOPO = 'https://cdn.jsdelivr.net/npm/us-atlas@3/states-albers-10m.json'
const COUNTIES_ALBERS_TOPO = 'https://cdn.jsdelivr.net/npm/us-atlas@3/counties-albers-10m.json'
// Unprojected (lng/lat) counties — for the Leaflet local-view county outline overlay.
const COUNTIES_LL_TOPO = 'https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json'

const FIPS2_TO_USPS: Record<string, string> = {
  '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO', '09': 'CT', '10': 'DE',
  '11': 'DC', '12': 'FL', '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL', '18': 'IN', '19': 'IA',
  '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME', '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN',
  '28': 'MS', '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH', '34': 'NJ', '35': 'NM',
  '36': 'NY', '37': 'NC', '38': 'ND', '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI',
  '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT', '50': 'VT', '51': 'VA', '53': 'WA',
  '54': 'WV', '55': 'WI', '56': 'WY', '72': 'PR',
}
const USPS_TO_FIPS2: Record<string, string> = Object.fromEntries(
  Object.entries(FIPS2_TO_USPS).map(([f, u]) => [u, f]),
)

function fips2(raw) {
  if (raw == null) return ''
  const s = String(raw).replace(/\D/g, '')
  return s.length <= 2 ? s.padStart(2, '0') : s.slice(-2).padStart(2, '0')
}

/**
 * Treat a fetch response as "real JSON" only if the server actually labels it
 * that way. Vite's dev server serves the SPA shell (200 + text/html) for any
 * unmatched path under public/, which would otherwise pose as a successful
 * 200 to vintage-fallback loops and short-circuit them on r.json() parse.
 */
function isJsonResponse(r: Response): boolean {
  if (r.status === 404) return false
  const ct = r.headers.get('content-type') ?? ''
  return ct.includes('json') || ct.includes('geo+json')
}

interface CensusMetric {
  slug: string
  label: string
  format: string
  table?: string
}

interface CensusManifest {
  vintage: string
  vintages?: string[]
  county_topo_cdn: string
  state_topo_cdn?: string
  metrics: CensusMetric[]
  place_states: string[]
  national_ref?: Record<string, Record<string, { us?: number | null; pop_weighted_states?: number | null }>>
  paths: { county_metrics: string; place_geojson: string; state_metrics?: string; state_trends?: string; county_trends?: string; place_trends?: string }
}

interface StateMetricsPayload {
  geography: string
  vintage: string
  values: Record<string, Record<string, number | null | undefined>>
}
interface StateTrendsPayload {
  geography: string
  vintages: string[]
  by_state: Record<string, Record<string, unknown>>
}
interface CountyTrendsPayload {
  geography: string
  state: string
  vintages: string[]
  byGeoid: Record<string, Record<string, unknown>>
}
interface PlaceTrendsPayload {
  geography: string
  state: string
  vintages: string[]
  byGeoid: Record<string, Record<string, unknown>>
}

function pickMetric(metrics: CensusMetric[], slug: string): CensusMetric | undefined {
  return metrics.find((m) => m.slug === slug)
}

function KpiSparkline({
  points,
  width = 80,
  height = 32,
}: {
  points: { x: number; y: number }[]
  width?: number
  height?: number
}) {
  if (points.length < 2) return null
  const xs = points.map((p) => p.x)
  const ys = points.map((p) => p.y)
  const xMin = Math.min(...xs)
  const xMax = Math.max(...xs)
  const yMin = Math.min(...ys)
  const yMax = Math.max(...ys)
  const xRange = xMax - xMin || 1
  const yRange = yMax - yMin || 1
  const pad = 2
  const innerW = width - pad * 2
  const innerH = height - pad * 2
  const xy = points.map((p) => [
    pad + ((p.x - xMin) / xRange) * innerW,
    pad + innerH - ((p.y - yMin) / yRange) * innerH,
  ])
  const d = xy
    .map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(' ')
  const [lx, ly] = xy[xy.length - 1]
  return (
    <svg width={width} height={height} className="block" aria-hidden="true">
      <path
        d={d}
        fill="none"
        stroke="#0284c7"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={lx} cy={ly} r={2} fill="#0284c7" />
    </svg>
  )
}

export default function CensusDrilldownMapPage() {
  const navigate = useNavigate()
  const { vintage: vintageParam, metric: metricParam } = useParams<{ vintage?: string; metric?: string }>()
  const [searchParams, setSearchParams] = useSearchParams()

  // ── view state ────────────────────────────────────────────────────────────
  const [view, setView] = useState<DrilldownView | 'local'>('nation')
  const [selectedStateFips, setSelectedStateFips] = useState<string | null>(null)
  const [selectedCountyGeoid, setSelectedCountyGeoid] = useState<string | null>(null)
  const [localPin, setLocalPin] = useState<{
    lat: number
    lng: number
    label: string
    zoom: number
    basemap: 'streets' | 'satellite'
  } | null>(null)
  const [pinnedAddress, setPinnedAddress] = useState<{
    lat: number
    lng: number
    label: string
    /** Full Nominatim display_name — used to search bronze.bronze_addresses for matches. */
    queryString?: string
    stateCode?: string | null
  } | null>(null)
  /** Result of the property-pin click → /api/addresses/search lookup. */
  const [propertyLookup, setPropertyLookup] = useState<{
    status: 'idle' | 'loading' | 'ok' | 'error'
    query: string
    matches: Array<{
      id: number
      owner_name: string | null
      situs_full: string | null
      city: string | null
      state_abbr: string | null
      parcel_number_formatted: string | null
      appraised_value: number | null
      data_source: string
    }>
    error?: string
  }>({ status: 'idle', query: '', matches: [] })
  const [pinnedCounty, setPinnedCounty] = useState<{
    geoid: string
    name: string
    value: number | null
    rank: { rank: number; total: number } | null
    lngLat: { lng: number; lat: number } | null
  } | null>(null)
  const [pinnedZcta, setPinnedZcta] = useState<{
    zcta: string
    value: number | null
    rank: { rank: number; total: number } | null
    lngLat: { lng: number; lat: number } | null
  } | null>(null)
  const [pinnedPlace, setPinnedPlace] = useState<{
    geoid: string
    name: string
    value: number | null
    rank: { rank: number; total: number } | null
    lngLat: { lng: number; lat: number } | null
  } | null>(null)
  const [hoverInfo, setHoverInfo] = useState<{
    kind: 'state' | 'county' | 'zip' | 'place'
    id: string
    name: string
    value: number | null
    rank: { rank: number; total: number } | null
  } | null>(null)

  // ── display options (mirror existing page) ────────────────────────────────
  const viz: 'filled' | 'bubble' = searchParams.get('viz') === 'bubble' ? 'bubble' : 'filled'
  const scaleRaw = searchParams.get('scale') || 'linear'
  const scale: CensusScaleId = (['linear', 'sqrt', 'log', 'exp'].includes(scaleRaw) ? scaleRaw : 'linear') as CensusScaleId
  const valueModeRaw = searchParams.get('valueMode') || 'raw'
  const valueMode: CensusValueMode = (['raw', 'yoy', 'vs_natl'].includes(valueModeRaw) ? valueModeRaw : 'raw') as CensusValueMode

  const setQP = useCallback(
    (key: string, value: string, defaultValue: string) => {
      const next = new URLSearchParams(searchParams)
      if (value === defaultValue) next.delete(key)
      else next.set(key, value)
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )
  const setViz = (v) => setQP('viz', v, 'filled')
  const setScale = (v) => setQP('scale', v, 'linear')
  const setValueMode = (v) => setQP('valueMode', v, 'raw')
  // ZIP view: overlay the drilled-from county boundary. Off by default.
  const showCountyOutline = searchParams.get('zipOutline') === '1'
  const setShowCountyOutline = (on: boolean) => setQP('zipOutline', on ? '1' : '0', '0')

  // ── inflation toggle (Nominal / Real) — only the pinned/hover KPI card
  //    deflates; leaderboards, choropleth, and narrative copy stay nominal.
  //    Scope is intentionally narrow to match the mockup; widening it would
  //    require plumbing CPI through every dollar surface on the page.
  const { mode: inflationMode, setMode: setInflationMode } = useInflationToggle()
  const cpi = useCpiAnnual()

  // ── data: manifest + state metrics + state trends + albers topology ───────
  const { data: manifest } = useQuery({
    queryKey: ['census-map-manifest'],
    queryFn: async (): Promise<CensusManifest> => {
      const r = await fetch('/data/census-map/manifest.json')
      if (!r.ok) throw new Error('manifest')
      return r.json()
    },
  })

  const { data: statePayload } = useQuery({
    queryKey: ['census-state-metrics', vintageParam],
    queryFn: async (): Promise<StateMetricsPayload | null> => {
      const v = vintageParam || manifest?.vintage || '2024'
      const r = await fetch(`/data/census-map/${v}/state_metrics.json`)
      if (r.status === 404) return null
      if (!r.ok) throw new Error('state metrics')
      return r.json()
    },
    enabled: !!manifest,
    retry: false,
  })

  const { data: stateTrends } = useQuery({
    queryKey: ['census-state-trends'],
    queryFn: async (): Promise<StateTrendsPayload | null> => {
      const r = await fetch('/data/census-map/state_trends.json')
      if (r.status === 404) return null
      if (!r.ok) throw new Error('state trends')
      return r.json()
    },
    enabled: !!manifest,
    retry: false,
  })

  const { data: countyTrends } = useQuery({
    queryKey: ['census-county-trends', selectedStateFips],
    queryFn: async (): Promise<CountyTrendsPayload | null> => {
      const r = await fetch(`/data/census-map/county_trends_${selectedStateFips}.json`)
      if (r.status === 404) return null
      if (!r.ok) throw new Error('county trends')
      return r.json()
    },
    enabled: !!manifest && !!selectedStateFips,
    retry: false,
  })

  const { data: statesTopo } = useQuery({
    queryKey: ['us-atlas-states-albers'],
    queryFn: async () => {
      const r = await fetch(STATES_ALBERS_TOPO)
      if (!r.ok) throw new Error('states topo')
      return r.json()
    },
    staleTime: 1000 * 60 * 60,
  })
  const { data: countiesTopo } = useQuery({
    queryKey: ['us-atlas-counties-albers'],
    queryFn: async () => {
      const r = await fetch(COUNTIES_ALBERS_TOPO)
      if (!r.ok) throw new Error('counties topo')
      return r.json()
    },
    staleTime: 1000 * 60 * 60,
  })

  // ── resolve metric + vintage from URL ─────────────────────────────────────
  const metrics = manifest?.metrics ?? []
  const metricSlug = metricParam ?? 'median_household_income'
  const currentMetric = pickMetric(metrics, metricSlug)
  const metricLabel = currentMetric?.label ?? metricSlug
  const metricFullHelp = censusMetricFullHelp(metricSlug, metricLabel)
  const vintages = useMemo(() => {
    const v = manifest?.vintages
    if (Array.isArray(v) && v.length) return v.slice().sort()
    return manifest?.vintage ? [manifest.vintage] : []
  }, [manifest])
  const displayVintage = vintageParam || manifest?.vintage || vintages[vintages.length - 1] || '2024'
  const yearHelp = `${CENSUS_MAP_UI_HELP.year}\n\n${metricFullHelp}`

  /**
   * Per-state ZCTA topology — lazy-loaded only after the user clicks
   * "Drill down to ZIP". Output of scripts/frontend/prep_zcta_tiles.sh.
   * Returns null on 404 so the layer renders nothing if a state hasn't been
   * prepped yet (rather than blocking the page).
   */
  const { data: zctaTopo } = useQuery({
    queryKey: ['zcta-topo', selectedStateFips],
    queryFn: async () => {
      if (!selectedStateFips) return null
      const r = await fetch(`/data/zctas/state-${selectedStateFips}.json`)
      if (r.status === 404) return null
      if (!r.ok) throw new Error('zcta topo')
      return r.json()
    },
    // Also loaded for 'local' (Leaflet) view, where the ZCTA tile (raw lng/lat)
    // backs the optional ZIP-outline overlay.
    enabled: !!selectedStateFips && (view === 'zip' || view === 'local'),
    staleTime: 1000 * 60 * 60,
    retry: false,
  })

  /**
   * Lng/lat counties topology — only the Leaflet local view needs it (the SVG
   * tiers use the Albers-projected us-atlas counties). Lazy-loaded when the
   * county-outline overlay can be shown, cached for the session.
   */
  const { data: countiesLLTopo } = useQuery({
    queryKey: ['us-atlas-counties-lnglat'],
    queryFn: async () => {
      const r = await fetch(COUNTIES_LL_TOPO)
      if (!r.ok) throw new Error('counties lng/lat topo')
      return r.json()
    },
    enabled:
      ((view === 'local' || view === 'place') && !!selectedCountyGeoid),
    staleTime: 1000 * 60 * 60,
    retry: false,
  })

  /**
   * Per-state places GeoJSON (raw lng/lat). Output of
   * scripts/datasources/census/export_census_map_static.py --place-states.
   * Currently only Alabama vintage 2022 is exported; we walk back through
   * known vintages and surface null on 404 so the page renders an empty-state
   * banner instead of failing. Lazy-loaded when the user enters the place tier.
   */
  const { data: placesGeoJson } = useQuery({
    queryKey: ['places-geojson', selectedStateFips, displayVintage, vintages.join(',')],
    queryFn: async (): Promise<GeoJSON.FeatureCollection | null> => {
      if (!selectedStateFips) return null
      const candidates = [displayVintage, ...vintages.slice().reverse().filter((v) => v !== displayVintage)]
      for (const v of candidates) {
        const r = await fetch(`/data/census-map/${v}/place_${selectedStateFips}.geojson`)
        // Treat "not really there" the same as 404. Vite's dev server serves
        // the SPA shell (200 + text/html) for any unmatched path under public/,
        // so a missing per-vintage file would otherwise short-circuit the
        // fallback to a vintage that *is* exported.
        if (!isJsonResponse(r)) continue
        if (!r.ok) throw new Error('place geojson')
        return r.json()
      }
      return null
    },
    enabled: !!manifest && !!selectedStateFips && (view === 'place' || view === 'local'),
    staleTime: 1000 * 60 * 60,
    retry: false,
  })

  /** Per-state places trends sidecar — same shape as county_trends. */
  const { data: placeTrends } = useQuery({
    queryKey: ['census-place-trends', selectedStateFips],
    queryFn: async (): Promise<PlaceTrendsPayload | null> => {
      if (!selectedStateFips) return null
      const r = await fetch(`/data/census-map/place_trends_${selectedStateFips}.json`)
      if (r.status === 404) return null
      if (!r.ok) throw new Error('place trends')
      return r.json()
    },
    enabled: !!manifest && !!selectedStateFips && view === 'place',
    retry: false,
  })

  /**
   * Per-ZCTA metric values for the current vintage. The exporter
   * (scripts/datasources/census/export_zcta_metrics.py) currently only
   * publishes a single vintage of files; when the requested vintage is missing
   * we walk back through the manifest's vintage list and use the most recent
   * one that does have a file. Without this fallback every non-exported
   * vintage drops to the neutral fill and the ZIP tier looks unshaded.
   */
  const { data: zctaMetricsPayload } = useQuery({
    queryKey: ['zcta-metrics', selectedStateFips, displayVintage, vintages.join(',')],
    queryFn: async (): Promise<{ values: Record<string, Record<string, number | null>> } | null> => {
      if (!selectedStateFips) return null
      const candidates = [displayVintage, ...vintages.slice().reverse().filter((v) => v !== displayVintage)]
      for (const v of candidates) {
        const r = await fetch(`/data/census-map/${v}/zcta_metrics_${selectedStateFips}.json`)
        if (!isJsonResponse(r)) continue
        if (!r.ok) throw new Error('zcta metrics')
        return r.json()
      }
      return null
    },
    enabled: !!selectedStateFips && view === 'zip',
    retry: false,
  })

  const selectableMetrics = useMemo(
    () => metrics.filter((m) => !CENSUS_EXPLORER_HIDDEN_METRIC_SLUGS.has(m.slug)),
    [metrics],
  )

  const onMetricChange = useCallback(
    (slug: string) => navigate(`/data-explorer/map/us/${displayVintage}/${slug}?${searchParams.toString()}`),
    [navigate, displayVintage, searchParams],
  )
  const onVintageChange = useCallback(
    (year: string) => navigate(`/data-explorer/map/us/${year}/${metricSlug}?${searchParams.toString()}`),
    [navigate, metricSlug, searchParams],
  )

  // ── display values per state (current vintage, current valueMode) ─────────
  const stateDisplayById = useMemo(() => {
    const out: Record<string, number | null> = {}
    if (!metricSlug) return out
    const prevV = prevVintageInList(vintages, displayVintage)
    const nat = nationalBaselineWithFallback(manifest?.national_ref, displayVintage, metricSlug, {
      stateRows: statePayload?.values,
      stateTrends,
    })
    if (statePayload?.values) {
      for (const [sid, row] of Object.entries(statePayload.values)) {
        const raw = typeof row[metricSlug] === 'number' && Number.isFinite(row[metricSlug]) ? row[metricSlug] : null
        let prev: number | null = null
        if (valueMode === 'yoy' && prevV && stateTrends?.by_state?.[sid]) {
          prev = trendCell((stateTrends.by_state[sid] as Record<string, unknown>)[metricSlug], prevV)
        }
        out[sid] = displayValueForMode(valueMode, raw, prev, nat)
      }
      return out
    }
    // Fallback: derive from stateTrends when the per-vintage state_metrics file
    // isn't available — keeps the choropleth shaded.
    if (stateTrends?.by_state) {
      for (const [sid, row] of Object.entries(stateTrends.by_state)) {
        const series = (row as Record<string, unknown>)[metricSlug]
        const raw = trendCell(series, displayVintage)
        let prev: number | null = null
        if (valueMode === 'yoy' && prevV) prev = trendCell(series, prevV)
        out[sid] = displayValueForMode(valueMode, raw, prev, nat)
      }
    }
    return out
  }, [statePayload, metricSlug, valueMode, displayVintage, vintages, stateTrends, manifest?.national_ref])

  const stateChoroExtent = useMemo(() => {
    const vals = Object.values(stateDisplayById).filter(
      (x): x is number => typeof x === 'number' && Number.isFinite(x),
    )
    if (!vals.length) return { min: 0, max: 1 }
    return quantileExtent(vals)
  }, [stateDisplayById])

  const stateBubbleExtent = useMemo(() => {
    const vals = Object.values(stateDisplayById).filter(
      (x): x is number => typeof x === 'number' && Number.isFinite(x),
    )
    if (vals.length >= 2) return minMaxExtent(vals)
    return { min: 0, max: 1 }
  }, [stateDisplayById])

  // ── county display values for the selected state (current vintage) ────────
  const countyDisplayByGeoid = useMemo(() => {
    const out: Record<string, number | null> = {}
    if (!countyTrends?.byGeoid || !metricSlug) return out
    const prevV = prevVintageInList(countyTrends.vintages ?? [], displayVintage)
    const nat = nationalBaselineWithFallback(manifest?.national_ref, displayVintage, metricSlug, { stateTrends })
    for (const [gid, row] of Object.entries(countyTrends.byGeoid)) {
      const series = (row as Record<string, unknown>)[metricSlug]
      const raw = trendCell(series, displayVintage)
      let prev: number | null = null
      if (valueMode === 'yoy' && prevV) prev = trendCell(series, prevV)
      const g5 = gid.replace(/\D/g, '').slice(-5).padStart(5, '0')
      out[g5] = displayValueForMode(valueMode, raw, prev, nat)
    }
    return out
  }, [countyTrends, metricSlug, displayVintage, valueMode, manifest?.national_ref, stateTrends])

  const countyChoroExtent = useMemo(() => {
    const vals = Object.values(countyDisplayByGeoid).filter(
      (x): x is number => typeof x === 'number' && Number.isFinite(x),
    )
    if (!vals.length) return { min: 0, max: 1 }
    return quantileExtent(vals)
  }, [countyDisplayByGeoid])

  // ── rank maps for hover tooltip / pin card ───────────────────────────────
  const stateRankById = useMemo(() => {
    const direction = censusMetricRankDirection(metricSlug)
    const entries: [string, number][] = Object.entries(stateDisplayById)
      .filter((entry): entry is [string, number] => typeof entry[1] === 'number' && Number.isFinite(entry[1]))
    entries.sort((a, b) => (direction === 'lower' ? a[1] - b[1] : b[1] - a[1]))
    const total = entries.length
    const out: Record<string, { rank: number; total: number } | null> = {}
    entries.forEach(([sid], i) => {
      out[sid] = { rank: i + 1, total }
    })
    return out
  }, [stateDisplayById, metricSlug])

  const countyRankByGeoid = useMemo(() => {
    const direction = censusMetricRankDirection(metricSlug)
    const entries: [string, number][] = Object.entries(countyDisplayByGeoid)
      .filter((entry): entry is [string, number] => typeof entry[1] === 'number' && Number.isFinite(entry[1]))
    entries.sort((a, b) => (direction === 'lower' ? a[1] - b[1] : b[1] - a[1]))
    const total = entries.length
    const out: Record<string, { rank: number; total: number } | null> = {}
    entries.forEach(([gid], i) => {
      out[gid] = { rank: i + 1, total }
    })
    return out
  }, [countyDisplayByGeoid, metricSlug])

  const countyBubbleExtent = useMemo(() => {
    const vals = Object.values(countyDisplayByGeoid).filter(
      (x): x is number => typeof x === 'number' && Number.isFinite(x),
    )
    if (vals.length >= 2) return minMaxExtent(vals)
    return { min: 0, max: 1 }
  }, [countyDisplayByGeoid])

  // ── Place display values, extents, ranks (mirrors county pattern) ────────
  // ACS place tables are currently only ingested for a sparse set of vintages
  // (Alabama has only 2022 today). When the requested vintage has no value, we
  // fall back to the most recent vintage in the trends file that does — without
  // it every place renders neutral the moment the user picks a year other than
  // 2022.
  const placeDisplayByGeoid = useMemo(() => {
    const out: Record<string, number | null> = {}
    if (!placeTrends?.byGeoid || !metricSlug) return out
    const trendsVintages = (placeTrends.vintages ?? []).slice().sort()
    const prevV = prevVintageInList(trendsVintages, displayVintage)
    const nat = nationalBaselineWithFallback(manifest?.national_ref, displayVintage, metricSlug, { stateTrends })
    const olderToNewer = trendsVintages.slice().reverse()
    for (const [gid, row] of Object.entries(placeTrends.byGeoid)) {
      const series = (row as Record<string, unknown>)[metricSlug]
      let raw = trendCell(series, displayVintage)
      if (raw == null) {
        for (const v of olderToNewer) {
          if (v === displayVintage) continue
          const candidate = trendCell(series, v)
          if (candidate != null) {
            raw = candidate
            break
          }
        }
      }
      let prev: number | null = null
      if (valueMode === 'yoy' && prevV) prev = trendCell(series, prevV)
      const cleaned = typeof raw === 'number' && Number.isFinite(raw) && raw > -1e7 ? raw : null
      const g7 = String(gid).padStart(7, '0')
      out[g7] = displayValueForMode(valueMode, cleaned, prev, nat)
    }
    return out
  }, [placeTrends, metricSlug, displayVintage, valueMode, manifest?.national_ref, stateTrends])

  /** Place GEOIDs whose polygon overlaps the drilled-from county. A pure
   *  centroid test misses multi-county cities — Atlanta straddles Fulton +
   *  DeKalb + Clayton + Cobb, so pinning DeKalb used to hide the city
   *  entirely. We include any place whose polygon intersects the county, and
   *  pass this set down to the stage as the rendering filter so the choro
   *  extent and the rendered set stay in sync. */
  const placeIdsInCounty = useMemo<Set<string> | null>(() => {
    if (!placesGeoJson || !selectedCountyGeoid || !countiesLLTopo) return null
    try {
      const want = String(selectedCountyGeoid).padStart(5, '0')
      const obj = (countiesLLTopo.objects as Record<string, unknown>).counties
      const feats = (topoFeature(countiesLLTopo as never, obj as never) as never).features as GeoJSON.Feature[]
      const countyFeat = feats.find((f) => String(f.id).padStart(5, '0') === want)
      if (!countyFeat) return null
      const countyRings = ringsOfGeom(countyFeat.geometry)
      if (!countyRings.length) return null
      const ids = new Set<string>()
      for (const f of placesGeoJson.features ?? []) {
        const gid = String(f.id ?? (f.properties as { GEOID?: string })?.GEOID ?? '').padStart(7, '0')
        if (!gid) continue
        // Centroid fast path — most places resolve here.
        const c = geoCentroid(f as never)
        if (Number.isFinite(c[0]) && geoContains(countyFeat as never, c)) {
          ids.add(gid)
          continue
        }
        // Multi-county fallback: include the place if its polygon actually
        // overlaps the county. The bbox prefilter inside ringsOverlap keeps
        // this cheap for the ~600 statewide places (most fail bbox quickly).
        const placeRings = ringsOfGeom(f.geometry)
        if (placeRings.length && ringsOverlap(placeRings, countyRings)) ids.add(gid)
      }
      return ids.size ? ids : null
    } catch {
      return null
    }
  }, [placesGeoJson, selectedCountyGeoid, countiesLLTopo])

  const placeChoroExtent = useMemo(() => {
    const entries = Object.entries(placeDisplayByGeoid)
    const scoped = placeIdsInCounty ? entries.filter(([g]) => placeIdsInCounty.has(g)) : entries
    const vals = scoped
      .map(([, v]) => v)
      .filter((x): x is number => typeof x === 'number' && Number.isFinite(x))
    if (!vals.length) return { min: 0, max: 1 }
    return quantileExtent(vals)
  }, [placeDisplayByGeoid, placeIdsInCounty])

  const placeBubbleExtent = useMemo(() => {
    const entries = Object.entries(placeDisplayByGeoid)
    const scoped = placeIdsInCounty ? entries.filter(([g]) => placeIdsInCounty.has(g)) : entries
    const vals = scoped
      .map(([, v]) => v)
      .filter((x): x is number => typeof x === 'number' && Number.isFinite(x))
    if (vals.length >= 2) return minMaxExtent(vals)
    return { min: 0, max: 1 }
  }, [placeDisplayByGeoid, placeIdsInCounty])

  const placeRankByGeoid = useMemo(() => {
    const direction = censusMetricRankDirection(metricSlug)
    const entries: [string, number][] = Object.entries(placeDisplayByGeoid)
      .filter((entry): entry is [string, number] => typeof entry[1] === 'number' && Number.isFinite(entry[1]))
    entries.sort((a, b) => (direction === 'lower' ? a[1] - b[1] : b[1] - a[1]))
    const total = entries.length
    const out: Record<string, { rank: number; total: number } | null> = {}
    entries.forEach(([gid], i) => {
      out[gid] = { rank: i + 1, total }
    })
    return out
  }, [placeDisplayByGeoid, metricSlug])

  // ── ZCTA display values, extents, ranks (mirrors county pattern) ──────────
  const zctaDisplayByZcta = useMemo(() => {
    const out: Record<string, number | null> = {}
    const rows = zctaMetricsPayload?.values
    if (!rows || !metricSlug) return out
    for (const [zcta, row] of Object.entries(rows)) {
      const cell = row[metricSlug]
      // Census ACS uses -666666666 / -555555555 / -333333333 / -222222222 for
      // "estimate not available / suppressed". Treat any large-magnitude
      // negative as null so they don't anchor the low end of the choropleth
      // ramp and wash everything else out. -1e7 is comfortably below any real
      // metric value (rent %, gini, etc) but above every sentinel.
      const raw =
        typeof cell === 'number' && Number.isFinite(cell) && cell > -1e7 ? cell : null
      // For now treat valueMode === 'raw' only — yoy/vs_natl need prior-vintage
      // ZCTA data which isn't ingested yet. Falls back to raw cleanly.
      out[zcta] = raw
    }
    return out
  }, [zctaMetricsPayload, metricSlug])

  const zctaRankByZcta = useMemo(() => {
    const direction = censusMetricRankDirection(metricSlug)
    const entries: [string, number][] = Object.entries(zctaDisplayByZcta)
      .filter((entry): entry is [string, number] => typeof entry[1] === 'number' && Number.isFinite(entry[1]))
    entries.sort((a, b) => (direction === 'lower' ? a[1] - b[1] : b[1] - a[1]))
    const total = entries.length
    const out: Record<string, { rank: number; total: number } | null> = {}
    entries.forEach(([zid], i) => {
      out[zid] = { rank: i + 1, total }
    })
    return out
  }, [zctaDisplayByZcta, metricSlug])

  // ── lng/lat geometry for the Leaflet local-view outline overlays ──────────
  /** Selected county as an unprojected GeoJSON feature (for the Leaflet overlay). */
  const localCountyFeature = useMemo<GeoJSON.Feature | null>(() => {
    if (!countiesLLTopo || !selectedCountyGeoid) return null
    try {
      const obj = (countiesLLTopo.objects as Record<string, unknown>).counties
      const feats = (topoFeature(countiesLLTopo as never, obj as never) as never).features as GeoJSON.Feature[]
      const want = String(selectedCountyGeoid).padStart(5, '0')
      return feats.find((f) => String(f.id).padStart(5, '0') === want) ?? null
    } catch {
      return null
    }
  }, [countiesLLTopo, selectedCountyGeoid])

  /**
   * ZCTAs (lng/lat) for the local-view overlay: those whose centroid falls in
   * the selected county, or — when no county is selected (address-search entry)
   * — those within ~0.4° of the pin, so the overlay never dumps the whole
   * state's ~600 polygons onto Leaflet.
   */
  const localZctaFeatures = useMemo<GeoJSON.Feature[] | null>(() => {
    if (!zctaTopo) return null
    try {
      const obj = (zctaTopo.objects as Record<string, unknown>).zctas
      if (!obj) return null
      const feats = (topoFeature(zctaTopo as never, obj as never) as never).features as GeoJSON.Feature[]
      if (localCountyFeature) {
        return feats.filter((f) => {
          const c = geoCentroid(f as never)
          return Number.isFinite(c[0]) && geoContains(localCountyFeature as never, c)
        })
      }
      if (localPin) {
        const R = 0.4 // degrees ~25-30mi; bounds the overlay around the pin
        return feats.filter((f) => {
          const c = geoCentroid(f as never)
          return (
            Number.isFinite(c[0]) &&
            Math.abs(c[0] - localPin.lng) <= R &&
            Math.abs(c[1] - localPin.lat) <= R
          )
        })
      }
      return null
    } catch {
      return null
    }
  }, [zctaTopo, localCountyFeature, localPin])

  /**
   * ZCTA5 ids whose centroid is inside the currently drilled county. Used to
   * scope the ZIP-tier bubble/choro extents to the visible polygons so the
   * dozen ZIPs of one county actually span the size/color scale — without
   * this the extent runs across all ~650 ZCTAs in the state and every
   * in-county ZIP collapses to ~the same bubble radius. Null when no county
   * is drilled in: callers should fall back to the statewide extent.
   */
  const zctaIdsInCounty = useMemo<Set<string> | null>(() => {
    if (!localCountyFeature || !localZctaFeatures) return null
    const ids = new Set<string>()
    for (const f of localZctaFeatures) {
      const z = String(f.id ?? (f.properties as { GEOID20?: string })?.GEOID20 ?? '').trim()
      if (z) ids.add(z)
    }
    return ids.size ? ids : null
  }, [localCountyFeature, localZctaFeatures])

  const zctaChoroExtent = useMemo(() => {
    const entries = Object.entries(zctaDisplayByZcta)
    const scoped = zctaIdsInCounty ? entries.filter(([z]) => zctaIdsInCounty.has(z)) : entries
    const vals = scoped
      .map(([, v]) => v)
      .filter((x): x is number => typeof x === 'number' && Number.isFinite(x))
    if (!vals.length) return { min: 0, max: 1 }
    return quantileExtent(vals)
  }, [zctaDisplayByZcta, zctaIdsInCounty])

  const zctaBubbleExtent = useMemo(() => {
    const entries = Object.entries(zctaDisplayByZcta)
    const scoped = zctaIdsInCounty ? entries.filter(([z]) => zctaIdsInCounty.has(z)) : entries
    const vals = scoped
      .map(([, v]) => v)
      .filter((x): x is number => typeof x === 'number' && Number.isFinite(x))
    if (vals.length >= 2) return minMaxExtent(vals)
    return { min: 0, max: 1 }
  }, [zctaDisplayByZcta, zctaIdsInCounty])

  // ── flyout / left rail state ──────────────────────────────────────────────
  const [advancedMapOptionsOpen, setAdvancedMapOptionsOpen] = useState(false)
  const [advancedFocusSection, setAdvancedFocusSection] = useState<CensusMapRailSection | null>(null)
  const [playing, setPlaying] = useState(false)

  // Auto-advance the vintage when "Play years" is on; stop at the newest year.
  useEffect(() => {
    if (!playing) return
    if (vintages.length < 2) {
      setPlaying(false)
      return
    }
    const PLAY_INTERVAL_MS = 1950
    const t = window.setInterval(() => {
      const idx = vintages.indexOf(displayVintage)
      const nextIdx = idx < 0 ? 0 : idx + 1
      if (nextIdx >= vintages.length) {
        setPlaying(false)
        return
      }
      onVintageChange(vintages[nextIdx])
    }, PLAY_INTERVAL_MS)
    return () => window.clearInterval(t)
  }, [playing, vintages, displayVintage, onVintageChange])

  // ── navigation handlers ───────────────────────────────────────────────────
  const onPickState = useCallback((fips: string) => {
    setSelectedStateFips(fips)
    setSelectedCountyGeoid(null)
    setView('state')
  }, [])
  const onPickCounty = useCallback(
    (info: {
      geoid: string
      name: string
      value: number | null
      rank: { rank: number; total: number } | null
      lngLat: { lng: number; lat: number } | null
      feature: GeoJSON.Feature
    }) => {
      // A county click drills straight into the ZIP tier: pin the info card,
      // promote the geoid so the Stage's zoom effect has a target feature, and
      // switch to 'zip' — the Stage then flies a van Wijk zoom to the county
      // bbox and reveals the ZCTA boundaries as the per-state tile loads.
      // (Street-view / school-zone CTAs still live in the pinned card.)
      setPinnedCounty({
        geoid: info.geoid,
        name: info.name,
        value: info.value,
        rank: info.rank,
        lngLat: info.lngLat,
      })
      setPinnedZcta(null)
      setPinnedPlace(null)
      setSelectedCountyGeoid(info.geoid)
      setLocalPin(null)
      setView('zip')
    },
    [],
  )

  const onPickZcta = useCallback(
    (info: {
      zcta: string
      value: number | null
      rank: { rank: number; total: number } | null
      lngLat: { lng: number; lat: number } | null
      feature: GeoJSON.Feature
    }) => {
      setPinnedZcta({
        zcta: info.zcta,
        value: info.value,
        rank: info.rank,
        lngLat: info.lngLat,
      })
    },
    [],
  )

  const onPickPlace = useCallback(
    (info: {
      geoid: string
      name: string
      value: number | null
      rank: { rank: number; total: number } | null
      lngLat: { lng: number; lat: number } | null
      feature: GeoJSON.Feature
    }) => {
      setPinnedPlace({
        geoid: info.geoid,
        name: info.name,
        value: info.value,
        rank: info.rank,
        lngLat: info.lngLat,
      })
    },
    [],
  )

  const drillPinnedCountyToStreet = useCallback(() => {
    if (!pinnedCounty?.lngLat) return
    // CTA label says "street view" — match it: open with the streets basemap selected.
    setLocalPin({
      lat: pinnedCounty.lngLat.lat,
      lng: pinnedCounty.lngLat.lng,
      label: pinnedCounty.name,
      zoom: 13,
      basemap: 'streets',
    })
    setSelectedCountyGeoid(pinnedCounty.geoid)
    setView('local')
  }, [pinnedCounty])
  const goNation = useCallback(() => {
    setSelectedStateFips(null)
    setSelectedCountyGeoid(null)
    setLocalPin(null)
    setPinnedCounty(null)
    setPinnedZcta(null)
    setPinnedPlace(null)
    setView('nation')
  }, [])
  const goState = useCallback(() => {
    setSelectedCountyGeoid(null)
    setLocalPin(null)
    setPinnedCounty(null)
    setPinnedZcta(null)
    setPinnedPlace(null)
    setView('state')
  }, [])
  const goCounty = useCallback(() => {
    setLocalPin(null)
    setPinnedPlace(null)
    setView('county')
  }, [])
  const goZip = useCallback(() => {
    // Drill from a pinned county into ZIP view. Keep the pinned county as the
    // initial camera anchor (the Stage frames the county bbox until a ZCTA is
    // clicked). Promote the pin to selectedCountyGeoid so the Stage's zoom
    // effect has a target feature — without this it falls back to a full
    // nation reset and the ZCTA layer renders too small to see.
    if (pinnedCounty) setSelectedCountyGeoid(pinnedCounty.geoid)
    setLocalPin(null)
    setPinnedZcta(null)
    setPinnedPlace(null)
    setView('zip')
  }, [pinnedCounty])

  /** Drill from a pinned county into the cities/towns tier. Same pattern as goZip. */
  const goPlace = useCallback(() => {
    if (pinnedCounty) setSelectedCountyGeoid(pinnedCounty.geoid)
    setLocalPin(null)
    setPinnedZcta(null)
    setPinnedPlace(null)
    setView('place')
  }, [pinnedCounty])

  const onPickAddress = useCallback(
    (r: MapAddressResult) => {
      const fips = r.stateCode ? USPS_TO_FIPS2[r.stateCode] ?? null : null
      setPinnedAddress({
        lat: r.lat,
        lng: r.lon,
        label: r.shortLabel || r.displayName,
        queryString: r.shortLabel || r.displayName,
        stateCode: r.stateCode,
      })
      setPropertyLookup({ status: 'idle', query: '', matches: [] })
      setPinnedPlace(null)
      if (fips) {
        setSelectedStateFips(fips)
        setSelectedCountyGeoid(null)
      }
      // Address search drops the user straight into LOCAL view (Leaflet, satellite).
      setLocalPin({ lat: r.lat, lng: r.lon, label: r.shortLabel || r.displayName, zoom: 17, basemap: 'satellite' })
      setView('local')
    },
    [],
  )

  const fetchPropertyDetails = useCallback(async () => {
    if (!pinnedAddress?.queryString) return
    const q = pinnedAddress.queryString
    setPropertyLookup({ status: 'loading', query: q, matches: [] })
    try {
      const params = new URLSearchParams({ q })
      if (pinnedAddress.stateCode) params.set('state', pinnedAddress.stateCode)
      params.set('limit', '5')
      const res = await fetch(`/api/addresses/search?${params.toString()}`)
      if (!res.ok) {
        const detail = res.status === 503 ? 'bronze.bronze_addresses not loaded' : `HTTP ${res.status}`
        setPropertyLookup({ status: 'error', query: q, matches: [], error: detail })
        return
      }
      const json = await res.json()
      const matches = Array.isArray(json?.addresses) ? json.addresses : []
      setPropertyLookup({ status: 'ok', query: q, matches })
    } catch (err) {
      setPropertyLookup({
        status: 'error',
        query: q,
        matches: [],
        error: err instanceof Error ? err.message : 'fetch failed',
      })
    }
  }, [pinnedAddress])

  // When dropping into local view from a county click, use the county centroid.
  const enterLocalAtCountyCentroid = useCallback(() => {
    // The drilldown stage uses Albers-projected SVG coords. To go to lng/lat
    // for Leaflet, we'd need the inverse — instead, just open the county at
    // its bbox center via the county feature's geo centroid (raw topology).
    // Implementation deferred — for now, user must use address search.
  }, [])

  // ── derived UI ────────────────────────────────────────────────────────────
  const stateName = selectedStateFips
    ? STATE_CODE_TO_NAME[FIPS2_TO_USPS[selectedStateFips] ?? ''] ?? selectedStateFips
    : null
  const countyName = useMemo(() => {
    if (!selectedCountyGeoid || !countyTrends?.byGeoid) return null
    const row = countyTrends.byGeoid[selectedCountyGeoid]
    const n = (row as { NAME?: string } | undefined)?.NAME
    return typeof n === 'string' ? n : null
  }, [selectedCountyGeoid, countyTrends])

  const fmt = useCallback(
    (v: number) => formatMetricValueDisplay(metricSlug, v, metrics, valueMode),
    [metricSlug, metrics, valueMode],
  )
  const choroSemantics = useMemo(
    () => censusChoroLegendSemantics(metricSlug, valueMode, metricLabel),
    [metricSlug, valueMode, metricLabel],
  )

  const showRightAside = view !== 'local'
  const localStatus = localPin ? localPin.label : 'Click any state to drill in'
  type Crumb = { label: string; current: boolean; onClick?: () => void }
  const crumbs: Crumb[] = [
    { label: 'United States', current: view === 'nation', onClick: goNation },
  ]
  if (selectedStateFips) {
    crumbs.push({
      label: stateName ?? selectedStateFips,
      current: view === 'state',
      onClick: goState,
    })
  }
  if (selectedCountyGeoid) {
    crumbs.push({
      label: countyName ?? `County ${selectedCountyGeoid}`,
      current: view === 'county',
      onClick: goCounty,
    })
  }
  if (view === 'zip') {
    // "ZIP codes" = the whole county's ZCTAs; clickable to re-frame when a
    // single ZCTA is pinned (goZip clears the pin and zooms back to county).
    crumbs.push({
      label: 'ZIP codes',
      current: !pinnedZcta,
      onClick: goZip,
    })
    if (pinnedZcta) {
      crumbs.push({ label: `ZIP ${pinnedZcta.zcta}`, current: true })
    }
  }
  if (view === 'place') {
    crumbs.push({
      label: 'Cities & towns',
      current: !pinnedPlace,
      onClick: goPlace,
    })
    if (pinnedPlace) {
      crumbs.push({ label: pinnedPlace.name, current: true })
    }
  }
  if (view === 'local') {
    crumbs.push({ label: 'Address', current: true })
  }

  const breadcrumb = (
    <nav
      aria-label="Drill-down breadcrumb"
      className="flex min-w-0 flex-wrap items-center gap-x-1 gap-y-0.5 text-[13px] leading-tight text-slate-700"
    >
      {crumbs.map((c, i) => {
        const isLast = i === crumbs.length - 1
        return (
          <span key={`${i}-${c.label}`} className="inline-flex min-w-0 items-center gap-1">
            {c.onClick && !c.current ? (
              <button
                type="button"
                onClick={c.onClick}
                title={`Zoom to ${c.label}`}
                className="truncate rounded px-1.5 py-0.5 font-medium text-slate-700 underline-offset-2 transition-colors hover:bg-amber-50 hover:text-amber-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
              >
                {c.label}
              </button>
            ) : (
              <span
                aria-current={c.current ? 'page' : undefined}
                className={`truncate rounded px-1.5 py-0.5 font-semibold ${
                  c.current ? 'bg-amber-100/70 text-amber-800' : 'text-slate-900'
                }`}
              >
                {c.label}
              </span>
            )}
            {!isLast ? (
              <span aria-hidden className="select-none text-slate-300">
                /
              </span>
            ) : null}
          </span>
        )
      })}
    </nav>
  )

  return (
    <div className="mx-auto w-full min-w-0 space-y-2.5">
      {/* options flyout (year, view, scale, values) */}
      <CensusMapOptionsFlyout
        open={advancedMapOptionsOpen}
        onClose={() => {
          setAdvancedMapOptionsOpen(false)
          setAdvancedFocusSection(null)
        }}
        focusSection={advancedFocusSection}
        onConsumedFocusSection={() => setAdvancedFocusSection(null)}
        viz={viz}
        setViz={setViz}
        scale={scale}
        setScale={setScale}
        valueMode={valueMode}
        setValueMode={setValueMode}
        vintages={vintages}
        displayVintage={displayVintage}
        onVintageChange={onVintageChange}
        yearHelp={yearHelp}
        metricFullHelp={metricFullHelp}
        playing={playing}
        setPlaying={setPlaying}
      />

      {/* header: breadcrumb + metric selector + address search */}
      <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm sm:flex-row sm:items-center">
        <div className="min-w-0 flex-1">{breadcrumb}</div>
        <div className="min-w-0 flex-1 sm:max-w-sm">
          <MetricPicker
            metrics={selectableMetrics}
            metricSlug={metricSlug}
            metricFullHelp={metricFullHelp}
            onPick={onMetricChange}
          />
        </div>
        <div className="min-w-0 flex-1 sm:max-w-md">
          <MapAddressSearch onPick={onPickAddress} onClear={() => setPinnedAddress(null)} />
        </div>
      </div>

      <div
        className={`grid gap-3 ${
          showRightAside
            ? 'grid-cols-1 xl:grid-cols-[auto_minmax(0,1fr)_minmax(300px,24rem)] items-start'
            : 'grid-cols-1 xl:grid-cols-[auto_minmax(0,1fr)] items-start'
        }`}
      >
        {/* left rail */}
        <div className="hidden xl:block xl:sticky xl:top-4">
          <CensusMapLeftRail
            activeSection={advancedMapOptionsOpen ? advancedFocusSection : null}
            yearBadge={displayVintage}
            onOpen={(section) => {
              // Toggle: clicking the same rail icon while the flyout is open
              // dismisses it, so the rail acts like a tabbed sidebar.
              if (advancedMapOptionsOpen && advancedFocusSection === section) {
                setAdvancedMapOptionsOpen(false)
                setAdvancedFocusSection(null)
              } else {
                setAdvancedFocusSection(section)
                setAdvancedMapOptionsOpen(true)
              }
            }}
            onReset={goNation}
            canReset={view !== 'nation' || !!selectedStateFips || !!pinnedCounty || !!pinnedAddress}
          />
        </div>

        {/* center: stage + legend */}
        <div className="flex min-w-0 flex-col gap-2">
          <div className="relative rounded-lg border border-slate-200 bg-white p-2 shadow-sm">
            {/* ZIP / places views: opt-in county boundary overlay (off by default). */}
            {view === 'zip' || view === 'place' ? (
              <label className="absolute left-3 top-3 z-10 inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-slate-300 bg-white/95 px-2 py-1 text-[11px] font-medium text-slate-700 shadow-sm backdrop-blur hover:bg-white">
                <input
                  type="checkbox"
                  checked={showCountyOutline}
                  onChange={(e) => setShowCountyOutline(e.target.checked)}
                  className="h-3.5 w-3.5 rounded border-slate-300 text-[#354F52] focus:ring-[#354F52]"
                />
                County outline
              </label>
            ) : null}
            {view === 'local' && localPin ? (
              <div className="relative h-[560px] w-full">
                <CensusDrilldownLocalView
                  key={`local-${localPin.basemap}`}
                  center={{ lat: localPin.lat, lng: localPin.lng }}
                  zoom={localPin.zoom}
                  label={localPin.label}
                  initialBasemap={localPin.basemap}
                  onMarkerClick={fetchPropertyDetails}
                  countyOutline={localCountyFeature}
                  zctaOutlines={localZctaFeatures}
                  topLeftSlot={
                    <button
                      type="button"
                      onClick={() => {
                        setLocalPin(null)
                        setView(selectedCountyGeoid ? 'county' : selectedStateFips ? 'state' : 'nation')
                      }}
                      className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-700 shadow-md hover:bg-slate-50"
                    >
                      <ArrowLeftIcon className="h-3.5 w-3.5" aria-hidden />
                      Back to map
                    </button>
                  }
                />
                {propertyLookup.status !== 'idle' ? (
                  <div className="pointer-events-auto absolute right-3 bottom-3 z-[500] w-[300px] max-w-[calc(100%-1.5rem)] rounded-lg border border-slate-300 bg-white p-3 shadow-xl">
                    <div className="flex items-start gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                          Property details
                        </div>
                        <div className="mt-0.5 truncate text-[12px] text-slate-700" title={propertyLookup.query}>
                          {propertyLookup.query}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setPropertyLookup({ status: 'idle', query: '', matches: [] })}
                        className="-mr-1 -mt-1 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                        aria-label="Close property details"
                      >
                        <XMarkIcon className="h-4 w-4" />
                      </button>
                    </div>
                    {propertyLookup.status === 'loading' ? (
                      <div className="mt-2 text-[12px] text-slate-500">Looking up parcel records…</div>
                    ) : null}
                    {propertyLookup.status === 'error' ? (
                      <div className="mt-2 text-[12px] text-rose-700">
                        Lookup failed: {propertyLookup.error}
                      </div>
                    ) : null}
                    {propertyLookup.status === 'ok' && propertyLookup.matches.length === 0 ? (
                      <div className="mt-2 text-[12px] leading-snug text-slate-600">
                        No matching parcel in <code>bronze.bronze_addresses</code>. Coverage is limited
                        to counties whose Esri parcel layer has been harvested — most haven't yet.
                      </div>
                    ) : null}
                    {propertyLookup.status === 'ok' && propertyLookup.matches.length > 0 ? (
                      <ul className="mt-2 space-y-2 text-[12px]">
                        {propertyLookup.matches.map((m) => (
                          <li key={m.id} className="rounded border border-slate-200 bg-slate-50/60 p-2">
                            <div className="font-semibold text-slate-900">
                              {m.situs_full || m.owner_name || `Parcel ${m.parcel_number_formatted ?? m.id}`}
                            </div>
                            {m.owner_name && m.situs_full ? (
                              <div className="text-[11px] text-slate-600">Owner: {m.owner_name}</div>
                            ) : null}
                            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-slate-600">
                              {m.parcel_number_formatted ? <span>Parcel {m.parcel_number_formatted}</span> : null}
                              {m.appraised_value != null ? (
                                <span>${m.appraised_value.toLocaleString()}</span>
                              ) : null}
                              {m.city || m.state_abbr ? (
                                <span>
                                  {[m.city, m.state_abbr].filter(Boolean).join(', ')}
                                </span>
                              ) : null}
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : (
              <CensusDrilldownStage
                view={view as DrilldownView}
                statesTopo={statesTopo as never}
                countiesTopo={countiesTopo as never}
                zctaTopo={zctaTopo as never}
                placesGeoJson={placesGeoJson ?? null}
                selectedStateFips={selectedStateFips}
                selectedCountyGeoid={selectedCountyGeoid}
                selectedZcta={pinnedZcta?.zcta ?? null}
                selectedPlaceGeoid={pinnedPlace?.geoid ?? null}
                stateDisplayById={stateDisplayById}
                countyDisplayByGeoid={countyDisplayByGeoid}
                zctaDisplayByZcta={zctaDisplayByZcta}
                placeDisplayByGeoid={placeDisplayByGeoid}
                placeIdsInCounty={placeIdsInCounty}
                stateChoroExtent={stateChoroExtent}
                countyChoroExtent={countyChoroExtent}
                zctaChoroExtent={zctaChoroExtent}
                placeChoroExtent={placeChoroExtent}
                stateBubbleExtent={stateBubbleExtent}
                countyBubbleExtent={countyBubbleExtent}
                zctaBubbleExtent={zctaBubbleExtent}
                placeBubbleExtent={placeBubbleExtent}
                scale={scale}
                viz={viz}
                onPickState={onPickState}
                onPickCounty={onPickCounty}
                onPickZcta={onPickZcta}
                onPickPlace={onPickPlace}
                onResetToNation={goNation}
                pinnedLngLat={pinnedAddress ? { lng: pinnedAddress.lng, lat: pinnedAddress.lat } : null}
                pinnedCountyGeoid={pinnedCounty?.geoid ?? null}
                pinnedZcta={pinnedZcta?.zcta ?? null}
                pinnedPlaceGeoid={pinnedPlace?.geoid ?? null}
                showCountyOutline={showCountyOutline}
                stateRankById={stateRankById}
                countyRankByGeoid={countyRankByGeoid}
                zctaRankByZcta={zctaRankByZcta}
                placeRankByGeoid={placeRankByGeoid}
                onHoverInfo={setHoverInfo}
              />
            )}
          </div>

          {/* status strip */}
          <div className="flex items-center justify-between gap-2 rounded-md border border-slate-200 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 shadow-sm">
            <span className="font-mono text-[10px] uppercase tracking-widest text-amber-200">
              {view.toUpperCase()}
            </span>
            <span className="min-w-0 flex-1 truncate text-slate-100">
              {view === 'local'
                ? localStatus
                : view === 'zip'
                  ? zctaTopo
                    ? `${stateName} · ${Object.keys(zctaDisplayByZcta).length || 'ZCTA'} polygons · click a ZIP to pin`
                    : `${stateName} · ZIP tiles not generated for this state yet — run scripts/frontend/prep_zcta_tiles.sh`
                  : view === 'place'
                    ? placesGeoJson
                      ? `${stateName} · ${(placesGeoJson.features ?? []).length} cities & towns in state · click any to pin`
                      : `${stateName} · place tiles not generated for this state yet — run scripts/datasources/census/export_census_map_static.py --place-states ${selectedStateFips ?? '??'}`
                    : view === 'county'
                      ? `${countyName ?? selectedCountyGeoid} · click any county or address to go deeper`
                      : view === 'state'
                        ? `${stateName} · click any county`
                        : `${Object.keys(stateDisplayById).length} states · click any to drill in`}
            </span>
            {view !== 'nation' ? (
              <button
                type="button"
                onClick={goNation}
                className="rounded p-0.5 text-slate-400 hover:bg-slate-700 hover:text-slate-100"
                aria-label="Reset"
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            ) : null}
          </div>

          {/* legends — same shading semantics as the existing page */}
          {view !== 'local' ? (
            viz === 'filled' ? (
              <ChoroplethLegend
                min={
                  view === 'zip'
                    ? zctaChoroExtent.min
                    : view === 'place'
                      ? placeChoroExtent.min
                      : view === 'nation'
                        ? stateChoroExtent.min
                        : countyChoroExtent.min
                }
                max={
                  view === 'zip'
                    ? zctaChoroExtent.max
                    : view === 'place'
                      ? placeChoroExtent.max
                      : view === 'nation'
                        ? stateChoroExtent.max
                        : countyChoroExtent.max
                }
                scale={scale}
                format={fmt}
                valueMode={valueMode}
                metricHelp={metricFullHelp}
                semantics={choroSemantics}
              />
            ) : (
              <BubbleLegend
                min={
                  view === 'zip'
                    ? zctaBubbleExtent.min
                    : view === 'place'
                      ? placeBubbleExtent.min
                      : view === 'nation'
                        ? stateBubbleExtent.min
                        : countyBubbleExtent.min
                }
                max={
                  view === 'zip'
                    ? zctaBubbleExtent.max
                    : view === 'place'
                      ? placeBubbleExtent.max
                      : view === 'nation'
                        ? stateBubbleExtent.max
                        : countyBubbleExtent.max
                }
                scale={scale}
                format={fmt}
                metricHelp={metricFullHelp}
              />
            )
          ) : null}
        </div>

        {/* right column — unified hover/pin readout (replaces dark floating tooltip) */}
        {showRightAside ? (
          <aside
            className={`flex flex-col gap-3 xl:sticky xl:top-4 ${
              // Mobile (<xl) has no hover affordance and the aside otherwise
              // stacks below a tall map — a tapped county's drill CTAs end up
              // off-screen. When a county is pinned, dock the aside as a bottom
              // sheet so "Drill down to ZIP" is immediately reachable. Desktop
              // keeps the sticky sidebar (all sheet styles reset at xl:).
              pinnedCounty
                ? 'fixed inset-x-0 bottom-0 z-40 max-h-[70vh] overflow-y-auto rounded-t-2xl border-t border-slate-200 bg-white/95 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-2xl backdrop-blur xl:inset-x-auto xl:bottom-auto xl:z-auto xl:max-h-none xl:overflow-visible xl:rounded-none xl:border-0 xl:bg-transparent xl:p-0 xl:shadow-none xl:backdrop-blur-none'
                : ''
            }`}
          >
            {(() => {
              // Card precedence: a pinned place > pinned county > transient hover > idle.
              // A place pin is a deeper drill than the surrounding county, so we
              // surface it on top — but keep the county pin's drill CTAs reachable
              // via the breadcrumb (cliking the county crumb re-frames).
              const isPinned = !!pinnedPlace || !!pinnedCounty
              // State-tier fallback: once a state is drilled into, keep its
              // KPI in the card so it doesn't vanish whenever the cursor
              // leaves the county layer. Mirrors how the county tier always
              // shows the pinned-county KPI.
              const stateFallback =
                view === 'state' && selectedStateFips
                  ? {
                      kind: 'state' as const,
                      id: selectedStateFips,
                      name: stateName ?? selectedStateFips,
                      value: stateDisplayById[selectedStateFips] ?? null,
                      rank: stateRankById[selectedStateFips] ?? null,
                    }
                  : null
              const showing = pinnedPlace
                ? {
                    kind: 'place' as const,
                    id: pinnedPlace.geoid,
                    name: pinnedPlace.name,
                    value: pinnedPlace.value,
                    rank: pinnedPlace.rank,
                  }
                : pinnedCounty
                  ? {
                      kind: 'county' as const,
                      id: pinnedCounty.geoid,
                      name: pinnedCounty.name,
                      value: pinnedCounty.value,
                      rank: pinnedCounty.rank,
                    }
                  : (hoverInfo ?? stateFallback)
              const idle = !showing
              const accent = isPinned
                ? 'border-amber-300 ring-2 ring-amber-100/70'
                : 'border-slate-200'
              // Trend series for the active region — drives the sparkline and
              // the YoY / 5yr deltas. ZIP-tier and unknown regions have no
              // multi-vintage data and fall through to a value-only readout.
              let trendSeries: Record<string, unknown> | undefined
              let trendVintages: string[] = []
              if (showing?.kind === 'state' && stateTrends?.by_state) {
                trendSeries = (stateTrends.by_state[fips2(showing.id)] as Record<string, unknown> | undefined)?.[
                  metricSlug
                ] as Record<string, unknown> | undefined
                trendVintages = vintages
              } else if (showing?.kind === 'county' && countyTrends?.byGeoid) {
                trendSeries = (countyTrends.byGeoid[String(showing.id).padStart(5, '0')] as
                  | Record<string, unknown>
                  | undefined)?.[metricSlug] as Record<string, unknown> | undefined
                trendVintages = countyTrends.vintages ?? []
              } else if (showing?.kind === 'place' && placeTrends?.byGeoid) {
                trendSeries = (placeTrends.byGeoid[String(showing.id).padStart(7, '0')] as
                  | Record<string, unknown>
                  | undefined)?.[metricSlug] as Record<string, unknown> | undefined
                trendVintages = placeTrends.vintages ?? []
              }
              const rawCurrent = trendSeries ? trendCell(trendSeries, displayVintage) : null
              const prev1y = trendVintages.length ? prevVintageInList(trendVintages, displayVintage) : null
              const yoyPct =
                trendSeries && prev1y ? pctChangeBetween(rawCurrent, trendCell(trendSeries, prev1y)) : null
              const prev5y = trendVintages.length
                ? prevVintageCalendarYearsBack(trendVintages, displayVintage, 5)
                : null
              const fiveYrPct =
                trendSeries && prev5y ? pctChangeBetween(rawCurrent, trendCell(trendSeries, prev5y)) : null
              const sparkPoints: { x: number; y: number }[] = trendSeries
                ? trendVintages
                    .map((v) => {
                      const y = trendCell(trendSeries!, v)
                      return { x: Number(v), y: typeof y === 'number' && Number.isFinite(y) ? y : NaN }
                    })
                    .filter(
                      (p): p is { x: number; y: number } =>
                        Number.isFinite(p.x) && Number.isFinite(p.y),
                    )
                : []
              // ── Inflation toggle overrides (Real mode) ─────────────────
              // Only deflate when the metric is dollars AND we're showing
              // the raw value (yoy/vs_natl modes are already percentages,
              // so the toggle is hidden in those modes). When CPI hasn't
              // loaded yet we silently fall back to nominal — better a
              // correct nominal number than a confusing dash.
              const dollarMetric = isDollarMetric(metricSlug)
              const toggleActive = dollarMetric && valueMode === 'raw'
              const cpiByYear = cpi.data?.by_year
              const cpiLatestYear = cpi.data?.latest_year
              const realMode = toggleActive && inflationMode === 'real' && !!cpiByYear && cpiLatestYear != null
              const displayValue = realMode
                ? deflate(showing?.value ?? null, displayVintage, cpiLatestYear, cpiByYear) ??
                  (showing?.value ?? null)
                : (showing?.value ?? null)
              const yoyPctEff =
                realMode && prev1y && trendSeries
                  ? pctChangeBetween(
                      deflate(rawCurrent, displayVintage, cpiLatestYear, cpiByYear),
                      deflate(trendCell(trendSeries, prev1y), prev1y, cpiLatestYear, cpiByYear),
                    )
                  : yoyPct
              const fiveYrPctEff =
                realMode && prev5y && trendSeries
                  ? pctChangeBetween(
                      deflate(rawCurrent, displayVintage, cpiLatestYear, cpiByYear),
                      deflate(trendCell(trendSeries, prev5y), prev5y, cpiLatestYear, cpiByYear),
                    )
                  : fiveYrPct
              const sparkPointsEff = realMode
                ? sparkPoints.map((p) => {
                    const dy = deflate(p.y, p.x, cpiLatestYear, cpiByYear)
                    return { x: p.x, y: dy ?? p.y }
                  })
                : sparkPoints
              const hasDeltasEff = yoyPctEff != null || fiveYrPctEff != null
              const peakYear = toggleActive ? peakYearOf(sparkPointsEff, displayVintage) : null
              const footnoteBits: string[] = []
              if (toggleActive) {
                footnoteBits.push(
                  realMode ? `real, in ${cpiLatestYear} dollars` : 'nominal',
                )
                if (peakYear != null) footnoteBits.push(`peaked in ${peakYear}`)
              }
              const inflationFootnote = footnoteBits.join(' · ')

              const showNameSuffix =
                !!showing &&
                (showing.kind === 'county' || showing.kind === 'zip' || showing.kind === 'place') &&
                !!stateName
              const clearPin = () => {
                if (pinnedPlace) setPinnedPlace(null)
                else setPinnedCounty(null)
              }
              return (
                <div className={`rounded-lg border bg-white p-3 shadow-sm transition-colors ${accent}`}>
                  {idle ? (
                    <div className="flex items-start gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                          Region details
                        </div>
                        <div className="mt-0.5 text-sm font-semibold leading-snug text-slate-900">
                          {view === 'nation'
                            ? 'Hover any state for details · click to zoom'
                            : `Hover any county in ${stateName ?? 'this state'} for details`}
                        </div>
                        <div className="mt-2 text-[11px] leading-snug text-slate-500">
                          Showing{' '}
                          <span className="font-medium text-slate-700">
                            {currentMetric && censusMapShowOfficialCensusLabel(currentMetric.slug)
                              ? currentMetric.label
                              : metricLabel}
                          </span>{' '}
                          for {displayVintage}.
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
                          {showing!.name}
                          {showNameSuffix ? (
                            <span className="font-normal text-slate-400">, {stateName}</span>
                          ) : null}
                        </div>
                        <div className="mt-1 text-[28px] font-semibold leading-none tabular-nums text-slate-900">
                          {displayValue != null
                            ? formatMetricValueCompact(metricSlug, displayValue, metrics, valueMode)
                            : '—'}
                        </div>
                        {hasDeltasEff ? (
                          <div className="mt-1.5 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] tabular-nums">
                            {yoyPctEff != null && prev1y != null ? (
                              <span className={yoyPctEff >= 0 ? 'text-emerald-600' : 'text-rose-600'}>
                                {yoyPctEff >= 0 ? '+' : ''}
                                {yoyPctEff.toFixed(1)}% vs {prev1y}
                              </span>
                            ) : null}
                            {yoyPctEff != null && fiveYrPctEff != null ? (
                              <span className="text-slate-300">·</span>
                            ) : null}
                            {fiveYrPctEff != null ? (
                              <span className={fiveYrPctEff >= 0 ? 'text-emerald-600' : 'text-rose-600'}>
                                {fiveYrPctEff >= 0 ? '+' : ''}
                                {fiveYrPctEff.toFixed(0)}% over 5yr
                              </span>
                            ) : null}
                          </div>
                        ) : null}
                        <div className="mt-1 truncate text-[10px] uppercase tracking-wide text-slate-400">
                          {metricLabel}
                        </div>
                        {inflationFootnote ? (
                          <div className="mt-0.5 truncate text-[10px] text-slate-400">
                            {inflationFootnote}
                          </div>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1.5">
                        {toggleActive ? (
                          <InflationToggle
                            mode={inflationMode}
                            onChange={setInflationMode}
                            ariaLabel={metricLabel}
                          />
                        ) : null}
                        <div className="flex items-center gap-1">
                          {showing!.rank ? (
                            <span className="whitespace-nowrap rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-semibold tabular-nums text-sky-700">
                              #{showing!.rank.rank} of {showing!.rank.total}
                            </span>
                          ) : null}
                          {isPinned ? (
                            <button
                              type="button"
                              onClick={clearPin}
                              className="-mr-1 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                              aria-label="Clear pin"
                            >
                              <XMarkIcon className="h-4 w-4" />
                            </button>
                          ) : null}
                        </div>
                        {sparkPointsEff.length >= 2 ? <KpiSparkline points={sparkPointsEff} /> : null}
                      </div>
                    </div>
                  )}
                  {isPinned ? (
                    <div className="mt-3 flex flex-col gap-1.5 border-t border-slate-100 pt-2.5">
                      <button
                        type="button"
                        onClick={drillPinnedCountyToStreet}
                        disabled={!pinnedCounty!.lngLat}
                        className="inline-flex items-center justify-center gap-1.5 rounded-md bg-[#354F52] px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-white shadow-sm hover:bg-[#2c4346] disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Drill down to street view
                      </button>
                      {view === 'zip' && pinnedZcta ? (
                        <button
                          type="button"
                          onClick={goZip}
                          title="Zoom back out to show every ZIP in this county."
                          className="inline-flex items-center justify-center gap-1.5 rounded-md bg-[#354F52] px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-white shadow-sm hover:bg-[#2c4346]"
                        >
                          Re-frame all county ZIPs
                        </button>
                      ) : view !== 'zip' ? (
                        <button
                          type="button"
                          onClick={goZip}
                          title="Show ZCTA (ZIP) boundaries within this county. Requires running scripts/frontend/prep_zcta_tiles.sh to generate per-state ZCTA topology."
                          className="inline-flex items-center justify-center gap-1.5 rounded-md bg-[#354F52] px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-white shadow-sm hover:bg-[#2c4346]"
                        >
                          Drill down to ZIP
                        </button>
                      ) : null}
                      {view === 'place' && pinnedPlace ? (
                        <button
                          type="button"
                          onClick={goPlace}
                          title="Zoom back out to show every city/town in this county."
                          className="inline-flex items-center justify-center gap-1.5 rounded-md bg-[#354F52] px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-white shadow-sm hover:bg-[#2c4346]"
                        >
                          Re-frame all county cities
                        </button>
                      ) : view !== 'place' ? (
                        (() => {
                          const stateHasPlaceData =
                            !!selectedStateFips && (manifest?.place_states ?? []).includes(selectedStateFips)
                          return stateHasPlaceData ? (
                            <button
                              type="button"
                              onClick={goPlace}
                              title="Show Census places (cities, towns, CDPs) within this county."
                              className="inline-flex items-center justify-center gap-1.5 rounded-md bg-[#354F52] px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-white shadow-sm hover:bg-[#2c4346]"
                            >
                              Drill down to cities &amp; towns
                            </button>
                          ) : (
                            <button
                              type="button"
                              disabled
                              title={`Place GeoJSON not exported for this state yet — run scripts/datasources/census/export_census_map_static.py --fetch --place-states ${selectedStateFips ?? '{fips}'} --year 2022`}
                              className="inline-flex cursor-not-allowed items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500"
                            >
                              Drill down to cities &amp; towns
                              <span className="ml-2 rounded bg-slate-200 px-1 py-px text-[9px] font-medium normal-case tracking-normal text-slate-600">
                                Soon
                              </span>
                            </button>
                          )
                        })()
                      ) : null}
                      <button
                        type="button"
                        disabled
                        title="School-zone tier needs district/attendance-zone polygons (Census EDGE / NCES) — not yet ingested."
                        className="inline-flex cursor-not-allowed items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500"
                      >
                        Drill down to school zones
                        <span className="ml-2 rounded bg-slate-200 px-1 py-px text-[9px] font-medium normal-case tracking-normal text-slate-600">
                          Soon
                        </span>
                      </button>
                    </div>
                  ) : null}
                </div>
              )
            })()}
            {/* Pin stays primary; when the cursor visits another region, the
                comparison chip slides in just below so the user can preview
                without dismissing. */}
            {pinnedCounty && hoverInfo && hoverInfo.id !== pinnedCounty.geoid ? (
              <div className="rounded-md border border-slate-200 bg-slate-50/80 px-3 py-2 text-[12px] shadow-sm">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="text-[9px] font-semibold uppercase tracking-wide text-slate-500">
                      Hovering{' '}
                      {hoverInfo.kind === 'state'
                        ? 'state'
                        : hoverInfo.kind === 'zip'
                          ? 'ZIP'
                          : hoverInfo.kind === 'place'
                            ? 'city/town'
                            : 'county'}
                    </div>
                    <div className="mt-0.5 truncate text-[13px] font-medium leading-snug text-slate-900">
                      {hoverInfo.name}
                    </div>
                    <div className="mt-0.5 text-[12px] tabular-nums text-slate-700">
                      {formatMetricValueCompact(metricSlug, hoverInfo.value, metrics, valueMode)}
                      {hoverInfo.rank ? (
                        <span className="ml-2 text-[11px] text-slate-500">
                          #{hoverInfo.rank.rank} of {hoverInfo.rank.total}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  {hoverInfo.kind === 'county' ? (
                    <button
                      type="button"
                      onClick={() => {
                        setPinnedCounty({
                          geoid: hoverInfo.id,
                          name: hoverInfo.name,
                          value: hoverInfo.value,
                          rank: hoverInfo.rank,
                          lngLat: null,
                        })
                      }}
                      className="shrink-0 rounded-md border border-slate-300 bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-700 hover:bg-slate-50"
                      title="Replace pin with this county"
                    >
                      Pin
                    </button>
                  ) : null}
                </div>
              </div>
            ) : null}
            {pinnedAddress ? (
              <div className="rounded-lg border border-rose-200 bg-white p-3 shadow-sm">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-rose-700">
                  Pinned address
                </div>
                <div className="mt-0.5 text-sm font-semibold text-slate-900">{pinnedAddress.label}</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      setLocalPin({ lat: pinnedAddress.lat, lng: pinnedAddress.lng, label: pinnedAddress.label, zoom: 17, basemap: 'satellite' })
                      || setView('local')
                    }
                    className="rounded-md bg-[#354F52] px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-white hover:bg-[#2c4346]"
                  >
                    Open satellite view
                  </button>
                  <button
                    type="button"
                    onClick={() => setPinnedAddress(null)}
                    className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-700 hover:bg-slate-50"
                  >
                    Clear pin
                  </button>
                </div>
              </div>
            ) : null}
          </aside>
        ) : null}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components: metric picker + options flyout (similar to existing patterns)
// ---------------------------------------------------------------------------

function MetricPicker({
  metrics,
  metricSlug,
  metricFullHelp,
  onPick,
}: {
  metrics: CensusMetric[]
  metricSlug: string
  metricFullHelp: string
  onPick: (slug: string) => void
}) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <span className="inline-flex items-center gap-1">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          What do you want to explore?
        </span>
        <InfoHelpTrigger help={metricFullHelp} topic="Metric" align="left" />
      </span>
      <select
        aria-label="Topic to show on the map"
        className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs font-medium text-slate-900 shadow-sm"
        value={metricSlug}
        onChange={(e) => onPick(e.target.value)}
      >
        {metrics.map((m) => (
          <option key={m.slug} value={m.slug}>
            {m.label}
          </option>
        ))}
      </select>
    </div>
  )
}

function CensusMapOptionsFlyout({
  open,
  onClose,
  focusSection,
  onConsumedFocusSection,
  viz,
  setViz,
  scale,
  setScale,
  valueMode,
  setValueMode,
  vintages,
  displayVintage,
  onVintageChange,
  yearHelp,
  metricFullHelp,
  playing,
  setPlaying,
}: {
  open: boolean
  onClose: () => void
  focusSection: CensusMapRailSection | null
  onConsumedFocusSection: () => void
  viz: 'filled' | 'bubble'
  setViz: (v: 'filled' | 'bubble') => void
  scale: CensusScaleId
  setScale: (s: CensusScaleId) => void
  valueMode: CensusValueMode
  setValueMode: (m: CensusValueMode) => void
  vintages: string[]
  displayVintage: string
  onVintageChange: (year: string) => void
  yearHelp: string
  metricFullHelp: string
  playing: boolean
  setPlaying: (v: boolean) => void
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  useEffect(() => {
    if (!open || !focusSection) return
    const id = `drilldown-section-${focusSection}`
    const t = window.setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      onConsumedFocusSection()
    }, 40)
    return () => window.clearTimeout(t)
  }, [open, focusSection, onConsumedFocusSection])

  if (!open || typeof document === 'undefined') return null
  return (
    // Non-modal panel: the map stays fully visible and interactive while the
    // user adjusts options. The panel itself catches pointer events; the rest
    // of the screen is unobstructed.
    <div className="pointer-events-none fixed inset-0 z-[200] flex justify-end">
      <div
        className="pointer-events-auto relative z-10 flex h-full w-[min(100vw,22rem)] flex-col border-l border-slate-200 bg-white shadow-2xl"
        role="dialog"
        aria-label="Map display options"
      >
        <div className="flex shrink-0 items-center justify-between gap-2 border-b border-slate-200 px-3 py-2.5">
          <h2 className="text-sm font-semibold text-slate-900">Map display options</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            aria-label="Close"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain p-3">
          <div id="drilldown-section-year" className="rounded-lg border border-slate-200 bg-slate-50/50 p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Year
              </span>
              {vintages.length >= 2 ? (
                <button
                  type="button"
                  onClick={() => {
                    if (!playing) {
                      // Begin from the oldest year so the user sees the full sweep.
                      const oldest = vintages[0]
                      if (oldest && oldest !== displayVintage) onVintageChange(oldest)
                    }
                    setPlaying(!playing)
                  }}
                  className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-700 shadow-sm hover:bg-slate-50"
                  aria-pressed={playing}
                  title={
                    playing
                      ? 'Pause auto-advance'
                      : 'Play years: cycle from the oldest vintage to the newest'
                  }
                >
                  {playing ? <PauseIcon className="h-3.5 w-3.5" /> : <PlayIcon className="h-3.5 w-3.5" />}
                  {playing ? 'Pause' : 'Play years'}
                </button>
              ) : null}
            </div>
            <div className="flex flex-wrap items-center gap-1" role="group" aria-label="ACS vintage">
              {vintages.map((y) => {
                const active = y === displayVintage
                return (
                  <button
                    key={y}
                    type="button"
                    onClick={() => {
                      if (playing) setPlaying(false)
                      onVintageChange(y)
                    }}
                    className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold tabular-nums ${
                      active
                        ? 'border-[#354F52] bg-[#354F52] text-white'
                        : 'border-slate-300 bg-white text-slate-800 hover:bg-slate-50'
                    }`}
                  >
                    {y}
                  </button>
                )
              })}
            </div>
            <p className="mt-2 text-[10px] leading-snug text-slate-500 whitespace-pre-wrap">
              {yearHelp}
            </p>
          </div>
          <div id="drilldown-section-view" className="rounded-lg border border-slate-200 bg-slate-50/50 p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Map view
            </div>
            <div className="flex overflow-hidden rounded-md border border-slate-200">
              <button
                type="button"
                onClick={() => setViz('filled')}
                className={`flex-1 px-3 py-2 text-xs font-medium ${
                  viz === 'filled' ? 'bg-[#354F52] text-white' : 'bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                Filled map
              </button>
              <button
                type="button"
                onClick={() => setViz('bubble')}
                className={`flex-1 border-l border-slate-200 px-3 py-2 text-xs font-medium ${
                  viz === 'bubble' ? 'bg-[#354F52] text-white' : 'bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                Bubbles
              </button>
            </div>
          </div>
          <div id="drilldown-section-scale" className="rounded-lg border border-slate-200 bg-slate-50/50 p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Color spread
            </div>
            <select
              className="w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-xs text-slate-900 shadow-sm"
              value={scale}
              onChange={(e) => setScale(e.target.value as CensusScaleId)}
            >
              {CENSUS_SCALES.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
          <div id="drilldown-section-values" className="rounded-lg border border-slate-200 bg-slate-50/50 p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              What numbers are on the map
            </div>
            <select
              className="w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-xs shadow-sm"
              value={valueMode}
              onChange={(e) => setValueMode(e.target.value as CensusValueMode)}
            >
              <option value="raw">ACS value</option>
              <option value="yoy">% change vs prior year</option>
              <option value="vs_natl">% vs national benchmark</option>
            </select>
            <p className="mt-2 text-[10px] leading-snug text-slate-500 whitespace-pre-wrap">
              {metricFullHelp}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
