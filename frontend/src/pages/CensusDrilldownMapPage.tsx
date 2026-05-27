// @ts-nocheck — Census utility functions and react-router types are loose; this file
// follows the same convention as CensusMapPage.tsx.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
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
import { ChoroplethLegend, BubbleLegend } from '../components/CensusMapLegends'
import { InfoHelpTrigger } from '../components/InfoHelpTrigger'
import MapAddressSearch, { type MapAddressResult } from '../components/MapAddressSearch'
import CensusMapLeftRail, { type CensusMapRailSection } from '../components/CensusMapLeftRail'
import CensusDrilldownStage, { type DrilldownView } from '../components/CensusDrilldownStage'
import CensusDrilldownLocalView from '../components/CensusDrilldownLocalView'
import PinnedAddressParcelCard from '../components/PinnedAddressParcelCard'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'

const STATES_ALBERS_TOPO = 'https://cdn.jsdelivr.net/npm/us-atlas@3/states-albers-10m.json'
const COUNTIES_ALBERS_TOPO = 'https://cdn.jsdelivr.net/npm/us-atlas@3/counties-albers-10m.json'

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

function pickMetric(metrics: CensusMetric[], slug: string): CensusMetric | undefined {
  return metrics.find((m) => m.slug === slug)
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
  const [pinnedAddress, setPinnedAddress] = useState<{ lat: number; lng: number; label: string } | null>(null)
  const [pinnedCounty, setPinnedCounty] = useState<{
    geoid: string
    name: string
    value: number | null
    rank: { rank: number; total: number } | null
    lngLat: { lng: number; lat: number } | null
  } | null>(null)
  const [hoverInfo, setHoverInfo] = useState<{
    kind: 'state' | 'county'
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
      // Click locks the info card; explicit CTAs inside the card handle the
      // drill (street view today; ZIP and school zones once those layers exist).
      setPinnedCounty({
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
    setView('nation')
  }, [])
  const goState = useCallback(() => {
    setSelectedCountyGeoid(null)
    setLocalPin(null)
    setPinnedCounty(null)
    setView('state')
  }, [])
  const goCounty = useCallback(() => {
    setLocalPin(null)
    setView('county')
  }, [])

  const onPickAddress = useCallback(
    (r: MapAddressResult) => {
      const fips = r.stateCode ? USPS_TO_FIPS2[r.stateCode] ?? null : null
      setPinnedAddress({ lat: r.lat, lng: r.lon, label: r.shortLabel || r.displayName })
      if (fips) {
        setSelectedStateFips(fips)
        setSelectedCountyGeoid(null)
      }
      // Address search drops the user straight into LOCAL view with the streets
      // basemap so road context is legible; user can toggle to Satellite.
      setLocalPin({ lat: r.lat, lng: r.lon, label: r.shortLabel || r.displayName, zoom: 17, basemap: 'streets' })
      setView('local')
    },
    [],
  )

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

  // Local view keeps the aside slot so the parcel card has somewhere to render.
  const showRightAside = true
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
          <div className="rounded-lg border border-slate-200 bg-white p-2 shadow-sm">
            {view === 'local' && localPin ? (
              <div className="h-[560px] w-full">
                <CensusDrilldownLocalView
                  key={`local-${localPin.basemap}`}
                  center={{ lat: localPin.lat, lng: localPin.lng }}
                  zoom={localPin.zoom}
                  label={localPin.label}
                  initialBasemap={localPin.basemap}
                  topLeftSlot={
                    <button
                      type="button"
                      onClick={() => {
                        setLocalPin(null)
                        setSelectedCountyGeoid(null)
                        setPinnedCounty(null)
                        setView(selectedStateFips ? 'state' : 'nation')
                      }}
                      className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-700 shadow-md hover:bg-slate-50"
                    >
                      <ArrowLeftIcon className="h-3.5 w-3.5" aria-hidden />
                      Back to map
                    </button>
                  }
                />
              </div>
            ) : (
              <CensusDrilldownStage
                view={view as DrilldownView}
                statesTopo={statesTopo as never}
                countiesTopo={countiesTopo as never}
                selectedStateFips={selectedStateFips}
                selectedCountyGeoid={selectedCountyGeoid}
                stateDisplayById={stateDisplayById}
                countyDisplayByGeoid={countyDisplayByGeoid}
                stateChoroExtent={stateChoroExtent}
                countyChoroExtent={countyChoroExtent}
                stateBubbleExtent={stateBubbleExtent}
                countyBubbleExtent={countyBubbleExtent}
                scale={scale}
                viz={viz}
                onPickState={onPickState}
                onPickCounty={onPickCounty}
                onResetToNation={goNation}
                pinnedLngLat={pinnedAddress ? { lng: pinnedAddress.lng, lat: pinnedAddress.lat } : null}
                pinnedCountyGeoid={pinnedCounty?.geoid ?? null}
                stateRankById={stateRankById}
                countyRankByGeoid={countyRankByGeoid}
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
                min={view === 'nation' ? stateChoroExtent.min : countyChoroExtent.min}
                max={view === 'nation' ? stateChoroExtent.max : countyChoroExtent.max}
                scale={scale}
                format={fmt}
                valueMode={valueMode}
                metricHelp={metricFullHelp}
                semantics={choroSemantics}
              />
            ) : (
              <BubbleLegend
                min={view === 'nation' ? stateBubbleExtent.min : countyBubbleExtent.min}
                max={view === 'nation' ? stateBubbleExtent.max : countyBubbleExtent.max}
                scale={scale}
                format={fmt}
                metricHelp={metricFullHelp}
              />
            )
          ) : null}
        </div>

        {/* right column — unified hover/pin readout (replaces dark floating tooltip) */}
        {showRightAside ? (
          <aside className="flex flex-col gap-3 xl:sticky xl:top-4">
            {view === 'local' && localPin ? (
              <PinnedAddressParcelCard
                label={localPin.label}
                lat={localPin.lat}
                lng={localPin.lng}
                onBack={() => {
                  setLocalPin(null)
                  setPinnedAddress(null)
                  setSelectedCountyGeoid(null)
                  setPinnedCounty(null)
                  setView(selectedStateFips ? 'state' : 'nation')
                }}
              />
            ) : (
              <>
            {(() => {
              // Card precedence: a pinned county wins, then transient hover, then idle.
              const isPinned = !!pinnedCounty
              const showing = pinnedCounty
                ? {
                    kind: 'county' as const,
                    name: pinnedCounty.name,
                    value: pinnedCounty.value,
                    rank: pinnedCounty.rank,
                  }
                : hoverInfo
              const idle = !showing
              const accent = isPinned
                ? 'border-amber-300 ring-2 ring-amber-100/70'
                : 'border-slate-200'
              return (
                <div className={`rounded-lg border bg-white p-3 shadow-sm transition-colors ${accent}`}>
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                        {idle
                          ? 'Region details'
                          : isPinned
                            ? 'Pinned'
                            : showing!.kind === 'state'
                              ? 'Hovered state'
                              : 'Hovered county'}
                      </div>
                      <div className="mt-0.5 text-sm font-semibold leading-snug text-slate-900">
                        {idle
                          ? view === 'nation'
                            ? 'Hover any state for details · click to zoom'
                            : `Hover any county in ${stateName ?? 'this state'} for details`
                          : (
                            <>
                              {showing!.name}
                              {showing!.kind === 'county' && stateName ? (
                                <span className="text-slate-500">, {stateName}</span>
                              ) : null}
                            </>
                          )}
                      </div>
                      {!idle ? (
                        <>
                          <div className="mt-1.5 text-[13px] tabular-nums text-slate-700">
                            <span className="text-slate-500">{metricLabel}: </span>
                            {formatMetricValueCompact(metricSlug, showing!.value, metrics, valueMode)}
                          </div>
                          {showing!.rank ? (
                            <div className="mt-0.5 text-[11px] text-slate-500">
                              Ranked #{showing!.rank.rank} of {showing!.rank.total}
                            </div>
                          ) : null}
                        </>
                      ) : (
                        <div className="mt-2 text-[11px] leading-snug text-slate-500">
                          Showing{' '}
                          <span className="font-medium text-slate-700">
                            {currentMetric && censusMapShowOfficialCensusLabel(currentMetric.slug)
                              ? currentMetric.label
                              : metricLabel}
                          </span>{' '}
                          for {displayVintage}.
                        </div>
                      )}
                    </div>
                    {isPinned ? (
                      <button
                        type="button"
                        onClick={() => setPinnedCounty(null)}
                        className="-mr-1 -mt-1 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                        aria-label="Clear pin"
                      >
                        <XMarkIcon className="h-4 w-4" />
                      </button>
                    ) : null}
                  </div>
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
                      <button
                        type="button"
                        disabled
                        title="ZIP tier needs ZCTA polygons + per-ZIP metric pivot — not yet ingested."
                        className="inline-flex cursor-not-allowed items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500"
                      >
                        Drill down to ZIP
                        <span className="ml-2 rounded bg-slate-200 px-1 py-px text-[9px] font-medium normal-case tracking-normal text-slate-600">
                          Soon
                        </span>
                      </button>
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
                      Hovering {hoverInfo.kind === 'state' ? 'state' : 'county'}
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
              </>
            )}
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
