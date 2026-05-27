// @ts-nocheck — react-simple-maps ships without TypeScript types (same as USMap.tsx)
import {
  startTransition,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { Link, Navigate, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ComposableMap, Geographies, Geography } from 'react-simple-maps'
import { geoCentroid } from 'd3-geo'
import { feature } from 'topojson-client'
import { MapContainer, GeoJSON, useMap, CircleMarker, Tooltip as LeafletTooltip } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import {
  AdjustmentsHorizontalIcon,
  ArrowLeftIcon,
  ChartBarSquareIcon,
  PauseIcon,
  PlayIcon,
  SwatchIcon,
  TableCellsIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { CartesianGrid, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis, Line, LineChart } from 'recharts'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import {
  CENSUS_CHORO_FILL_TRANSITION,
  CENSUS_SCALES,
  bubbleFillFromT,
  bubbleRadiusPx,
  colorFromT,
  formatCensusMapAxisTickForMetric,
  formatMetricValueCompact,
  formatMetricValueDisplay,
  metricToDisplayT,
  minMaxExtent,
  quantileExtent,
  type CensusScaleId,
} from '../utils/censusMapTransforms'
import { giniLetterSuffix } from '../utils/giniLetterGrade'
import {
  type CensusValueMode,
  displayValueForMode,
  nationalBaselineWithFallback,
  prevVintageInList,
  trendCell,
} from '../utils/censusMapValueMode'
import {
  type CensusChoroLegendSemantics,
  censusChoroLegendSemantics,
  censusMetricExploreQuestion,
  censusMetricFullHelp,
  censusMetricRankDirection,
  censusMetricStaleDataNote,
  censusMetricWinnerCaption,
  censusMapShowOfficialCensusLabel,
  compareRankedMetricValues,
  CENSUS_EXPLORER_HIDDEN_METRIC_SLUGS,
  CENSUS_MAP_UI_HELP,
} from '../utils/censusDataDictionary'
import {
  buildCensusNarrativePack,
  buildCensusTrendChartTitle,
  buildPlaceTrendNarrative,
  type CensusNarrativePack,
} from '../utils/censusMapNarrative'
import { CensusRaceBarChart } from '../components/CensusRaceBarChart'
import { GiniIncomeInequalityLetterLegend } from '../components/GiniInequalityReadout'
import { InfoHelpTrigger } from '../components/InfoHelpTrigger'
import MapAddressSearch, { type MapAddressResult } from '../components/MapAddressSearch'
import CensusMapLeftRail, { type CensusMapRailSection } from '../components/CensusMapLeftRail'
import { censusMapPathPrefix, mapPathPlace, mapPathState, mapPathUs } from '../utils/dataExplorerPaths'

const STATES_TOPO = 'https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json'
const COUNTY_TOPO = 'https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json'

/** Truncate long state / place names for chart Y-axis (single line). */
function truncateStateLabel(name: string, maxChars = 18) {
  if (!name) return ''
  if (name.length <= maxChars) return name
  return `${name.slice(0, Math.max(1, maxChars - 1))}…`
}

/** High-contrast tooltips (default Recharts is pale on transparent). */
const CENSUS_RECHARTS_TOOLTIP = {
  contentStyle: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: 10,
    boxShadow: '0 14px 28px rgba(0,0,0,0.35)',
    padding: '10px 14px',
    color: '#f8fafc',
  },
  labelStyle: { color: '#e2e8f0', fontWeight: 700, fontSize: 12, marginBottom: 6 },
  itemStyle: { color: '#f8fafc', fontSize: 13 },
}

/** Lon/lat pair for geography centroids. */
function toLonLatPair(c: unknown): [number, number] | null {
  if (!Array.isArray(c) || c.length < 2) return null
  const lon = Number(c[0])
  const lat = Number(c[1])
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null
  return [lon, lat]
}

/** Project [lon,lat] to SVG; geoAlbersUsa may return null / non-array — never feed that to r-s-m Marker. */
function safeProjectScreen(
  projection: ((c: [number, number]) => unknown) | null | undefined,
  lonLat: [number, number],
): [number, number] | null {
  if (projection == null || typeof projection !== 'function') return null
  try {
    const p = projection(lonLat)
    if (!Array.isArray(p) || p.length < 2) return null
    const x = Number(p[0])
    const y = Number(p[1])
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null
    return [x, y]
  } catch {
    return null
  }
}

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
  Object.entries(FIPS2_TO_USPS).map(([fips, usps]) => [usps, fips]),
)

/** Topo / Census ids may be 1 or "01"; normalize to 2-digit state FIPS for routes and JSON keys. */
function normalizeStateFips(raw: unknown): string | null {
  const s = String(raw ?? '').trim()
  if (!s) return null
  const n = Number.parseInt(s, 10)
  if (!Number.isFinite(n) || n < 1 || n > 99) return null
  return String(n).padStart(2, '0')
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
  paths: {
    county_metrics: string
    place_geojson: string
    state_metrics?: string
    state_trends?: string
    county_trends?: string
    place_trends?: string
  }
}

interface StateMetricsPayload {
  geography: string
  vintage: string
  values: Record<string, Record<string, number | null | undefined>>
}

interface CountyMetricsPayload {
  geography: string
  vintage: string
  values: Record<string, Record<string, number | null | undefined>>
}

/** Multi-year state series from ``state_trends.json`` */
interface StateTrendsPayload {
  geography: string
  vintages: string[]
  by_state: Record<string, Record<string, unknown>>
}

interface CountyPlaceTrendsPayload {
  geography: string
  state: string
  vintages: string[]
  byGeoid: Record<string, Record<string, unknown>>
}

type GeoJSONFeatureCollection = GeoJSON.FeatureCollection

function stateMetricsFromTrends(
  trends: StateTrendsPayload,
  vintage: string,
  metricSlugs: string[],
): StateMetricsPayload {
  const values: Record<string, Record<string, number | null | undefined>> = {}
  for (const [st, row] of Object.entries(trends.by_state)) {
    const cell: Record<string, number | null | undefined> = {}
    const nm = row.NAME
    if (typeof nm === 'string' && nm.trim()) cell.NAME = nm.trim()
    for (const slug of metricSlugs) {
      const series = row[slug]
      if (series && typeof series === 'object' && !Array.isArray(series)) {
        const v = (series as Record<string, unknown>)[vintage]
        cell[slug] = typeof v === 'number' && Number.isFinite(v) ? v : null
      } else {
        cell[slug] = null
      }
    }
    values[st] = cell
  }
  return { geography: 'state', vintage, values }
}

function countyMetricsFromTrends(
  trends: CountyPlaceTrendsPayload,
  vintage: string,
  metricSlugs: string[],
  stateFips: string,
): CountyMetricsPayload {
  const values: Record<string, Record<string, number | null | undefined>> = {}
  const stp = stateFips.padStart(2, '0')
  for (const [gid, row] of Object.entries(trends.byGeoid)) {
    if (!gid.startsWith(stp)) continue
    const cell: Record<string, number | null | undefined> = {}
    const nm = row.NAME
    if (typeof nm === 'string' && nm.trim()) cell.NAME = nm.trim()
    cell.GEOID = gid
    for (const slug of metricSlugs) {
      const series = row[slug]
      if (series && typeof series === 'object' && !Array.isArray(series)) {
        const v = (series as Record<string, unknown>)[vintage]
        cell[slug] = typeof v === 'number' && Number.isFinite(v) ? v : null
      } else {
        cell[slug] = null
      }
    }
    const g5 = gid.replace(/\D/g, '').slice(-5).padStart(5, '0')
    values[g5] = cell
  }
  return { geography: 'county', vintage, values }
}

function mergePlaceGeoWithTrends(
  base: GeoJSONFeatureCollection | undefined,
  trends: CountyPlaceTrendsPayload | undefined,
  vintage: string,
  metricSlugs: string[],
): GeoJSONFeatureCollection | undefined {
  if (!base) return undefined
  if (!trends?.byGeoid) return base
  return {
    ...base,
    features: base.features.map((f) => {
      const p = (f.properties ?? {}) as Record<string, unknown>
      const gid = String(p.GEOID ?? '')
      const row = trends.byGeoid[gid]
      if (!row) return f
      const np: Record<string, unknown> = { ...p }
      for (const slug of metricSlugs) {
        const series = row[slug]
        if (series && typeof series === 'object' && !Array.isArray(series)) {
          const v = (series as Record<string, unknown>)[vintage]
          if (typeof v === 'number' && Number.isFinite(v)) np[slug] = v
        }
      }
      return { ...f, properties: np }
    }),
  }
}

function manifestVintagesFromManifest(manifest: CensusManifest): string[] {
  const v = manifest.vintages
  if (Array.isArray(v) && v.length > 0) return [...v]
  return manifest.vintage ? [manifest.vintage] : []
}

/** Dedupe + ascending calendar order for ACS end-years (slider / play). */
function chronoUniqueVintages(years: string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const y of years) {
    if (!y || seen.has(y)) continue
    seen.add(y)
    out.push(y)
  }
  out.sort((a, b) => Number(a) - Number(b))
  return out
}

/**
 * After the vintage list is swapped mid-play (manifest → trends), map the same calendar year
 * to its new index; if that year vanished, use the latest year still ≤ heldYear.
 */
function indexForHeldYearInNewVintages(vintages: string[], heldYear: string): number {
  if (!vintages.length) return 0
  const exact = vintages.indexOf(heldYear)
  if (exact >= 0) return exact
  const hy = Number(heldYear)
  if (!Number.isFinite(hy)) return 0
  let bestIdx = 0
  let bestVal = -Infinity
  for (let i = 0; i < vintages.length; i++) {
    const y = Number(vintages[i])
    if (!Number.isFinite(y)) continue
    if (y <= hy && y >= bestVal) {
      bestVal = y
      bestIdx = i
    }
  }
  if (bestVal > -Infinity) return bestIdx
  return 0
}

function metricHasTrendSeriesInRow(row: Record<string, unknown>, slug: string): boolean {
  const series = row[slug]
  return Boolean(series && typeof series === 'object' && !Array.isArray(series))
}

function stateHasAnySeriesForSlug(trends: StateTrendsPayload, slug: string): boolean {
  return Object.values(trends.by_state).some((row) =>
    metricHasTrendSeriesInRow(row as Record<string, unknown>, slug),
  )
}

function stateTrendSliderVintages(trends: StateTrendsPayload, metricSlug: string): string[] {
  const base = trends.vintages ?? []
  if (!base.length) return base
  if (!stateHasAnySeriesForSlug(trends, metricSlug)) return base
  const filtered = base.filter((y) =>
    Object.values(trends.by_state).some((row) => {
      const series = (row as Record<string, unknown>)[metricSlug]
      const v = trendCell(series, y)
      return typeof v === 'number' && Number.isFinite(v)
    }),
  )
  return filtered.length ? filtered : base
}

function countyPlaceSliderVintages(
  trends: CountyPlaceTrendsPayload,
  stateFips: string,
  metricSlug: string,
): string[] {
  const base = trends.vintages ?? []
  if (!base.length) return base
  const stp = stateFips.padStart(2, '0')
  const hasAny = Object.entries(trends.byGeoid).some(
    ([gid, row]) =>
      gid.startsWith(stp) && metricHasTrendSeriesInRow(row as Record<string, unknown>, metricSlug),
  )
  if (!hasAny) return base
  const filtered = base.filter((y) =>
    Object.entries(trends.byGeoid).some(([gid, row]) => {
      if (!gid.startsWith(stp)) return false
      const series = (row as Record<string, unknown>)[metricSlug]
      const v = trendCell(series, y)
      return typeof v === 'number' && Number.isFinite(v)
    }),
  )
  return filtered.length ? filtered : base
}

function sliderVintages(args: {
  mode: 'us' | 'stateCounty' | 'place'
  manifest: CensusManifest
  metricSlug: string
  stateTrends: StateTrendsPayload | null | undefined
  countyTrends: CountyPlaceTrendsPayload | null | undefined
  placeTrends: CountyPlaceTrendsPayload | null | undefined
  stateFips: string | undefined
}): string[] {
  const mv = chronoUniqueVintages(manifestVintagesFromManifest(args.manifest))
  let resolved: string[]
  if (args.mode === 'us') {
    if (args.stateTrends?.vintages?.length) resolved = stateTrendSliderVintages(args.stateTrends, args.metricSlug)
    else resolved = mv.length ? mv : ['2022']
  } else if (args.mode === 'stateCounty' && args.stateFips && args.countyTrends?.vintages?.length) {
    resolved = countyPlaceSliderVintages(args.countyTrends, args.stateFips, args.metricSlug)
  } else if (args.mode === 'place' && args.stateFips && args.placeTrends?.vintages?.length) {
    resolved = countyPlaceSliderVintages(args.placeTrends, args.stateFips, args.metricSlug)
  } else {
    resolved = mv.length ? mv : ['2022']
  }
  return chronoUniqueVintages(resolved)
}

/** Top-N for race bar charts (states / counties / places). */
const CENSUS_TOP_BAR_ROW_LIMIT = 10

/**
 * Pool display values for the choropleth legend across every manifest vintage using trend
 * sidecars, so min/max (and percentile clipping) stay fixed while the year slider moves.
 */
function collectAllVintageDisplayValuesState(
  trends: StateTrendsPayload,
  vintages: string[],
  metricSlug: string,
  valueMode: CensusValueMode,
  nationalRef: CensusManifest['national_ref'],
): number[] {
  const vals: number[] = []
  for (const vy of vintages) {
    const prevV = prevVintageInList(vintages, vy)
    const nat = nationalBaselineWithFallback(nationalRef, vy, metricSlug, { stateTrends: trends })
    for (const row of Object.values(trends.by_state)) {
      const rec = row as Record<string, unknown>
      const series = rec[metricSlug]
      const raw = trendCell(series, vy)
      let prev: number | null = null
      if (valueMode === 'yoy' && prevV) prev = trendCell(series, prevV)
      const d = displayValueForMode(valueMode, raw, prev, nat)
      if (typeof d === 'number' && Number.isFinite(d)) vals.push(d)
    }
  }
  return vals
}

function collectAllVintageDisplayValuesCounty(
  trends: CountyPlaceTrendsPayload,
  stateFips: string,
  vintages: string[],
  metricSlug: string,
  valueMode: CensusValueMode,
  nationalRef: CensusManifest['national_ref'],
  stateTrends: StateTrendsPayload | null | undefined,
): number[] {
  const stp = stateFips.padStart(2, '0')
  const vals: number[] = []
  for (const vy of vintages) {
    const prevV = prevVintageInList(vintages, vy)
    const nat = nationalBaselineWithFallback(nationalRef, vy, metricSlug, { stateTrends })
    for (const [gid, row] of Object.entries(trends.byGeoid)) {
      if (!gid.startsWith(stp)) continue
      const rec = row as Record<string, unknown>
      const series = rec[metricSlug]
      const raw = trendCell(series, vy)
      let prev: number | null = null
      if (valueMode === 'yoy' && prevV) prev = trendCell(series, prevV)
      const d = displayValueForMode(valueMode, raw, prev, nat)
      if (typeof d === 'number' && Number.isFinite(d)) vals.push(d)
    }
  }
  return vals
}

function collectAllVintageDisplayValuesPlace(
  trends: CountyPlaceTrendsPayload,
  stateFips: string,
  vintages: string[],
  metricSlug: string,
  valueMode: CensusValueMode,
  nationalRef: CensusManifest['national_ref'],
  stateTrends: StateTrendsPayload | null | undefined,
): number[] {
  const stp = stateFips.padStart(2, '0')
  const vals: number[] = []
  for (const vy of vintages) {
    const prevV = prevVintageInList(vintages, vy)
    const nat = nationalBaselineWithFallback(nationalRef, vy, metricSlug, { stateTrends })
    for (const [gid, row] of Object.entries(trends.byGeoid)) {
      if (!gid.startsWith(stp)) continue
      const rec = row as Record<string, unknown>
      const series = rec[metricSlug]
      const raw = trendCell(series, vy)
      let prev: number | null = null
      if (valueMode === 'yoy' && prevV) prev = trendCell(series, prevV)
      const d = displayValueForMode(valueMode, raw, prev, nat)
      if (typeof d === 'number' && Number.isFinite(d)) vals.push(d)
    }
  }
  return vals
}

function LabelWithInfo({
  label,
  help,
  labelClassName = 'text-xs font-semibold uppercase tracking-wide text-slate-500',
}: {
  label: string
  help: string
  labelClassName?: string
}) {
  return (
    <span className="inline-flex items-center gap-1 shrink-0">
      <span className={labelClassName}>{label}</span>
      <InfoHelpTrigger help={help} topic={label} align="left" />
    </span>
  )
}

function CensusMetricToolbarControl({
  metricFullHelp,
  metrics,
  metricSlug,
  onPickMetric,
  unconstrainedWidth = false,
}: {
  metricFullHelp: string
  metrics: CensusMetric[]
  metricSlug: string
  onPickMetric: (slug: string) => void
  /** When true, drop the narrow max-width so the control can fill a toolbar tile. */
  unconstrainedWidth?: boolean
}) {
  const current = metrics.find((m) => m.slug === metricSlug)
  return (
    <div
      className={
        unconstrainedWidth
          ? 'flex min-w-0 max-w-full flex-col gap-0.5'
          : 'flex min-w-0 max-w-full flex-col gap-0.5 sm:max-w-[min(26rem,calc(100vw-9rem))]'
      }
    >
      <LabelWithInfo
        label="What do you want to explore?"
        help={`${CENSUS_MAP_UI_HELP.metric}\n\n${metricFullHelp}`}
        labelClassName={
          unconstrainedWidth
            ? 'text-[10px] font-semibold uppercase tracking-wide text-slate-500 leading-tight'
            : undefined
        }
      />
      <select
        aria-label="Topic to show on the map"
        className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs font-medium text-slate-900 shadow-sm w-full"
        value={metricSlug}
        onChange={(e) => onPickMetric(e.target.value)}
      >
        {metrics.map((m) => (
          <option key={m.slug} value={m.slug}>
            {censusMetricExploreQuestion(m.slug, m.label)}
          </option>
        ))}
      </select>
      {current && censusMapShowOfficialCensusLabel(current.slug) ? (
        <span className="text-[10px] leading-snug text-slate-500">
          Census label: <span className="font-medium text-slate-600">{current.label}</span>
        </span>
      ) : null}
    </div>
  )
}

/** Thin heading row directly above the map (keeps `aria-labelledby` target). */
function CensusMapHeadingStrip({
  titleId,
  title,
  insight,
  selectionActive,
}: {
  titleId: string
  title: string
  /** Extra context (e.g. selected state vs national) shown under the title. */
  insight?: string | null
  /** True when a leaderboard row is pinned so the strip reads as “this location is selected.” */
  selectionActive?: boolean
}) {
  return (
    <div
      className={
        selectionActive
          ? 'border-b border-amber-200/90 bg-amber-50/80 px-3 py-1 sm:px-3 border-l-[5px] border-l-amber-500'
          : 'border-b border-slate-100 bg-slate-50/60 px-3 py-1 sm:px-3'
      }
    >
      <h2 id={titleId} className="text-sm font-semibold text-slate-900 leading-snug tracking-tight">
        {title}
      </h2>
      {insight ? (
        <p className="mt-0.5 text-xs leading-snug text-slate-600" id={`${titleId}-insight`}>
          {insight}
        </p>
      ) : null}
    </div>
  )
}

/** Source line + “how to read” tips; panel opens on button click to keep the map chrome compact. */
function CensusMapExplainerDetails({ subtitle, calloutLines }: { subtitle: string; calloutLines: string[] }) {
  const panelId = useId()
  const [open, setOpen] = useState(false)
  return (
    <div className="border-b border-slate-200 bg-slate-50/40">
      <div className="flex items-center justify-end gap-2 px-3 py-1">
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((v) => !v)}
        >
          <span>How to read this map</span>
          <span
            className={`text-[10px] text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
            aria-hidden
          >
            ▼
          </span>
        </button>
      </div>
      {open ? (
        <div
          id={panelId}
          className="space-y-2 border-t border-slate-100 bg-white px-3 pb-3 pt-2"
          role="region"
          aria-label="How to read this map"
        >
          <p className="text-xs leading-relaxed text-slate-600">{subtitle}</p>
          {calloutLines.length > 0 ? (
            <ul className="space-y-1.5 text-xs leading-snug text-slate-800">
              {calloutLines.map((line, i) => (
                <li key={i} className="flex gap-2">
                  <span className="select-none font-semibold text-slate-500" aria-hidden>
                    ·
                  </span>
                  <span className="min-w-0 flex-1">{line}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

function CensusMapAdvancedMapOptionsFlyout({
  open,
  onClose,
  metricFullHelp,
  viz,
  setViz,
  scale,
  setScale,
  valueMode,
  setValueMode,
  focusSection,
  onConsumedFocusSection,
  yearControls,
}: {
  open: boolean
  onClose: () => void
  metricFullHelp: string
  viz: 'filled' | 'bubble'
  setViz: (v: 'filled' | 'bubble') => void
  scale: CensusScaleId
  setScale: (s: CensusScaleId) => void
  valueMode: CensusValueMode
  setValueMode: (m: CensusValueMode) => void
  /** When opening from a toolbar affordance, scroll this block into view. */
  focusSection?: 'year' | 'view' | 'scale' | 'values' | null
  onConsumedFocusSection?: () => void
  /** When provided, renders an in-flyout Year + Play section above the other sections. */
  yearControls?: {
    vintages: string[]
    displayVintage: string
    singleVintage: boolean
    showPlay: boolean
    playing: boolean
    setPlaying: (v: boolean) => void
    onVintageChange: (v: string) => void
    onBeginPlay?: () => void
    yearHelp: string
  }
}) {
  useEffect(() => {
    if (!open) return
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prevOverflow
      window.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])

  useEffect(() => {
    if (!open || !focusSection) return
    const id =
      focusSection === 'year'
        ? 'census-advanced-section-year'
        : focusSection === 'view'
          ? 'census-advanced-section-view'
          : focusSection === 'scale'
            ? 'census-advanced-section-scale'
            : 'census-advanced-section-values'
    const t = window.setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      onConsumedFocusSection?.()
    }, 40)
    return () => window.clearTimeout(t)
  }, [open, focusSection, onConsumedFocusSection])

  if (!open || typeof document === 'undefined') return null

  return createPortal(
    <div className="fixed inset-0 z-[200] flex justify-end">
      <button
        type="button"
        className="absolute inset-0 z-0 bg-slate-900/45"
        aria-label="Close map options"
        onClick={onClose}
      />
      <div
        className="relative z-10 flex h-full w-[min(100vw,22rem)] flex-col border-l border-slate-200 bg-white shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="census-advanced-map-options-title"
      >
        <div className="flex shrink-0 items-center justify-between gap-2 border-b border-slate-200 px-3 py-2.5">
          <h2 id="census-advanced-map-options-title" className="text-sm font-semibold text-slate-900">
            Map display options
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2"
            aria-label="Close"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain p-3">
          {yearControls ? (
            <div
              id="census-advanced-section-year"
              className="rounded-lg border border-slate-200 bg-slate-50/50 p-3 scroll-mt-3"
            >
              <div className="mb-2">
                <LabelWithInfo label="Year (ACS end year)" help={yearControls.yearHelp} />
              </div>
              <VintageAndPlayControls
                vintages={yearControls.vintages}
                displayVintage={yearControls.displayVintage}
                singleVintage={yearControls.singleVintage}
                showPlay={yearControls.showPlay}
                playing={yearControls.playing}
                setPlaying={yearControls.setPlaying}
                onVintageChange={yearControls.onVintageChange}
                onBeginPlay={yearControls.onBeginPlay}
                yearHelp={yearControls.yearHelp}
              />
            </div>
          ) : null}
          <div id="census-advanced-section-view" className="rounded-lg border border-slate-200 bg-slate-50/50 p-3 scroll-mt-3">
            <div className="mb-2">
              <LabelWithInfo
                label="Map view"
                help={`${CENSUS_MAP_UI_HELP.vizFilled} ${CENSUS_MAP_UI_HELP.vizBubble}\n\n${metricFullHelp}`}
              />
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
          <div id="census-advanced-section-scale" className="rounded-lg border border-slate-200 bg-slate-50/50 p-3 scroll-mt-3">
            <div className="mb-2">
              <LabelWithInfo label="Color spread" help={`${CENSUS_MAP_UI_HELP.scale}\n\n${metricFullHelp}`} />
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
          <div id="census-advanced-section-values" className="rounded-lg border border-slate-200 bg-slate-50/50 p-3 scroll-mt-3">
            <div className="mb-2">
              <LabelWithInfo label="What numbers are on the map" help={`${CENSUS_MAP_UI_HELP.mapValue}\n\n${metricFullHelp}`} />
            </div>
            <select
              className="w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-xs shadow-sm"
              value={valueMode}
              onChange={(e) => setValueMode(e.target.value as CensusValueMode)}
            >
              <option value="raw">ACS value (color spread adjusted)</option>
              <option value="yoy">% change vs prior year</option>
              <option value="vs_natl">% vs national benchmark</option>
            </select>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

function trendPointsFromSeries(
  vintages: string[],
  series: Record<string, unknown> | undefined,
): { year: string; value: number | null }[] {
  if (!series || typeof series !== 'object' || Array.isArray(series)) return []
  return vintages.map((y) => {
    const v = (series as Record<string, unknown>)[y]
    return { year: y, value: typeof v === 'number' && Number.isFinite(v) ? v : null }
  })
}

function VintageAndPlayControls({
  vintages,
  displayVintage,
  singleVintage,
  showPlay,
  playing,
  setPlaying,
  onVintageChange,
  onBeginPlay,
  yearHelp = CENSUS_MAP_UI_HELP.year,
}: {
  vintages: string[]
  displayVintage: string
  singleVintage: boolean
  showPlay: boolean
  playing: boolean
  setPlaying: (v: boolean) => void
  onVintageChange: (v: string) => void
  /** When starting Play, jump to the first year in the list (oldest). */
  onBeginPlay?: () => void
  yearHelp?: string
}) {
  const yearScrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const root = yearScrollRef.current
    if (!root || !vintages.length) return
    const active = root.querySelector<HTMLElement>(`[data-census-vintage="${displayVintage}"]`)
    if (!active) return
    const run = () => active.scrollIntoView({ behavior: 'auto', inline: 'center', block: 'nearest' })
    requestAnimationFrame(() => requestAnimationFrame(run))
  }, [displayVintage, vintages])

  return (
    <div className="flex min-w-0 max-w-full flex-wrap items-center gap-x-1.5 gap-y-1">
      <div className="flex min-w-0 max-w-full flex-1 flex-col gap-0.5">
        <LabelWithInfo
          label="Year (ACS end year)"
          help={yearHelp}
          labelClassName="text-[10px] font-semibold uppercase tracking-wide text-slate-500 leading-tight"
        />
        <div
          ref={yearScrollRef}
          className="flex min-w-0 max-w-full flex-nowrap items-center gap-1 overflow-x-auto overflow-y-hidden overscroll-x-contain py-0.5 [scrollbar-gutter:stable] [scrollbar-width:thin] pr-1 [-webkit-overflow-scrolling:touch]"
          role="group"
          aria-label="Select ACS vintage"
        >
          {vintages.map((y) => {
            const active = y === displayVintage
            return (
              <button
                key={y}
                type="button"
                data-census-vintage={y}
                disabled={singleVintage && !active}
                onClick={() => {
                  setPlaying(false)
                  onVintageChange(y)
                }}
                className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-semibold tabular-nums transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40 ${
                  active
                    ? 'border-[#354F52] bg-[#354F52] text-white shadow-sm'
                    : 'border-slate-300 bg-white text-slate-800 hover:bg-slate-50'
                }`}
              >
                {y}
              </button>
            )
          })}
        </div>
      </div>
      {showPlay ? (
        <button
          type="button"
          onClick={() => {
            if (playing) {
              setPlaying(false)
            } else {
              onBeginPlay?.()
              setPlaying(true)
            }
          }}
          className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 shrink-0"
          title={
            playing
              ? 'Pause animation'
              : `${CENSUS_MAP_UI_HELP.play} Starts at the oldest year in the list and advances until the newest, then stops.`
          }
        >
          {playing ? <PauseIcon className="h-4 w-4" /> : <PlayIcon className="h-4 w-4" />}
          {playing ? 'Pause' : 'Play years'}
        </button>
      ) : null}
    </div>
  )
}

const explorerFilterTile =
  'rounded-xl border border-slate-200 bg-white px-2 py-1.5 shadow-sm sm:px-2.5 sm:py-2 min-w-0 flex flex-col justify-center'

function CensusExplorerFilterBar({
  leadingSlot,
  metricFullHelp,
  metricChoices,
  metricSlug,
  onMetricChange,
  vintages,
  displayVintage,
  singleVintage,
  showPlay,
  playing,
  setPlaying,
  onVintageChange,
  onBeginPlay,
  yearHelp,
  onOpenAdvanced,
}: {
  leadingSlot?: ReactNode
  metricFullHelp: string
  /** Metrics shown in the topic dropdown (excludes internal / table-total slugs). */
  metricChoices: CensusMetric[]
  metricSlug: string
  onMetricChange: (slug: string) => void
  vintages: string[]
  displayVintage: string
  singleVintage: boolean
  showPlay: boolean
  playing: boolean
  setPlaying: (v: boolean) => void
  onVintageChange: (v: string) => void
  onBeginPlay?: () => void
  yearHelp: string
  onOpenAdvanced: (section: 'view' | 'scale' | 'values') => void
}) {
  return (
    <div
      className="flex flex-col gap-1.5 xl:flex-row xl:flex-wrap xl:items-stretch"
      role="toolbar"
      aria-label="Map and chart filters"
    >
      {leadingSlot ? (
        <div className={`${explorerFilterTile} shrink-0 xl:max-w-[min(100%,22rem)]`}>
          <div className="flex flex-wrap items-center gap-2">{leadingSlot}</div>
        </div>
      ) : null}
      <div className={`${explorerFilterTile} min-w-0 flex-1 xl:min-w-[11rem] xl:max-w-md`}>
        <CensusMetricToolbarControl
          metricFullHelp={metricFullHelp}
          metrics={metricChoices}
          metricSlug={metricSlug}
          onPickMetric={onMetricChange}
          unconstrainedWidth
        />
      </div>
      <div className={`${explorerFilterTile} min-w-0 flex-1 xl:min-w-[18rem]`}>
        <VintageAndPlayControls
          vintages={vintages}
          displayVintage={displayVintage}
          singleVintage={singleVintage}
          showPlay={showPlay}
          playing={playing}
          setPlaying={setPlaying}
          onVintageChange={onVintageChange}
          onBeginPlay={onBeginPlay}
          yearHelp={yearHelp}
        />
      </div>
      <div
        className={`${explorerFilterTile} flex flex-row flex-wrap items-center gap-1 xl:ml-auto xl:max-w-[24rem] xl:justify-end`}
      >
        <button
          type="button"
          title="Filled map vs bubbles"
          onClick={() => onOpenAdvanced('view')}
          className="inline-flex shrink-0 items-center rounded-md border border-slate-300 bg-white px-2 py-1.5 text-[11px] font-medium text-slate-800 shadow-sm hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2"
        >
          Map view
        </button>
        <button
          type="button"
          title="How values stretch across colors"
          onClick={() => onOpenAdvanced('scale')}
          className="inline-flex shrink-0 items-center rounded-md border border-slate-300 bg-white px-2 py-1.5 text-[11px] font-medium text-slate-800 shadow-sm hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2"
        >
          Color spread
        </button>
        <button
          type="button"
          title="Raw ACS value, year-over-year change, or vs national"
          onClick={() => onOpenAdvanced('values')}
          className="inline-flex shrink-0 items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-[11px] font-medium text-slate-800 shadow-sm hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2"
        >
          <AdjustmentsHorizontalIcon className="h-3.5 w-3.5 shrink-0 text-slate-600" aria-hidden />
          Map numbers
        </button>
      </div>
    </div>
  )
}

function AcTrendChart({
  title,
  subtitle,
  readingLines,
  chartTitleId,
  points,
  format,
  metricHelp,
  metricTooltipLabel,
}: {
  title: string
  subtitle?: string
  readingLines?: string[]
  chartTitleId?: string
  points: { year: string; value: number | null }[]
  format: (v: number) => string
  metricHelp?: string
  /** Shown in the point tooltip as ``{label}: {formatted value}``. */
  metricTooltipLabel?: string
}) {
  const readingPanelId = useId()
  const [readingOpen, setReadingOpen] = useState(false)
  const nonNull = points.filter((p) => p.value != null)
  if (nonNull.length < 2) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50/80 p-3 text-xs text-slate-500">
        <div id={chartTitleId}>
          <span className="font-semibold text-slate-700">{title}</span>
          {subtitle ? <p className="mt-1 text-slate-600 leading-snug">{subtitle}</p> : null}
        </div>
        <p className="mt-2">Need at least two years with data for a trend line.</p>
        {readingLines?.length ? (
          <div className="mt-3 border-t border-slate-200 pt-2">
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2"
              aria-expanded={readingOpen}
              aria-controls={readingPanelId}
              onClick={() => setReadingOpen((v) => !v)}
            >
              <span>How to read this chart</span>
              <span
                className={`text-[10px] text-slate-400 transition-transform ${readingOpen ? 'rotate-180' : ''}`}
                aria-hidden
              >
                ▼
              </span>
            </button>
            {readingOpen ? (
              <div
                id={readingPanelId}
                className="mt-2 rounded-md border border-amber-100/90 bg-amber-50/45 px-2.5 py-2"
                role="region"
                aria-label="How to read this chart"
              >
                <ul className="space-y-1 text-xs text-slate-800 leading-snug">
                  {readingLines.map((line, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="font-semibold text-amber-700 select-none" aria-hidden>
                        ·
                      </span>
                      <span className="min-w-0 flex-1">{line}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    )
  }
  return (
    <div
      className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
      role="region"
      {...(chartTitleId ? { 'aria-labelledby': chartTitleId } : {})}
    >
      <div className="mb-1.5 flex min-w-0 items-start gap-1 border-b border-slate-100 pb-1.5">
        <div className="min-w-0 flex-1">
          <div
            id={chartTitleId}
            className="text-[11px] font-semibold uppercase tracking-wide text-slate-800 leading-tight"
            title={title}
          >
            {title}
          </div>
          {subtitle ? (
            <p className="mt-0.5 text-xs font-normal normal-case text-slate-600 leading-relaxed">{subtitle}</p>
          ) : null}
        </div>
        {metricHelp ? <InfoHelpTrigger help={metricHelp} topic="Trend chart" align="right" /> : null}
      </div>
      {readingLines?.length ? (
        <div className="mb-1.5">
          <button
            type="button"
            className="mb-1.5 inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-amber-200/90 bg-amber-50/60 px-2.5 py-1.5 text-xs font-medium text-amber-950/90 shadow-sm hover:bg-amber-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2 sm:w-auto sm:justify-start"
            aria-expanded={readingOpen}
            aria-controls={readingPanelId}
            onClick={() => setReadingOpen((v) => !v)}
          >
            <span>How to read this chart</span>
            <span
              className={`text-[10px] text-slate-500 transition-transform ${readingOpen ? 'rotate-180' : ''}`}
              aria-hidden
            >
              ▼
            </span>
          </button>
          {readingOpen ? (
            <div
              id={readingPanelId}
              className="rounded-md border border-amber-100/90 bg-amber-50/45 px-2.5 py-2"
              role="region"
              aria-label="How to read this chart"
            >
              <ul className="space-y-1 text-xs text-slate-800 leading-snug">
                {readingLines.map((line, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="font-semibold text-amber-700 select-none" aria-hidden>
                      ·
                    </span>
                    <span className="min-w-0 flex-1">{line}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
      <div className="h-[160px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200" />
            <XAxis dataKey="year" tick={{ fontSize: 9 }} interval="preserveStartEnd" />
            <YAxis
              width={44}
              tick={{ fontSize: 9 }}
              tickFormatter={(x) => {
                const n = Number(x)
                if (!Number.isFinite(n)) return ''
                if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
                if (Math.abs(n) >= 1000) return `${Math.round(n / 1000)}k`
                return String(Math.round(n))
              }}
            />
            <RechartsTooltip
              {...CENSUS_RECHARTS_TOOLTIP}
              formatter={(value: number | string) => {
                const n = Number(value)
                const formatted = Number.isFinite(n) ? format(n) : String(value)
                const line = metricTooltipLabel ? `${metricTooltipLabel}: ${formatted}` : formatted
                return [line, '']
              }}
              labelFormatter={(y) => `Year ${y}`}
            />
            <Line type="monotone" dataKey="value" stroke="#52796F" strokeWidth={2} dot={{ r: 3 }} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function countyGeoidFromFeature(f: GeoJSON.Feature): string {
  const id = f.id
  if (typeof id === 'number' && Number.isFinite(id)) return String(Math.trunc(id)).padStart(5, '0')
  if (typeof id === 'string' && /^\d+$/.test(id)) return id.padStart(5, '0')
  const p = f.properties as Record<string, unknown> | null
  const raw = p?.GEOID ?? p?.GEO_ID ?? p?.geoid
  if (raw == null) return ''
  const digits = String(raw).replace(/\D/g, '')
  if (!digits) return ''
  return digits.length <= 5 ? digits.padStart(5, '0') : digits.slice(-5).padStart(5, '0')
}

/** 7-digit place GEOID aligned with ``placeDisplayByGeoid`` / map styling. */
function placeGeoid7FromProperties(p: Record<string, unknown> | null, fallbackIdx: number): string {
  const raw = String(p?.GEOID ?? '').replace(/\D/g, '')
  if (!raw) return `idx_${fallbackIdx}`
  return raw.length <= 7 ? raw.padStart(7, '0') : raw.slice(-7).padStart(7, '0')
}

function buildStateCountyGeoJson(
  topology: { objects: { counties: unknown } },
  values: Record<string, Record<string, unknown>>,
  stateFips: string,
  metricSlug: string,
): GeoJSONFeatureCollection | null {
  try {
    const fc = feature(topology as never, topology.objects.counties as never) as GeoJSON.FeatureCollection
    const features: GeoJSON.Feature[] = []
    for (const f of fc.features) {
      const gid = countyGeoidFromFeature(f)
      if (gid.length !== 5 || !gid.startsWith(stateFips)) continue
      const row = values[gid] ?? {}
      const base = (f.properties as Record<string, unknown> | undefined) ?? {}
      const name = typeof row.NAME === 'string' ? row.NAME : typeof base.name === 'string' ? base.name : gid
      const props: Record<string, unknown> = {
        ...base,
        GEOID: gid,
        NAME: name,
        ...row,
        [metricSlug]: row[metricSlug],
      }
      features.push({ ...f, properties: props, id: gid })
    }
    if (!features.length) return null
    return { type: 'FeatureCollection', features }
  } catch {
    return null
  }
}

function censusNull(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

function formatMetricValue(
  slug: string,
  v: number | null | undefined,
  metrics: CensusMetric[],
  valueMode: CensusValueMode = 'raw',
): string {
  const s = formatMetricValueDisplay(slug, v, metrics, valueMode)
  if (slug !== 'gini_income_inequality' || valueMode !== 'raw' || v == null || !Number.isFinite(v)) return s
  return `${s}${giniLetterSuffix(v)}`
}

function metricValueTooltipLine(
  metricLabel: string,
  slug: string,
  v: number | null | undefined,
  metrics: CensusMetric[],
  valueMode: CensusValueMode,
): string {
  return `${metricLabel}: ${formatMetricValue(slug, v, metrics, valueMode)}`
}

/** County / place drill-down: fit data, clamp zoom/pan so wheel zoom cannot leave the state/city context. */
function DrilldownMapBoundsController({ data }: { data: GeoJSONFeatureCollection }) {
  const map = useMap()
  useEffect(() => {
    if (!data?.features?.length) return
    const layer = L.geoJSON(data as never)
    const b = layer.getBounds()
    if (!b.isValid()) return

    let cancelled = false
    let clampOnMoveEnd: (() => void) | null = null

    /** Padding passed to getBoundsZoom (Leaflet subtracts this once from map width/height). */
    const fitPad = L.point(28, 28)

    const run = () => {
      if (cancelled) return
      map.invalidateSize()
      const size = map.getSize()
      if (size.x < 32 || size.y < 32) return

      // “Contain” zooms bound how far users can zoom out / in while still framing the geography.
      const zLoose = map.getBoundsZoom(b.pad(0.22), false)
      const zTight = map.getBoundsZoom(b.pad(0.06), false)
      if (!Number.isFinite(zLoose) || !Number.isFinite(zTight)) return

      const zOut = Math.min(zLoose, zTight)
      const zIn = Math.max(zLoose, zTight)
      let safeMin = Math.max(5, Math.floor(zOut) - 1)

      // Initial view: fit the whole area in the map (inside=false). Use generous bounds padding so
      // narrow side-by-side layouts do not “over-zoom” into a few counties (e.g. Alabama in a short map pane).
      const zFit = map.getBoundsZoom(b.pad(0.14), false, fitPad)
      if (!Number.isFinite(zFit)) return

      let safeMax = Math.min(13, Math.max(Math.ceil(zIn) + 1, Math.ceil(zFit) + 2))
      if (safeMax <= safeMin) safeMax = safeMin + 1

      // Use floor(zFit) so the entire padded bounds stay in view; avoid +1 here — it was zooming one level too tight.
      let z = Math.min(safeMax, Math.max(safeMin, Math.floor(zFit)))

      map.setMinZoom(safeMin)
      map.setMaxZoom(safeMax)
      map.setMaxBounds(b.pad(0.32))
      map.options.maxBoundsViscosity = 0.75

      map.setView(b.getCenter(), z, { animate: false })

      if (clampOnMoveEnd) {
        map.off('moveend', clampOnMoveEnd)
        clampOnMoveEnd = null
      }
      clampOnMoveEnd = () => {
        const zz = map.getZoom()
        if (zz > safeMax) map.setZoom(safeMax)
        else if (zz < safeMin) map.setZoom(safeMin)
      }
      if (!cancelled) map.once('moveend', clampOnMoveEnd)
    }

    const schedule = () => {
      requestAnimationFrame(() => requestAnimationFrame(run))
    }
    map.whenReady(schedule)

    const host = map.getContainer().parentElement
    const ro =
      typeof ResizeObserver !== 'undefined' && host
        ? new ResizeObserver(() => {
            if (cancelled) return
            requestAnimationFrame(run)
          })
        : null
    if (ro && host) ro.observe(host)

    return () => {
      cancelled = true
      ro?.disconnect()
      if (clampOnMoveEnd) map.off('moveend', clampOnMoveEnd)
      map.setMinZoom(5)
      map.setMaxZoom(13)
      map.setMaxBounds(null as any)
      map.options.maxBoundsViscosity = undefined
    }
  }, [map, data])
  return null
}

function featureLatLng(feature: GeoJSON.Feature): { lat: number; lng: number } | null {
  try {
    const layer = L.geoJSON(feature as never)
    const c = layer.getBounds().getCenter()
    if (c && Number.isFinite(c.lat) && Number.isFinite(c.lng)) return { lat: c.lat, lng: c.lng }
  } catch {
    /* ignore */
  }
  return null
}

const CHORO_LEGEND_GRADIENT_STOPS = 17

function ChoroplethLegend({
  min,
  max,
  scale,
  format,
  valueMode = 'raw',
  extentPoolsAllVintages = false,
  metricHelp,
  semantics,
  letterGradeLegend,
}: {
  min: number
  max: number
  scale: CensusScaleId
  format: (v: number) => string
  valueMode?: CensusValueMode
  /** When trend sidecars are used, min/max are from all vintages pooled (still ~4th–96th pct.). */
  extentPoolsAllVintages?: boolean
  metricHelp?: string
  /** Plain-language ends of the ramp + one sentence on how to read color intensity. */
  semantics?: CensusChoroLegendSemantics | null
  /** Optional strip (e.g. Gini A–F grades) shown under the semantics line. */
  letterGradeLegend?: import('react').ReactNode
}) {
  const legendHelpPanelId = useId()
  const [legendHelpOpen, setLegendHelpOpen] = useState(false)
  const n = CHORO_LEGEND_GRADIENT_STOPS
  const stops = Array.from({ length: n }, (_, i) => {
    const u = n <= 1 ? 0 : i / (n - 1)
    const v = min + u * (max - min)
    const t = metricToDisplayT(v, min, max, scale) ?? 0
    return { offset: `${u * 100}%`, color: colorFromT(t), value: v }
  })
  const tickUs = [0, 0.25, 0.5, 0.75, 1] as const
  const gradId = `census-ramp-${scale}-${Math.round(min)}-${Math.round(max)}`
  const legendInfoBody = [
    'Legend maps the displayed value to color using the selected transform. When multi-year data is loaded, low/high can be pooled across years so colors stay comparable as you change year.',
    metricHelp,
  ]
    .filter(Boolean)
    .join('\n\n')
  const legendFootnote = `Stops are evenly spaced in mapped value range; shading follows the selected transform (${CENSUS_SCALES.find((x) => x.id === scale)?.label ?? scale}). ${
    valueMode === 'raw'
      ? extentPoolsAllVintages
        ? 'Percentile band (~4th–96th pct.) is computed across all years in the slider when multi-year trend data is present, so colors stay comparable as you change year.'
        : 'Extremes use percentile clipping so outliers do not wash out the map.'
      : valueMode === 'yoy'
        ? 'Legend shows percent change vs the prior year in the slider order.'
        : 'Legend shows percent difference from the national benchmark (population-weighted state composite when available).'
  }${
    extentPoolsAllVintages && valueMode !== 'raw'
      ? ' Endpoints pool all years from trend data so the scale stays fixed while you scrub the year slider.'
      : ''
  }`
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-3 shadow-sm">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-600 mb-2">
        <SwatchIcon className="h-4 w-4 shrink-0" />
        {metricHelp ? (
          <LabelWithInfo label="What the colors mean" help={metricHelp} />
        ) : (
          <span>What the colors mean</span>
        )}
      </div>
      {semantics ? (
        <>
          <div className="mb-1 flex items-center justify-between gap-2 px-0.5 text-[10px] font-semibold text-slate-700">
            <span className="min-w-0 text-left leading-tight">{semantics.lowEnd}</span>
            <span className="shrink-0 text-slate-400" aria-hidden>
              ←→
            </span>
            <span className="min-w-0 text-right leading-tight">{semantics.highEnd}</span>
          </div>
          <p className="mb-2 text-[10px] leading-snug text-slate-600">{semantics.gradientHint}</p>
        </>
      ) : null}
      <svg width="100%" height="52" viewBox="0 0 260 52" preserveAspectRatio="xMidYMid meet" className="max-w-full">
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
            {stops.map((s, i) => (
              <stop key={i} offset={s.offset} stopColor={s.color} />
            ))}
          </linearGradient>
        </defs>
        <rect x="8" y="8" width="244" height="14" rx="3" fill={`url(#${gradId})`} stroke="#94a3b8" strokeWidth="0.5" />
        {tickUs.map((frac) => (
          <text key={frac} x={8 + frac * 244} y="44" fontSize="9" fill="#475569" textAnchor="middle">
            {format(min + frac * (max - min))}
          </text>
        ))}
      </svg>
      {letterGradeLegend ? (
        <div className="mt-2 border-t border-slate-200/90 pt-2">{letterGradeLegend}</div>
      ) : null}
      <div className="mt-2">
        <button
          type="button"
          className="inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-amber-200/90 bg-amber-50/60 px-2.5 py-1.5 text-xs font-medium text-amber-950/90 shadow-sm hover:bg-amber-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2 sm:w-auto sm:justify-start"
          aria-expanded={legendHelpOpen}
          aria-controls={legendHelpPanelId}
          onClick={() => setLegendHelpOpen((v) => !v)}
        >
          <span>How to read this legend</span>
          <span
            className={`text-[10px] text-slate-500 transition-transform ${legendHelpOpen ? 'rotate-180' : ''}`}
            aria-hidden
          >
            ▼
          </span>
        </button>
        {legendHelpOpen ? (
          <div
            id={legendHelpPanelId}
            className="mt-2 rounded-md border border-amber-100/90 bg-amber-50/45 px-2.5 py-2 space-y-2"
            role="region"
            aria-label="How to read this legend"
          >
            <p className="text-[11px] text-slate-800 leading-snug whitespace-pre-wrap">{legendInfoBody}</p>
            <p className="text-[10px] text-slate-600 leading-snug">{legendFootnote}</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}

function BubbleLegend({
  min,
  max,
  scale,
  format,
  metricHelp,
  letterGradeLegend,
}: {
  min: number
  max: number
  scale: CensusScaleId
  format: (v: number) => string
  metricHelp?: string
  letterGradeLegend?: import('react').ReactNode
}) {
  const legendHelpPanelId = useId()
  const [legendHelpOpen, setLegendHelpOpen] = useState(false)
  const refs = [0.15, 0.5, 0.88].map((u) => min + u * (max - min))
  const items = refs.map((v) => ({
    v,
    r: bubbleRadiusPx(v, min, max, scale, 4, 22),
    t: metricToDisplayT(v, min, max, scale),
    label: format(v),
  }))
  const bubbleInfoBody = [
    'Circle area encodes the mapped value; color follows the Deep Ocean ramp (steel blue → teal → deep emerald) as on the map.',
    metricHelp,
  ]
    .filter(Boolean)
    .join('\n\n')
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-3 shadow-sm">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-600 mb-2">
        {metricHelp ? (
          <LabelWithInfo label="Bubble size scale" help={metricHelp} />
        ) : (
          <span>Bubble size scale</span>
        )}
      </div>
      <div className="flex items-end justify-around gap-2 px-2" style={{ height: 56 }}>
        {items.map((it, i) => (
          <div key={i} className="flex flex-col items-center gap-1">
            <div
              className="rounded-full border border-white shadow"
              style={{
                width: it.r * 2,
                height: it.r * 2,
                backgroundColor: bubbleFillFromT(it.t, 0.9),
              }}
            />
            <span className="text-[10px] text-slate-600 text-center max-w-[72px] leading-tight">{it.label}</span>
          </div>
        ))}
      </div>
      {letterGradeLegend ? (
        <div className="mt-2 border-t border-slate-200/90 pt-2">{letterGradeLegend}</div>
      ) : null}
      <div className="mt-2">
        <button
          type="button"
          className="inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-amber-200/90 bg-amber-50/60 px-2.5 py-1.5 text-xs font-medium text-amber-950/90 shadow-sm hover:bg-amber-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2 sm:w-auto sm:justify-start"
          aria-expanded={legendHelpOpen}
          aria-controls={legendHelpPanelId}
          onClick={() => setLegendHelpOpen((v) => !v)}
        >
          <span>How to read this legend</span>
          <span
            className={`text-[10px] text-slate-500 transition-transform ${legendHelpOpen ? 'rotate-180' : ''}`}
            aria-hidden
          >
            ▼
          </span>
        </button>
        {legendHelpOpen ? (
          <div
            id={legendHelpPanelId}
            className="mt-2 rounded-md border border-amber-100/90 bg-amber-50/45 px-2.5 py-2"
            role="region"
            aria-label="How to read this legend"
          >
            <p className="text-[11px] text-slate-800 leading-snug whitespace-pre-wrap">{bubbleInfoBody}</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}

/** When the slider has 2+ vintages (from manifest or trend sidecars), advance years with Play. */
const PLAY_INTERVAL_MS = 1950

function CensusMapPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const { vintage, metric, stateFips: stateFipsRaw } = useParams<{
    vintage?: string
    metric?: string
    stateFips?: string
  }>()
  const stateFips = stateFipsRaw
    ? normalizeStateFips(stateFipsRaw) ?? (stateFipsRaw.length <= 2 ? stateFipsRaw.padStart(2, '0') : stateFipsRaw)
    : undefined

  const stateUsps = stateFips ? FIPS2_TO_USPS[stateFips] : undefined
  const stateName = stateUsps ? STATE_CODE_TO_NAME[stateUsps] : undefined

  const mapPrefix = useMemo(() => censusMapPathPrefix(location.pathname), [location.pathname])

  const mode = useMemo(() => {
    if (location.pathname.includes('/census-map/place/') || location.pathname.includes('/data-explorer/map/place/'))
      return 'place'
    if (location.pathname.includes('/census-map/state/') || location.pathname.includes('/data-explorer/map/state/'))
      return 'stateCounty'
    return 'us'
  }, [location.pathname])

  const viz: 'filled' | 'bubble' = searchParams.get('viz') === 'bubble' ? 'bubble' : 'filled'
  const scaleRaw = searchParams.get('scale') || 'linear'
  const scale: CensusScaleId = (['linear', 'sqrt', 'log', 'exp'].includes(scaleRaw) ? scaleRaw : 'linear') as CensusScaleId

  const setViz = (v: 'filled' | 'bubble') => {
    const next = new URLSearchParams(searchParams)
    if (v === 'filled') next.delete('viz')
    else next.set('viz', 'bubble')
    setSearchParams(next, { replace: true })
  }

  const setScale = (s: CensusScaleId) => {
    const next = new URLSearchParams(searchParams)
    if (s === 'linear') next.delete('scale')
    else next.set('scale', s)
    setSearchParams(next, { replace: true })
  }

  const valueModeRaw = searchParams.get('valueMode') || 'raw'
  const valueMode: CensusValueMode = (
    ['raw', 'yoy', 'vs_natl'].includes(valueModeRaw) ? valueModeRaw : 'raw'
  ) as CensusValueMode

  const setValueMode = (m: CensusValueMode) => {
    const next = new URLSearchParams(searchParams)
    if (m === 'raw') next.delete('valueMode')
    else next.set('valueMode', m)
    setSearchParams(next, { replace: true })
  }

  const [advancedMapOptionsOpen, setAdvancedMapOptionsOpen] = useState(false)
  const [advancedFocusSection, setAdvancedFocusSection] = useState<'year' | 'view' | 'scale' | 'values' | null>(null)
  const [pinnedAddress, setPinnedAddress] = useState<{
    displayName: string
    shortLabel: string
    lat: number
    lon: number
    stateCode: string | null
    stateFips: string | null
    county: string
    city: string
  } | null>(null)
  const [censusOnboardingDismissed, setCensusOnboardingDismissed] = useState(() => {
    if (typeof window === 'undefined') return false
    try {
      return window.localStorage.getItem('open-navigator-census-map-onboarding-dismissed') === '1'
    } catch {
      return false
    }
  })
  const dismissCensusOnboarding = useCallback(() => {
    try {
      if (typeof window !== 'undefined') {
        window.localStorage.setItem('open-navigator-census-map-onboarding-dismissed', '1')
      }
    } catch {
      /* ignore */
    }
    setCensusOnboardingDismissed(true)
  }, [])

  const { data: manifest, isError: manifestError } = useQuery({
    queryKey: ['census-map-manifest'],
    queryFn: async (): Promise<CensusManifest> => {
      const r = await fetch('/data/census-map/manifest.json')
      if (!r.ok) throw new Error('manifest')
      return r.json()
    },
  })

  const metricSlug = metric ?? 'median_household_income'
  const metricSlugsList = useMemo(() => (manifest?.metrics ?? []).map((m) => m.slug), [manifest?.metrics])

  const { data: stateTrends, isFetched: stateTrendsFetched } = useQuery({
    queryKey: ['census-state-trends'],
    queryFn: async (): Promise<StateTrendsPayload | null> => {
      const r = await fetch('/data/census-map/state_trends.json')
      if (r.status === 404) return null
      if (!r.ok) throw new Error('state trends')
      return r.json() as StateTrendsPayload
    },
    enabled: !!manifest,
    retry: false,
  })

  const { data: countyTrends, isFetched: countyTrendsFetched } = useQuery({
    queryKey: ['census-county-trends', stateFips],
    queryFn: async (): Promise<CountyPlaceTrendsPayload | null> => {
      const r = await fetch(`/data/census-map/county_trends_${stateFips}.json`)
      if (r.status === 404) return null
      if (!r.ok) throw new Error('county trends')
      return r.json() as CountyPlaceTrendsPayload
    },
    enabled: !!manifest && mode === 'stateCounty' && !!stateFips,
    retry: false,
  })

  const { data: placeTrends, isFetched: placeTrendsFetched } = useQuery({
    queryKey: ['census-place-trends', stateFips],
    queryFn: async (): Promise<CountyPlaceTrendsPayload | null> => {
      const r = await fetch(`/data/census-map/place_trends_${stateFips}.json`)
      if (r.status === 404) return null
      if (!r.ok) throw new Error('place trends')
      return r.json() as CountyPlaceTrendsPayload
    },
    enabled: !!manifest && mode === 'place' && !!stateFips,
    retry: false,
  })

  const stateTrendsDriveStatePayload =
    mode === 'us' && !!stateTrends && stateHasAnySeriesForSlug(stateTrends, metricSlug)

  const countyTrendsDriveCountyPayload =
    mode === 'stateCounty' &&
    !!countyTrends &&
    !!stateFips &&
    Object.entries(countyTrends.byGeoid).some(
      ([gid, row]) =>
        gid.startsWith(stateFips.padStart(2, '0')) &&
        metricHasTrendSeriesInRow(row as Record<string, unknown>, metricSlug),
    )

  const vintages = useMemo(() => {
    if (!manifest) return ['2022']
    return sliderVintages({
      mode,
      manifest,
      metricSlug,
      stateTrends,
      countyTrends,
      placeTrends,
      stateFips,
    })
  }, [mode, manifest, metricSlug, stateTrends, countyTrends, placeTrends, stateFips])

  const effectiveVintage = useMemo(() => {
    if (!manifest) return vintage ?? '2022'
    const list = vintages
    if (!list.length) return vintage ?? manifest.vintage ?? '2022'
    const latest = list[list.length - 1]!
    if (!vintage) return latest
    if (list.includes(vintage)) return vintage
    return latest
  }, [manifest, vintage, vintages])

  const [playing, setPlaying] = useState(false)
  const [animIndex, setAnimIndex] = useState(0)
  const vintagesRef = useRef(vintages)
  vintagesRef.current = vintages

  /** While dragging the year slider, update charts immediately; URL follows on a short debounce. */
  const [scrubVintage, setScrubVintage] = useState<string | null>(null)
  const vintageNavigateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (vintageNavigateTimerRef.current) window.clearTimeout(vintageNavigateTimerRef.current)
    }
  }, [])

  useEffect(() => {
    if (scrubVintage != null && vintage === scrubVintage) setScrubVintage(null)
  }, [vintage, scrubVintage])

  useEffect(() => {
    setScrubVintage(null)
  }, [metricSlug, mode, stateFips])

  useEffect(() => {
    if (playing) return
    const ix = vintages.indexOf(effectiveVintage)
    setAnimIndex(ix >= 0 ? ix : 0)
  }, [effectiveVintage, vintages.join(','), playing])

  const vintagesPlayKeyRef = useRef<string>('')
  const animIndexPlayRef = useRef(0)
  animIndexPlayRef.current = animIndex
  useLayoutEffect(() => {
    const key = vintages.join(',')
    if (playing) {
      const prevKey = vintagesPlayKeyRef.current
      if (prevKey && prevKey !== key) {
        const prevList = prevKey.split(',')
        const safeIx = Math.min(
          Math.max(0, animIndexPlayRef.current),
          Math.max(0, prevList.length - 1),
        )
        const heldYear = prevList[safeIx]
        if (heldYear) {
          const nextIx = indexForHeldYearInNewVintages(vintages, heldYear)
          setAnimIndex(nextIx)
        }
      }
    }
    vintagesPlayKeyRef.current = key
  }, [playing, vintages])

  const canPlayMultiVintage =
    vintages.length > 1 &&
    (mode === 'us' || (mode === 'stateCounty' && !!stateFips) || (mode === 'place' && !!stateFips))

  const canTrendAnimate = canPlayMultiVintage

  const displayVintage = useMemo(() => {
    if (playing && canTrendAnimate && vintages.length) {
      const ix = Math.min(Math.max(0, animIndex), vintages.length - 1)
      return vintages[ix]!
    }
    if (scrubVintage && vintages.includes(scrubVintage)) return scrubVintage
    return effectiveVintage
  }, [playing, canTrendAnimate, animIndex, vintages, scrubVintage, effectiveVintage])

  useEffect(() => {
    if (!playing || !canTrendAnimate) return
    const t = window.setInterval(() => {
      setAnimIndex((i) => {
        const list = vintagesRef.current
        if (!list.length) return 0
        const last = list.length - 1
        if (i >= last) {
          queueMicrotask(() => setPlaying(false))
          return last
        }
        return i + 1
      })
    }, PLAY_INTERVAL_MS)
    return () => window.clearInterval(t)
  }, [playing, canTrendAnimate])

  useEffect(() => {
    setPlaying(false)
  }, [effectiveVintage, mode, metricSlug, valueMode])

  useEffect(() => {
    if (valueMode !== 'raw' && viz === 'bubble') {
      const next = new URLSearchParams(searchParams)
      next.delete('viz')
      setSearchParams(next, { replace: true })
    }
  }, [valueMode, viz, searchParams, setSearchParams])

  const showPlay = canTrendAnimate

  const { data: statePayloadRaw } = useQuery({
    queryKey: ['census-state-metrics', displayVintage],
    queryFn: async (): Promise<StateMetricsPayload> => {
      const r = await fetch(`/data/census-map/${displayVintage}/state_metrics.json`)
      if (!r.ok) throw new Error('state metrics')
      return r.json()
    },
    enabled: mode === 'us' && !!displayVintage && !stateTrendsDriveStatePayload,
    placeholderData: keepPreviousData,
    staleTime: 1000 * 60 * 60,
    retry: false,
  })

  const statePayload = useMemo(() => {
    if (mode === 'us' && stateTrendsDriveStatePayload && stateTrends && displayVintage) {
      return stateMetricsFromTrends(stateTrends, displayVintage, metricSlugsList)
    }
    return statePayloadRaw
  }, [mode, stateTrendsDriveStatePayload, stateTrends, statePayloadRaw, displayVintage, metricSlugsList])

  const { data: countyPayloadRaw, isError: countyPayloadError, isPending: countyPayloadLoading } = useQuery({
    queryKey: ['census-county-metrics', displayVintage],
    queryFn: async (): Promise<CountyMetricsPayload> => {
      const r = await fetch(`/data/census-map/${displayVintage}/county_metrics.json`)
      if (!r.ok) throw new Error('county metrics')
      return r.json()
    },
    enabled: mode === 'stateCounty' && !!displayVintage && !countyTrendsDriveCountyPayload,
    placeholderData: keepPreviousData,
    staleTime: 1000 * 60 * 60,
    retry: false,
  })

  const countyPayload = useMemo(() => {
    if (mode === 'stateCounty' && countyTrendsDriveCountyPayload && countyTrends && stateFips && displayVintage) {
      return countyMetricsFromTrends(countyTrends, displayVintage, metricSlugsList, stateFips)
    }
    return countyPayloadRaw
  }, [mode, countyTrendsDriveCountyPayload, countyTrends, countyPayloadRaw, displayVintage, metricSlugsList, stateFips])

  const { data: countyTopo, isPending: countyTopoLoading } = useQuery({
    queryKey: ['census-county-topo', manifest?.county_topo_cdn],
    queryFn: async () => {
      const u = manifest!.county_topo_cdn || COUNTY_TOPO
      const r = await fetch(u)
      if (!r.ok) throw new Error('county topo')
      return r.json()
    },
    enabled: mode === 'stateCounty' && !!manifest,
    staleTime: Infinity,
  })

  const placeUrl =
    mode === 'place' && stateFips
      ? `/data/census-map/${displayVintage}/place_${stateFips}.geojson`
      : null

  const { data: placeGeo, isError: placeGeoError } = useQuery({
    queryKey: ['census-place-geo', placeUrl],
    queryFn: async (): Promise<GeoJSONFeatureCollection> => {
      const r = await fetch(placeUrl!)
      if (!r.ok) throw new Error('place geojson')
      return r.json()
    },
    enabled: mode === 'place' && !!placeUrl,
    placeholderData: keepPreviousData,
    staleTime: 1000 * 60 * 60,
    retry: false,
  })

  const placeGeoMerged = useMemo(
    () => mergePlaceGeoWithTrends(placeGeo, placeTrends ?? undefined, displayVintage, metricSlugsList),
    [placeGeo, placeTrends, displayVintage, metricSlugsList],
  )

  const [countyHover, setCountyHover] = useState<{ id: string; name: string; value: number | null } | null>(null)
  const [placeHover, setPlaceHover] = useState<{ id: string; name: string; value: number | null } | null>(null)
  /** Bar-chart selection: highlight matching area on the map (click same bar again to clear). */
  const [leaderboardPinnedId, setLeaderboardPinnedId] = useState<string | null>(null)

  useEffect(() => {
    setLeaderboardPinnedId(null)
  }, [mode, stateFips, metricSlug])

  const toggleLeaderboardPin = useCallback((id: string) => {
    setLeaderboardPinnedId((prev) => (prev === id ? null : id))
  }, [])

  const placePinnedLabel = useMemo((): string | null => {
    if (mode !== 'place' || !leaderboardPinnedId || !placeGeoMerged?.features.length) return null
    const pid = leaderboardPinnedId
    for (const f of placeGeoMerged.features) {
      const p = f.properties as Record<string, unknown> | null
      if (placeGeoid7FromProperties(p, 0) === pid) {
        const n = String(p?.NAME ?? '').trim()
        return n || null
      }
    }
    return null
  }, [mode, leaderboardPinnedId, placeGeoMerged])

  const focusPinnedStateNarrative = useMemo(() => {
    if (mode !== 'us' || leaderboardPinnedId == null || leaderboardPinnedId === '' || !statePayload?.values)
      return null
    const sid = normalizeStateFips(leaderboardPinnedId) ?? leaderboardPinnedId
    const row = statePayload.values[sid]
    if (!row) return null
    const name = typeof row.NAME === 'string' && row.NAME.trim() ? row.NAME.trim() : sid
    return { geoid: sid, name }
  }, [mode, leaderboardPinnedId, statePayload])

  const manifestMetrics = manifest?.metrics ?? []
  const selectableMetrics = useMemo(
    () => manifestMetrics.filter((m) => !CENSUS_EXPLORER_HIDDEN_METRIC_SLUGS.has(m.slug)),
    [manifestMetrics],
  )
  const metrics = manifestMetrics
  const placeStates = manifest?.place_states ?? []

  const currentMetricMeta = useMemo(() => metrics.find((m) => m.slug === metricSlug), [metrics, metricSlug])
  const metricFullHelp = useMemo(
    () => censusMetricFullHelp(metricSlug, currentMetricMeta),
    [metricSlug, currentMetricMeta],
  )

  const choroLegendSemantics = useMemo(
    () => censusChoroLegendSemantics(metricSlug, valueMode, currentMetricMeta?.label ?? metricSlug),
    [metricSlug, valueMode, currentMetricMeta?.label],
  )

  const giniRawLetterLegend = useMemo(
    () => (metricSlug === 'gini_income_inequality' && valueMode === 'raw' ? <GiniIncomeInequalityLetterLegend /> : null),
    [metricSlug, valueMode],
  )

  const nationalContextNote = useMemo(() => {
    if (valueMode !== 'raw' || mode !== 'us') return null
    const baseline = nationalBaselineWithFallback(manifest?.national_ref, displayVintage, metricSlug, {
      stateRows: statePayload?.values,
      stateTrends,
    })
    if (baseline == null || !Number.isFinite(baseline)) return null
    const label = currentMetricMeta?.label ?? metricSlug
    const formatted = formatMetricValue(metricSlug, baseline, metrics, 'raw')
    return `National benchmark for ${label}: ${formatted} (population-weighted U.S. composite when available).`
  }, [valueMode, mode, manifest?.national_ref, displayVintage, metricSlug, currentMetricMeta?.label, metrics, statePayload, stateTrends])

  const [hoverRegion, setHoverRegion] = useState<{
    id: string
    name: string
    value: number | null
  } | null>(null)

  const trendAsideCapturingHoverRef = useRef(false)
  const hoverClearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const cancelScheduledHoverClear = useCallback(() => {
    if (hoverClearTimerRef.current != null) {
      window.clearTimeout(hoverClearTimerRef.current)
      hoverClearTimerRef.current = null
    }
  }, [])

  const scheduleHoverRegionClear = useCallback(() => {
    cancelScheduledHoverClear()
    hoverClearTimerRef.current = window.setTimeout(() => {
      hoverClearTimerRef.current = null
      if (!trendAsideCapturingHoverRef.current) {
        setHoverRegion(null)
      }
    }, 240)
  }, [cancelScheduledHoverClear])

  useEffect(() => {
    return () => {
      cancelScheduledHoverClear()
    }
  }, [cancelScheduledHoverClear])

  useEffect(() => {
    cancelScheduledHoverClear()
  }, [metricSlug, mode, cancelScheduledHoverClear])

  const usMapInnerRef = useRef<HTMLDivElement | null>(null)
  const [usMapTipPos, setUsMapTipPos] = useState<{ x: number; y: number } | null>(null)

  const updateUsMapTip = useCallback((clientX: number, clientY: number) => {
    const el = usMapInnerRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const lx = clientX - r.left + el.scrollLeft
    const ly = clientY - r.top + el.scrollTop
    const estW = 280
    const estH = 132
    let left = lx + 14
    let top = ly + 14
    if (left + estW > el.scrollWidth - 8) left = Math.max(8, lx - estW - 14)
    if (top + estH > el.scrollTop + el.clientHeight - 8) top = Math.max(8, ly - estH - 14)
    left = Math.max(8, Math.min(left, Math.max(8, el.scrollWidth - estW - 8)))
    top = Math.max(8, Math.min(top, Math.max(8, el.scrollTop + el.clientHeight - estH - 8)))
    setUsMapTipPos({ x: left, y: top })
  }, [])

  const [tableSort, setTableSort] = useState<{ key: 'name' | 'value' | 'geoid'; dir: 'asc' | 'desc' }>(() => ({
    key: 'value',
    dir: censusMetricRankDirection(metricSlug) === 'lower' ? 'asc' : 'desc',
  }))

  useEffect(() => {
    setTableSort((prev) =>
      prev.key === 'value'
        ? { key: 'value', dir: censusMetricRankDirection(metricSlug) === 'lower' ? 'asc' : 'desc' }
        : prev,
    )
  }, [metricSlug])

  const reduceMotion = useReducedMotion()
  const trendChartOpenCounty = Boolean(countyTrends && countyHover && stateFips)
  const trendFadeTransition = { duration: reduceMotion ? 0 : 0.28, ease: 'easeInOut' }

  const stateDisplayById = useMemo(() => {
    const out: Record<string, number | null> = {}
    if (!statePayload || !metricSlug) return out
    const prevV = prevVintageInList(vintages, displayVintage)
    const nat = nationalBaselineWithFallback(manifest?.national_ref, displayVintage, metricSlug, {
      stateRows: statePayload.values,
      stateTrends,
    })
    for (const [sid, row] of Object.entries(statePayload.values)) {
      const raw = typeof row[metricSlug] === 'number' && Number.isFinite(row[metricSlug]) ? row[metricSlug] : null
      let prev: number | null = null
      if (valueMode === 'yoy' && prevV && stateTrends?.by_state?.[sid]) {
        prev = trendCell((stateTrends.by_state[sid] as Record<string, unknown>)[metricSlug], prevV)
      }
      out[sid] = displayValueForMode(valueMode, raw, prev, nat)
    }
    return out
  }, [
    statePayload,
    metricSlug,
    valueMode,
    displayVintage,
    vintages.join(','),
    stateTrends,
    manifest?.national_ref,
  ])

  useEffect(() => {
    setHoverRegion((prev) => {
      if (!prev?.id) return prev
      const row = statePayload?.values?.[prev.id]
      const name = row && typeof row.NAME === 'string' ? row.NAME : prev.name
      const disp = stateDisplayById[prev.id] ?? null
      if (name === prev.name && disp === prev.value) return prev
      return { ...prev, name, value: disp }
    })
  }, [statePayload, stateDisplayById, displayVintage, metricSlug])

  /** US trend line: hovered state, or the bar-chart pinned state when the pointer has left the map. */
  const usTrendSubject = useMemo(() => {
    if (mode !== 'us') return null
    if (hoverRegion) return hoverRegion
    if (leaderboardPinnedId != null && leaderboardPinnedId !== '' && statePayload?.values) {
      const sid = normalizeStateFips(leaderboardPinnedId) ?? leaderboardPinnedId
      const row = statePayload.values[sid]
      if (!row) return null
      const name = typeof (row as { NAME?: string }).NAME === 'string' ? (row as { NAME: string }).NAME : sid
      const disp = stateDisplayById[sid] ?? null
      return { id: sid, name, value: disp }
    }
    return null
  }, [mode, hoverRegion, leaderboardPinnedId, statePayload, stateDisplayById])

  const trendChartOpenUs = Boolean(stateTrends && usTrendSubject)

  const stateChoroPooledForLegend = useMemo((): number[] | null => {
    if (mode !== 'us' || !stateTrends || !metricSlug || vintages.length < 2) return null
    const arr = collectAllVintageDisplayValuesState(
      stateTrends,
      vintages,
      metricSlug,
      valueMode,
      manifest?.national_ref,
    )
    return arr.length >= 20 ? arr : null
  }, [mode, stateTrends, vintages.join(','), metricSlug, valueMode, manifest?.national_ref])

  const stateChoroExtent = useMemo(() => {
    if (stateChoroPooledForLegend?.length) return quantileExtent(stateChoroPooledForLegend)
    const vals = Object.values(stateDisplayById).filter(
      (x): x is number => typeof x === 'number' && Number.isFinite(x),
    )
    if (!vals.length) return { min: 0, max: 1 }
    return quantileExtent(vals)
  }, [stateChoroPooledForLegend, stateDisplayById])

  const stateBubbleExtent = useMemo(() => {
    if (!statePayload || !metricSlug) return { min: 0, max: 1 }
    const displayVals = Object.values(stateDisplayById).filter(
      (x): x is number => typeof x === 'number' && Number.isFinite(x),
    )
    if (displayVals.length >= 2) {
      return minMaxExtent(displayVals)
    }
    const vals = Object.values(statePayload.values)
      .map((row) => row[metricSlug])
      .filter((x): x is number => typeof x === 'number' && Number.isFinite(x))
    if (!vals.length) return { min: 0, max: 1 }
    return minMaxExtent(vals)
  }, [statePayload, metricSlug, stateDisplayById])

  const placeDisplayByGeoid = useMemo(() => {
    const out: Record<string, number | null> = {}
    const g = placeGeoMerged
    if (!g || !metricSlug) return out
    const prevV = prevVintageInList(vintages, displayVintage)
    const nat = nationalBaselineWithFallback(manifest?.national_ref, displayVintage, metricSlug, {
      stateRows: statePayload?.values,
      stateTrends,
    })
    for (const f of g.features) {
      const p = f.properties as Record<string, unknown> | null
      const raw = typeof p?.[metricSlug] === 'number' && Number.isFinite(p[metricSlug]) ? p[metricSlug] : null
      const rawG = String(p?.GEOID ?? '').replace(/\D/g, '')
      const gid7 = rawG.length <= 7 ? rawG.padStart(7, '0') : rawG.slice(-7).padStart(7, '0')
      let prev: number | null = null
      if (valueMode === 'yoy' && prevV && placeTrends?.byGeoid?.[gid7]) {
        prev = trendCell((placeTrends.byGeoid[gid7] as Record<string, unknown>)[metricSlug], prevV)
      }
      out[gid7] = displayValueForMode(valueMode, raw, prev, nat)
    }
    return out
  }, [
    placeGeoMerged,
    metricSlug,
    valueMode,
    displayVintage,
    vintages.join(','),
    placeTrends,
    manifest?.national_ref,
    stateTrends,
    statePayload,
  ])

  const placeTrendSubject = useMemo(() => {
    if (mode !== 'place') return null
    if (placeHover) return placeHover
    if (leaderboardPinnedId && placeGeoMerged?.features.length) {
      for (const f of placeGeoMerged.features) {
        const p = f.properties as Record<string, unknown> | null
        const gid7 = placeGeoid7FromProperties(p, 0)
        if (gid7 === leaderboardPinnedId) {
          const name = String(p?.NAME ?? gid7)
          const value = placeDisplayByGeoid[gid7] ?? null
          return { id: gid7, name, value }
        }
      }
    }
    return null
  }, [mode, placeHover, leaderboardPinnedId, placeGeoMerged, placeDisplayByGeoid])

  const trendChartOpenPlace = Boolean(placeTrends && placeTrendSubject)

  const placeChoroPooledForLegend = useMemo((): number[] | null => {
    if (mode !== 'place' || !placeTrends || !stateFips || !metricSlug || vintages.length < 2) return null
    const arr = collectAllVintageDisplayValuesPlace(
      placeTrends,
      stateFips,
      vintages,
      metricSlug,
      valueMode,
      manifest?.national_ref,
      stateTrends,
    )
    return arr.length >= 20 ? arr : null
  }, [mode, placeTrends, stateFips, vintages.join(','), metricSlug, valueMode, manifest?.national_ref, stateTrends])

  const placeChoroExtent = useMemo(() => {
    if (placeChoroPooledForLegend?.length) return quantileExtent(placeChoroPooledForLegend)
    const vals = Object.values(placeDisplayByGeoid).filter(
      (x): x is number => typeof x === 'number' && Number.isFinite(x),
    )
    if (!vals.length) return { min: 0, max: 1 }
    return quantileExtent(vals)
  }, [placeChoroPooledForLegend, placeDisplayByGeoid])

  const placeBubbleExtent = useMemo(() => {
    const g = placeGeoMerged
    if (!g || !metricSlug) return { min: 0, max: 1 }
    const displayVals = Object.values(placeDisplayByGeoid).filter(
      (x): x is number => typeof x === 'number' && Number.isFinite(x),
    )
    if (displayVals.length >= 2) {
      return minMaxExtent(displayVals)
    }
    const vals = g.features
      .map((f) => {
        const v = (f.properties as Record<string, unknown> | null)?.[metricSlug]
        return typeof v === 'number' && Number.isFinite(v) ? v : null
      })
      .filter((x): x is number => x != null)
    if (!vals.length) return { min: 0, max: 1 }
    return minMaxExtent(vals)
  }, [placeGeoMerged, metricSlug, placeDisplayByGeoid])

  const placeRankByGeoid = useMemo(() => {
    const m = new Map<string, { rank: number; total: number }>()
    const g = placeGeoMerged
    if (!g) return m
    const rows: { id: string; value: number }[] = []
    for (const f of g.features) {
      const p = f.properties as Record<string, unknown> | null
      const gid7 = placeGeoid7FromProperties(p, 0)
      const v = placeDisplayByGeoid[gid7]
      if (typeof v === 'number' && Number.isFinite(v)) rows.push({ id: gid7, value: v })
    }
    rows.sort((a, b) => compareRankedMetricValues(a.value, b.value, metricSlug))
    const total = rows.length
    rows.forEach((r, i) => m.set(r.id, { rank: i + 1, total }))
    return m
  }, [placeGeoMerged, placeDisplayByGeoid, metricSlug])

  const stateCountyGeo = useMemo(() => {
    if (mode !== 'stateCounty' || !stateFips || !countyTopo || !countyPayload?.values) return null
    return buildStateCountyGeoJson(countyTopo, countyPayload.values, stateFips, metricSlug)
  }, [mode, stateFips, countyTopo, countyPayload, metricSlug])

  const countyDisplayByGeoid = useMemo(() => {
    const out: Record<string, number | null> = {}
    if (!stateCountyGeo || !metricSlug) return out
    const prevV = prevVintageInList(vintages, displayVintage)
    const nat = nationalBaselineWithFallback(manifest?.national_ref, displayVintage, metricSlug, {
      stateRows: statePayload?.values,
      stateTrends,
    })
    for (const f of stateCountyGeo.features) {
      const p = f.properties as Record<string, unknown> | null
      const gid = countyGeoidFromFeature(f as GeoJSON.Feature)
      const raw = typeof p?.[metricSlug] === 'number' && Number.isFinite(p[metricSlug]) ? p[metricSlug] : null
      let prev: number | null = null
      if (valueMode === 'yoy' && prevV && countyTrends?.byGeoid?.[gid]) {
        prev = trendCell((countyTrends.byGeoid[gid] as Record<string, unknown>)[metricSlug], prevV)
      }
      out[gid] = displayValueForMode(valueMode, raw, prev, nat)
    }
    return out
  }, [
    stateCountyGeo,
    metricSlug,
    valueMode,
    displayVintage,
    vintages.join(','),
    countyTrends,
    manifest?.national_ref,
    stateTrends,
    statePayload,
  ])

  const focusPinnedCountyNarrative = useMemo(() => {
    if (
      mode !== 'stateCounty' ||
      leaderboardPinnedId == null ||
      leaderboardPinnedId === '' ||
      !stateCountyGeo?.features?.length
    )
      return null
    for (const f of stateCountyGeo.features) {
      const gid = countyGeoidFromFeature(f as GeoJSON.Feature)
      if (gid !== leaderboardPinnedId) continue
      const p = (f as GeoJSON.Feature).properties as Record<string, unknown> | null
      const name = String(p?.NAME ?? gid).trim() || gid
      return { geoid: gid, name }
    }
    return { geoid: leaderboardPinnedId, name: leaderboardPinnedId }
  }, [mode, leaderboardPinnedId, stateCountyGeo])

  const narrativePack = useMemo((): CensusNarrativePack => {
    const label = currentMetricMeta?.label ?? metricSlug
    const region =
      mode === 'us'
        ? 'United States'
        : stateName && String(stateName).trim()
          ? String(stateName)
          : stateFips
            ? `State ${stateFips}`
            : 'This area'
    const geoLevel = mode === 'us' ? 'us_states' : mode === 'stateCounty' ? 'counties' : 'places'
    const focusFips = stateFips ? normalizeStateFips(stateFips) ?? stateFips : ''
    const stRow = focusFips ? stateTrends?.by_state?.[focusFips] : undefined
    const rawSeries = stRow?.[metricSlug]
    const stateMetricSeries =
      rawSeries != null && typeof rawSeries === 'object' && !Array.isArray(rawSeries)
        ? (rawSeries as Record<string, unknown>)
        : undefined
    const focusState =
      (mode === 'stateCounty' || mode === 'place') && stateFips
        ? { stateName: region, stateFips: focusFips, stateMetricSeries }
        : null
    return buildCensusNarrativePack({
      geoLevel,
      regionDisplayName: region,
      metricLabel: label,
      metricSlug,
      displayVintage,
      viz,
      valueMode,
      nationalRef: manifest?.national_ref,
      vintages,
      focusState,
      focusPlaceName: mode === 'place' ? placePinnedLabel : null,
      focusPinnedState: focusPinnedStateNarrative,
      focusPinnedCounty: focusPinnedCountyNarrative,
    })
  }, [
    mode,
    stateName,
    stateFips,
    currentMetricMeta?.label,
    metricSlug,
    displayVintage,
    viz,
    valueMode,
    manifest?.national_ref,
    vintages.join(','),
    stateTrends,
    placePinnedLabel,
    focusPinnedStateNarrative,
    focusPinnedCountyNarrative,
  ])

  const mapHeadingSelectionActive =
    leaderboardPinnedId != null && String(leaderboardPinnedId).trim() !== ''

  const censusStaleDataNote = useMemo(() => {
    if (valueMode !== 'raw') return null
    const raw: number[] = []
    if (mode === 'us' && statePayload?.values) {
      for (const row of Object.values(statePayload.values)) {
        const v = (row as Record<string, unknown>)[metricSlug]
        if (typeof v === 'number' && Number.isFinite(v)) raw.push(v)
      }
    } else if (mode === 'stateCounty' && stateCountyGeo?.features?.length) {
      for (const f of stateCountyGeo.features) {
        const v = (f.properties as Record<string, unknown> | null)?.[metricSlug]
        if (typeof v === 'number' && Number.isFinite(v)) raw.push(v)
      }
    } else if (mode === 'place' && placeGeoMerged?.features?.length) {
      for (const f of placeGeoMerged.features) {
        const v = (f.properties as Record<string, unknown> | null)?.[metricSlug]
        if (typeof v === 'number' && Number.isFinite(v)) raw.push(v)
      }
    }
    return censusMetricStaleDataNote(metricSlug, valueMode, raw)
  }, [mode, valueMode, metricSlug, statePayload, stateCountyGeo, placeGeoMerged])

  const countyChoroPooledForLegend = useMemo((): number[] | null => {
    if (mode !== 'stateCounty' || !countyTrends || !stateFips || !metricSlug || vintages.length < 2) return null
    const arr = collectAllVintageDisplayValuesCounty(
      countyTrends,
      stateFips,
      vintages,
      metricSlug,
      valueMode,
      manifest?.national_ref,
      stateTrends,
    )
    return arr.length >= 20 ? arr : null
  }, [mode, countyTrends, stateFips, vintages.join(','), metricSlug, valueMode, manifest?.national_ref, stateTrends])

  const countyChoroExtent = useMemo(() => {
    if (countyChoroPooledForLegend?.length) return quantileExtent(countyChoroPooledForLegend)
    const vals = Object.values(countyDisplayByGeoid).filter(
      (x): x is number => typeof x === 'number' && Number.isFinite(x),
    )
    if (!vals.length) return { min: 0, max: 1 }
    return quantileExtent(vals)
  }, [countyChoroPooledForLegend, countyDisplayByGeoid])

  const countyBubbleExtent = useMemo(() => {
    if (!stateCountyGeo || !metricSlug) return { min: 0, max: 1 }
    const displayVals = Object.values(countyDisplayByGeoid).filter(
      (x): x is number => typeof x === 'number' && Number.isFinite(x),
    )
    if (displayVals.length >= 2) {
      return minMaxExtent(displayVals)
    }
    const vals = stateCountyGeo.features
      .map((f) => {
        const v = (f.properties as Record<string, unknown> | null)?.[metricSlug]
        return typeof v === 'number' && Number.isFinite(v) ? v : null
      })
      .filter((x): x is number => x != null)
    if (!vals.length) return { min: 0, max: 1 }
    return minMaxExtent(vals)
  }, [stateCountyGeo, metricSlug, countyDisplayByGeoid])

  const countyRankByGeoid = useMemo(() => {
    const m = new Map<string, { rank: number; total: number }>()
    if (!stateCountyGeo) return m
    const rows: { id: string; value: number }[] = []
    for (const f of stateCountyGeo.features) {
      const gid = countyGeoidFromFeature(f as GeoJSON.Feature)
      const v = countyDisplayByGeoid[gid]
      if (typeof v === 'number' && Number.isFinite(v)) rows.push({ id: gid, value: v })
    }
    rows.sort((a, b) => compareRankedMetricValues(a.value, b.value, metricSlug))
    const total = rows.length
    rows.forEach((r, i) => m.set(r.id, { rank: i + 1, total }))
    return m
  }, [stateCountyGeo, countyDisplayByGeoid, metricSlug])

  /** Stable ref for react-leaflet GeoJSON `style` — inline functions change every render and trigger Leaflet
   * `setStyle` on all paths whenever e.g. `countyHover` updates, which clears hover / breaks tooltips. */
  const countyFilledGeoJsonStyle = useCallback(
    (feature: GeoJSON.Feature) => {
      const gid = countyGeoidFromFeature(feature)
      const disp = countyDisplayByGeoid[gid]
      const t = metricToDisplayT(disp, countyChoroExtent.min, countyChoroExtent.max, scale)
      const isHL = leaderboardPinnedId != null && gid === leaderboardPinnedId
      return {
        fillColor: colorFromT(t),
        color: isHL ? '#b45309' : '#334155',
        weight: isHL ? 3 : 0.5,
        fillOpacity: 0.88,
      }
    },
    [scale, countyChoroExtent.min, countyChoroExtent.max, countyDisplayByGeoid, leaderboardPinnedId],
  )

  const placeFilledGeoJsonStyle = useCallback(
    (feature: GeoJSON.Feature) => {
      const p = feature?.properties as Record<string, unknown> | undefined
      const raw = String(p?.GEOID ?? '').replace(/\D/g, '')
      const gid7 = raw.length <= 7 ? raw.padStart(7, '0') : raw.slice(-7).padStart(7, '0')
      const disp = placeDisplayByGeoid[gid7]
      const t = metricToDisplayT(disp, placeChoroExtent.min, placeChoroExtent.max, scale)
      const isHL = leaderboardPinnedId != null && gid7 === leaderboardPinnedId
      return {
        fillColor: colorFromT(t),
        color: isHL ? '#b45309' : '#334155',
        weight: isHL ? 3 : 0.5,
        fillOpacity: 0.88,
      }
    },
    [scale, placeChoroExtent.min, placeChoroExtent.max, placeDisplayByGeoid, leaderboardPinnedId],
  )

  const fmt = useCallback(
    (v: number) => formatMetricValue(metricSlug, v, metrics, valueMode),
    [metricSlug, metrics, valueMode],
  )

  const formatAxisTick = useCallback(
    (x: number, span?: number) => formatCensusMapAxisTickForMetric(metricSlug, metrics, x, span, valueMode),
    [metricSlug, metrics, valueMode],
  )

  const stateRows = useMemo(() => {
    if (!statePayload) return []
    return Object.entries(statePayload.values).map(([st, row]) => {
      const name = typeof row.NAME === 'string' ? row.NAME : st
      const disp = stateDisplayById[st] ?? null
      return { geoid: st, name, value: disp }
    })
  }, [statePayload, metricSlug, stateDisplayById])

  const sortedStateRows = useMemo(() => {
    const arr = [...stateRows]
    const mul = tableSort.dir === 'asc' ? 1 : -1
    arr.sort((a, b) => {
      if (tableSort.key === 'geoid') return mul * a.geoid.localeCompare(b.geoid)
      if (tableSort.key === 'name') return mul * a.name.localeCompare(b.name)
      const av = a.value ?? -Infinity
      const bv = b.value ?? -Infinity
      return mul * (av - bv)
    })
    return arr
  }, [stateRows, tableSort])

  const barData = useMemo(() => {
    const withVal = stateRows.filter((r) => r.value != null)
    withVal.sort((a, b) => compareRankedMetricValues(a.value!, b.value!, metricSlug))
    return withVal.slice(0, CENSUS_TOP_BAR_ROW_LIMIT).map((r) => ({
      name: r.name,
      fullName: r.name,
      value: r.value,
      geoid: r.geoid,
    }))
  }, [stateRows, metricSlug])

  const stateRankByGeoid = useMemo(() => {
    const m = new Map<string, { rank: number; total: number }>()
    const withVal = stateRows.filter((r) => r.value != null)
    withVal.sort((a, b) => compareRankedMetricValues(a.value!, b.value!, metricSlug))
    const total = withVal.length
    withVal.forEach((r, i) => m.set(r.geoid, { rank: i + 1, total }))
    return m
  }, [stateRows, metricSlug])

  const onMetricChange = (slug: string) => {
    if (!manifest) return
    const list = sliderVintages({
      mode,
      manifest,
      metricSlug: slug,
      stateTrends,
      countyTrends,
      placeTrends,
      stateFips,
    })
    const nextV = list.includes(effectiveVintage)
      ? effectiveVintage
      : (list[list.length - 1] ?? effectiveVintage)
    const q = searchParams.toString()
    if (mode === 'place' && stateFips) {
      navigate(mapPathPlace(mapPrefix, stateFips, nextV, slug, q))
    } else if (mode === 'stateCounty' && stateFips) {
      navigate(mapPathState(mapPrefix, stateFips, nextV, slug, q))
    } else {
      navigate(mapPathUs(mapPrefix, nextV, slug, q))
    }
  }

  const onVintageChange = (v: string) => {
    setPlaying(false)
    setScrubVintage(v)
    const q = searchParams.toString()
    if (vintageNavigateTimerRef.current) window.clearTimeout(vintageNavigateTimerRef.current)
    vintageNavigateTimerRef.current = window.setTimeout(() => {
      vintageNavigateTimerRef.current = null
      startTransition(() => {
        if (mode === 'place' && stateFips) {
          navigate(mapPathPlace(mapPrefix, stateFips, v, metricSlug, q), { replace: true })
        } else if (mode === 'stateCounty' && stateFips) {
          navigate(mapPathState(mapPrefix, stateFips, v, metricSlug, q), { replace: true })
        } else {
          navigate(mapPathUs(mapPrefix, v, metricSlug, q), { replace: true })
        }
      })
    }, 90)
  }

  const stateFill = useCallback(
    (stateId: string) => {
      if (!statePayload?.values) return '#e2e8f0'
      const disp = stateDisplayById[stateId]
      const t = metricToDisplayT(disp, stateChoroExtent.min, stateChoroExtent.max, scale)
      return colorFromT(t)
    },
    [statePayload, stateDisplayById, stateChoroExtent.min, stateChoroExtent.max, scale],
  )

  const onStateClick = (stateId: string) => {
    const fid = normalizeStateFips(stateId)
    if (!fid) return
    navigate(mapPathState(mapPrefix, fid, effectiveVintage, metricSlug, searchParams.toString()))
  }

  const toggleTableSort = (key: 'name' | 'value' | 'geoid') => {
    setTableSort((prev) => {
      if (prev.key === key) return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
      const valueDir = censusMetricRankDirection(metricSlug) === 'lower' ? 'asc' : 'desc'
      return { key, dir: key === 'value' ? valueDir : 'asc' }
    })
  }

  if (manifestError) {
    return (
      <div className="max-w-3xl mx-auto p-8 text-slate-700">
        <h1 className="text-xl font-semibold text-slate-900">Census map</h1>
        <p className="mt-2">
          Static data is missing. Run{' '}
          <code className="rounded bg-slate-100 px-1">
            .venv/bin/python scripts/datasources/census/export_census_map_static.py
          </code>{' '}
          from the repo root after caching ACS parquets.
        </p>
      </div>
    )
  }

  if (!manifest) {
    return <div className="p-8 text-slate-600">Loading census map…</div>
  }

  if (mode === 'us' && !stateTrendsFetched) {
    return <div className="p-8 text-slate-600">Loading census map…</div>
  }

  if (mode === 'stateCounty' && stateFips && !countyTrendsFetched) {
    return <div className="p-8 text-slate-600">Loading census map…</div>
  }

  if (mode === 'place' && stateFips && !placeTrendsFetched) {
    return <div className="p-8 text-slate-600">Loading census map…</div>
  }

  const knownSlugs = new Set(selectableMetrics.map((m) => m.slug))
  if (metric && !knownSlugs.has(metric)) {
    const fallback = selectableMetrics[0]?.slug ?? metrics[0]?.slug ?? 'median_household_income'
    if (mode === 'place' && stateFips) {
      return <Navigate to={mapPathPlace(mapPrefix, stateFips, effectiveVintage, fallback)} replace />
    }
    if (mode === 'stateCounty' && stateFips) {
      return <Navigate to={mapPathState(mapPrefix, stateFips, effectiveVintage, fallback)} replace />
    }
    return <Navigate to={mapPathUs(mapPrefix, effectiveVintage, fallback)} replace />
  }

  if (vintage && vintages.length && !vintages.includes(vintage)) {
    const q = searchParams.toString()
    if (mode === 'place' && stateFips) {
      return <Navigate to={mapPathPlace(mapPrefix, stateFips, effectiveVintage, metricSlug, q)} replace />
    }
    if (mode === 'stateCounty' && stateFips) {
      return <Navigate to={mapPathState(mapPrefix, stateFips, effectiveVintage, metricSlug, q)} replace />
    }
    return <Navigate to={mapPathUs(mapPrefix, effectiveVintage, metricSlug, q)} replace />
  }

  const singleVintage = vintages.length <= 1

  const mapToolbarDrillNav =
    (mode === 'place' || mode === 'stateCounty') && stateFips ? (
      <div className="flex flex-wrap items-center gap-2 shrink-0">
        <Link
          to={mapPathUs(mapPrefix, effectiveVintage, metricSlug, searchParams.toString())}
          className="inline-flex items-center gap-2 rounded-md bg-[#354F52] px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-[#2d4245] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2 focus-visible:ring-offset-white"
        >
          <ArrowLeftIcon className="h-4 w-4 shrink-0" aria-hidden />
          Back to US map
        </Link>
        {mode === 'stateCounty' && placeStates.includes(stateFips) ? (
          <Link
            to={mapPathPlace(mapPrefix, stateFips, effectiveVintage, metricSlug, searchParams.toString())}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-800 shadow-sm hover:bg-slate-50"
          >
            Cities / places
          </Link>
        ) : null}
        {mode === 'place' ? (
          <Link
            to={mapPathState(mapPrefix, stateFips, effectiveVintage, metricSlug, searchParams.toString())}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-800 shadow-sm hover:bg-slate-50"
          >
            Counties
          </Link>
        ) : null}
      </div>
    ) : null

  const nestedInDataExplorer = location.pathname.includes('/data-explorer/map')

  const wrapExplorerMap = (child: JSX.Element) =>
    nestedInDataExplorer ? (
      <div className="min-w-0 rounded-lg border border-slate-200/70 bg-white/40 p-1.5 sm:p-2">{child}</div>
    ) : (
      child
    )

  return (
    <div
      className={
        nestedInDataExplorer ? 'mx-auto w-full min-w-0 space-y-2.5' : 'mx-auto w-full max-w-[1600px] p-4 md:p-6'
      }
    >
      {!nestedInDataExplorer ? (
        <header className="mb-3 max-w-[60rem] border-b border-slate-200/80 pb-3">
          <h1 className="text-xl font-semibold text-slate-900">Census explorer</h1>
          <p className="mt-1 max-w-[60rem] text-xs leading-snug text-slate-600">
            Explore American Community Survey (5-year) estimates on the map. Pick a question and year, then click a
            state to open county or city views when that data is bundled for download.
          </p>
        </header>
      ) : null}

      {!censusOnboardingDismissed ? (
        <div className={nestedInDataExplorer ? 'mb-2 rounded-lg border border-sky-200/90 bg-sky-50/90 p-2 sm:p-2.5' : 'mb-4'}>
          <div
            className="flex flex-col gap-2 rounded-lg border border-sky-200 bg-sky-50/80 px-3 py-2.5 text-sm text-slate-800 shadow-sm sm:flex-row sm:items-center sm:justify-between"
            role="status"
          >
            <p className="min-w-0 leading-snug">
            <span aria-hidden>👋 </span>
            Pick what you want to explore above, choose a year, then <strong>click any state</strong> on the map. Use the
            ranking panel on the right to jump to a state — bars are numbered #1–#10 for this metric.
          </p>
          <button
            type="button"
            onClick={dismissCensusOnboarding}
            className="shrink-0 self-start rounded-md border border-sky-300 bg-white px-3 py-1.5 text-xs font-semibold text-sky-950 shadow-sm hover:bg-sky-100/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2 sm:self-center"
          >
            Got it
          </button>
        </div>
        </div>
      ) : null}

      <CensusMapAdvancedMapOptionsFlyout
        open={advancedMapOptionsOpen}
        onClose={() => {
          setAdvancedMapOptionsOpen(false)
          setAdvancedFocusSection(null)
        }}
        focusSection={advancedFocusSection}
        onConsumedFocusSection={() => setAdvancedFocusSection(null)}
        metricFullHelp={metricFullHelp}
        viz={viz}
        setViz={setViz}
        scale={scale}
        setScale={setScale}
        valueMode={valueMode}
        setValueMode={setValueMode}
        yearControls={
          mode === 'us'
            ? {
                vintages,
                displayVintage,
                singleVintage,
                showPlay,
                playing,
                setPlaying,
                onVintageChange,
                onBeginPlay: () => setAnimIndex(0),
                yearHelp: `${CENSUS_MAP_UI_HELP.year}\n\n${metricFullHelp}`,
              }
            : undefined
        }
      />

      {mode === 'us' && wrapExplorerMap(
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-end sm:gap-3">
            <div className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm sm:max-w-md">
              <CensusMetricToolbarControl
                metricFullHelp={metricFullHelp}
                metrics={selectableMetrics}
                metricSlug={metricSlug}
                onPickMetric={onMetricChange}
                unconstrainedWidth
              />
            </div>
            <div className="min-w-0 flex-1 sm:max-w-lg">
              <MapAddressSearch
                onPick={(r: MapAddressResult) => {
                  const fips = r.stateCode ? USPS_TO_FIPS2[r.stateCode] ?? null : null
                  setPinnedAddress({
                    displayName: r.displayName,
                    shortLabel: r.shortLabel,
                    lat: r.lat,
                    lon: r.lon,
                    stateCode: r.stateCode,
                    stateFips: fips,
                    county: r.county,
                    city: r.city,
                  })
                }}
                onClear={() => setPinnedAddress(null)}
              />
            </div>
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-[auto_minmax(0,1fr)_minmax(300px,26rem)] gap-3 items-start">
          <div className="hidden xl:block xl:sticky xl:top-4">
            <CensusMapLeftRail
              activeSection={advancedMapOptionsOpen ? advancedFocusSection : null}
              yearBadge={displayVintage}
              onOpen={(section: CensusMapRailSection) => {
                setAdvancedFocusSection(section)
                setAdvancedMapOptionsOpen(true)
              }}
            />
          </div>
          <div
            className="flex min-w-0 flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
            role="region"
            aria-labelledby="census-explorer-map-title-us"
          >
            <CensusMapHeadingStrip
              titleId="census-explorer-map-title-us"
              title={narrativePack.mapTitle}
              insight={narrativePack.mapTitleInsight}
              selectionActive={mapHeadingSelectionActive}
            />
            <CensusMapExplainerDetails
              subtitle={narrativePack.mapSubtitle}
              calloutLines={narrativePack.mapCallouts}
            />
            <div className="p-2">
              {!statePayload ? (
                <div className="h-[480px] flex flex-col items-center justify-center gap-2 px-4 text-center text-slate-500 text-sm">
                  <span>Loading state map…</span>
                  <span className="text-xs text-slate-400">
                    If this hangs, run export (needs <code className="text-[11px]">state_metrics.json</code>).
                  </span>
                </div>
              ) : (
                <>
                  <div className="relative w-full">
                    <div
                      ref={usMapInnerRef}
                      className="w-full overflow-x-auto relative"
                      onMouseMove={(e) => updateUsMapTip(e.clientX, e.clientY)}
                      onMouseLeave={() => {
                        setUsMapTipPos(null)
                      }}
                    >
                      <ComposableMap
                        key={`census-us-map-${metricSlug}-${viz}-${scale}`}
                        projection="geoAlbersUsa"
                        projectionConfig={{ scale: 1000 }}
                        width={960}
                        height={520}
                      >
                        <Geographies geography={manifest.state_topo_cdn || STATES_TOPO}>
                          {({ geographies, projection }) => {
                            const usBarPinFips =
                              leaderboardPinnedId != null && leaderboardPinnedId !== ''
                                ? normalizeStateFips(leaderboardPinnedId) ?? leaderboardPinnedId
                                : null
                            return (
                            <>
                              {geographies.map((geo) => {
                                const sid = normalizeStateFips(geo.id) ?? String(geo.id)
                                const row = statePayload.values[sid]
                                const name = (row as { NAME?: string } | undefined)?.NAME
                                const isBubble = viz === 'bubble'
                                const fill = isBubble ? 'rgba(248,250,252,0.94)' : stateFill(sid)
                                const isPinned = usBarPinFips != null && sid === usBarPinFips
                                const stroke = isPinned ? '#b45309' : isBubble ? '#64748b' : '#94a3b8'
                                const sw = isPinned ? 2.35 : 0.55
                                return (
                                  <Geography
                                    key={geo.rsmKey}
                                    geography={geo}
                                    style={{
                                      default: {
                                        outline: 'none',
                                        cursor: 'default',
                                        fill,
                                        stroke,
                                        strokeWidth: sw,
                                        transition: CENSUS_CHORO_FILL_TRANSITION,
                                      },
                                      hover: {
                                        outline: 'none',
                                        cursor: 'pointer',
                                        fill: isBubble ? 'rgba(226,232,240,0.98)' : '#64748b',
                                        stroke: isPinned ? '#92400e' : stroke,
                                        strokeWidth: isPinned ? 2.5 : sw,
                                        transition:
                                          'fill 0.2s cubic-bezier(0.65, 0, 0.35, 1), stroke 0.2s cubic-bezier(0.65, 0, 0.35, 1)',
                                      },
                                      pressed: {
                                        outline: 'none',
                                        fill,
                                        stroke,
                                        strokeWidth: sw,
                                      },
                                    }}
                                    onMouseEnter={(e) => {
                                      cancelScheduledHoverClear()
                                      const disp = stateDisplayById[sid] ?? null
                                      setHoverRegion({
                                        id: sid,
                                        name: typeof name === 'string' ? name : sid,
                                        value: disp,
                                      })
                                      updateUsMapTip(e.clientX, e.clientY)
                                    }}
                                    onMouseLeave={() => scheduleHoverRegionClear()}
                                    onClick={() => onStateClick(sid)}
                                  />
                                )
                              })}
                              {viz === 'bubble' &&
                                geographies.map((geo) => {
                                  const sid = normalizeStateFips(geo.id) ?? String(geo.id)
                                  const num = stateDisplayById[sid] ?? null
                                  if (num == null) return null
                                  const geom = geo.geometry
                                  if (!geom) return null
                                  let centroidPt
                                  try {
                                    centroidPt = geoCentroid({
                                      type: 'Feature',
                                      properties: {},
                                      geometry: geom,
                                    } as GeoJSON.Feature)
                                  } catch {
                                    return null
                                  }
                                  const pair = toLonLatPair(centroidPt)
                                  if (!pair) return null
                                  const xy = safeProjectScreen(projection, pair)
                                  if (!xy) return null
                                  const r = bubbleRadiusPx(num, stateBubbleExtent.min, stateBubbleExtent.max, scale, 4, 20)
                                  const bt =
                                    metricToDisplayT(num, stateBubbleExtent.min, stateBubbleExtent.max, scale) ?? 0
                                  const isPinnedBubble = usBarPinFips != null && sid === usBarPinFips
                                  return (
                                    <g
                                      key={`bubble-${geo.rsmKey}`}
                                      transform={`translate(${xy[0]},${xy[1]})`}
                                      style={{ pointerEvents: 'none' }}
                                    >
                                      <circle
                                        r={r}
                                        fill={bubbleFillFromT(bt, 0.86)}
                                        stroke={isPinnedBubble ? '#b45309' : '#fff'}
                                        strokeWidth={isPinnedBubble ? 2.4 : 0.6}
                                      />
                                    </g>
                                  )
                                })}
                              {pinnedAddress
                                ? (() => {
                                    const xy = safeProjectScreen(projection, [pinnedAddress.lon, pinnedAddress.lat])
                                    if (!xy) return null
                                    return (
                                      <g
                                        key="address-pin"
                                        transform={`translate(${xy[0]},${xy[1]})`}
                                        style={{ pointerEvents: 'none' }}
                                      >
                                        <circle r={2} fill="#0f172a" />
                                      </g>
                                    )
                                  })()
                                : null}
                            </>
                          )
                          }}
                        </Geographies>
                      </ComposableMap>
                      {hoverRegion && usMapTipPos ? (
                        <div
                          className="absolute z-20 max-w-[280px] rounded-lg border border-slate-600 bg-slate-950 px-3 py-2.5 text-sm text-white shadow-2xl pointer-events-none"
                          style={{ left: usMapTipPos.x, top: usMapTipPos.y }}
                        >
                          <div className="font-semibold leading-snug text-white">{hoverRegion.name}</div>
                          <div className="mt-0.5 text-slate-100 tabular-nums leading-snug">
                            {formatMetricValueCompact(metricSlug, hoverRegion.value, metrics, valueMode)}
                            {(() => {
                              const stRank = stateRankByGeoid.get(hoverRegion.id)
                              if (!stRank) return null
                              return (
                                <span className="text-slate-300">
                                  {' '}
                                  · Ranked #{stRank.rank} of {stRank.total}
                                </span>
                              )
                            })()}
                          </div>
                          <div className="mt-1 text-[11px] leading-snug text-slate-400">
                            {currentMetricMeta?.label ?? metricSlug}
                          </div>
                          <div className="mt-1.5 text-xs font-medium text-slate-300">
                            Click for county-level map
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </>
              )}
              </div>
              {viz === 'filled' && (
                <div className="border-t border-slate-100 px-3 pt-3 pb-2">
                  <ChoroplethLegend
                    min={stateChoroExtent.min}
                    max={stateChoroExtent.max}
                    scale={scale}
                    format={fmt}
                    valueMode={valueMode}
                    extentPoolsAllVintages={stateChoroPooledForLegend != null}
                    metricHelp={metricFullHelp}
                    semantics={choroLegendSemantics}
                    letterGradeLegend={giniRawLetterLegend}
                  />
                </div>
              )}
              {viz === 'bubble' && (
                <div className="border-t border-slate-100 px-3 pt-3 pb-2">
                  <BubbleLegend
                    min={stateBubbleExtent.min}
                    max={stateBubbleExtent.max}
                    scale={scale}
                    format={fmt}
                    metricHelp={metricFullHelp}
                    letterGradeLegend={giniRawLetterLegend}
                  />
                </div>
              )}
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
                <span>
                  U.S. Census Bureau ACS 5-year · state estimates (
                  <code className="text-[10px]">state_metrics.json</code>)
                </span>
                <span>
                  {stateChoroPooledForLegend != null
                    ? `Color scale range (~4th–96th pct., all years): ${fmt(stateChoroExtent.min)} — ${fmt(stateChoroExtent.max)}`
                    : `Color scale range (~4th–96th pct.): ${fmt(stateChoroExtent.min)} — ${fmt(stateChoroExtent.max)}`}
                </span>
              </div>
          </div>

          <aside className="flex flex-col gap-4 xl:sticky xl:top-4">
            {pinnedAddress ? (() => {
              const fips = pinnedAddress.stateFips
              const stRow = fips ? statePayload?.values?.[fips] : undefined
              const stName =
                (stRow as { NAME?: string } | undefined)?.NAME ??
                (pinnedAddress.stateCode ? STATE_CODE_TO_NAME[pinnedAddress.stateCode] : null) ??
                pinnedAddress.stateCode ??
                'Selected location'
              const rawVal =
                stRow && (stRow as Record<string, unknown>)[metricSlug] != null
                  ? ((stRow as Record<string, unknown>)[metricSlug] as number)
                  : null
              const metricLabel = currentMetricMeta?.label ?? metricSlug
              const rank = fips ? stateRankByGeoid.get(fips) : null
              return (
                <div className="rounded-lg border border-rose-200 bg-white p-3 shadow-sm">
                  <div className="flex items-start gap-2">
                    <span
                      className="mt-0.5 inline-block h-3 w-3 shrink-0 rounded-full border-2 border-white bg-rose-500 shadow ring-2 ring-rose-200"
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1">
                      <div className="text-[10px] font-semibold uppercase tracking-wide text-rose-700">
                        Pinned address
                      </div>
                      <div className="mt-0.5 truncate text-sm font-semibold text-slate-900" title={pinnedAddress.displayName}>
                        {pinnedAddress.shortLabel || pinnedAddress.displayName}
                      </div>
                      {pinnedAddress.county || pinnedAddress.city ? (
                        <div className="mt-0.5 text-[11px] text-slate-500">
                          {[pinnedAddress.city, pinnedAddress.county && `${pinnedAddress.county} County`, stName]
                            .filter(Boolean)
                            .join(' · ')}
                        </div>
                      ) : null}
                    </div>
                    <button
                      type="button"
                      onClick={() => setPinnedAddress(null)}
                      className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-1"
                      aria-label="Clear pin"
                    >
                      <XMarkIcon className="h-4 w-4" />
                    </button>
                  </div>
                  {rawVal != null ? (
                    <div className="mt-2.5 rounded-md border border-slate-100 bg-slate-50/80 px-2.5 py-2">
                      <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
                        {stName} · {metricLabel}
                      </div>
                      <div className="mt-0.5 text-base font-semibold text-slate-900 tabular-nums">
                        {formatMetricValue(metricSlug, rawVal, metrics, valueMode)}
                      </div>
                      {rank ? (
                        <div className="mt-0.5 text-[11px] text-slate-500">
                          Ranked #{rank.rank} of {rank.total} states
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <div className="mt-2.5 rounded-md border border-dashed border-slate-200 bg-slate-50/60 px-2.5 py-2 text-[11px] text-slate-500">
                      State value not available for this metric/year.
                    </div>
                  )}
                  {fips ? (
                    <button
                      type="button"
                      onClick={() => navigate(mapPathState(fips, displayVintage, metricSlug))}
                      className="mt-2.5 inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-[#354F52] px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#2c4346] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2"
                    >
                      Open {stName} county view →
                    </button>
                  ) : null}
                </div>
              )
            })() : null}
            {stateTrends && usTrendSubject ? (
              <div
                onMouseEnter={() => {
                  trendAsideCapturingHoverRef.current = true
                  cancelScheduledHoverClear()
                }}
                onMouseLeave={() => {
                  trendAsideCapturingHoverRef.current = false
                  scheduleHoverRegionClear()
                }}
              >
                {(() => {
                  const trendPts = trendPointsFromSeries(
                    stateTrends.vintages,
                    stateTrends.by_state[usTrendSubject.id]?.[metricSlug] as Record<string, unknown> | undefined,
                  )
                  return (
                    <AcTrendChart
                      title={buildCensusTrendChartTitle(
                        usTrendSubject.name,
                        metricSlug,
                        metrics.find((m) => m.slug === metricSlug)?.label ?? metricSlug,
                        trendPts,
                      )}
                      subtitle={narrativePack.trendChartSubtitle}
                      readingLines={narrativePack.trendChartCallouts}
                      chartTitleId="census-explorer-trend-chart-us"
                      points={trendPts}
                      format={fmt}
                      metricHelp={metricFullHelp}
                      metricTooltipLabel={currentMetricMeta?.label ?? metricSlug}
                    />
                  )
                })()}
                <p className="mt-2 text-[10px] leading-snug text-slate-500">
                  Move the pointer onto this panel before leaving the map to keep the chart, or click a state in the
                  ranking list to lock its trend until you click that bar again.
                </p>
              </div>
            ) : null}

            <motion.div
              className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm relative"
              initial={false}
              animate={{ opacity: trendChartOpenUs ? 0 : 1 }}
              transition={trendFadeTransition}
              style={{ pointerEvents: trendChartOpenUs ? 'none' : undefined }}
            >
              <div className="mb-2 flex gap-2 border-b border-slate-100 pb-2">
                <ChartBarSquareIcon className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                <div className="flex min-w-0 flex-1 items-start gap-1.5">
                  <h3 className="min-w-0 flex-1 text-sm font-semibold leading-snug text-slate-900 [overflow-wrap:anywhere]">
                    {narrativePack.leaderboardSectionTitle}
                  </h3>
                  <InfoHelpTrigger
                    topic="Leaderboard strip"
                    align="left"
                    help={`${metricFullHelp}\n\nClick a bar to highlight that state on the map (click again to clear); click the map to drill down.`}
                    buttonClassName="shrink-0 self-start rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
                  />
                </div>
              </div>
              <div className="relative w-full pr-1">
                <CensusRaceBarChart
                  className="min-h-0"
                  rows={barData.map((r) => ({
                    id: r.geoid,
                    label: r.name,
                    fullName: r.fullName,
                    value: r.value!,
                  }))}
                  formatValue={(v) => formatMetricValue(metricSlug, v, metrics, valueMode)}
                  formatBarEnd={(v) => formatMetricValueCompact(metricSlug, v, metrics, valueMode)}
                  formatAxisTick={formatAxisTick}
                  playing={playing}
                  vintageYear={displayVintage}
                  yearHelp={CENSUS_MAP_UI_HELP.year}
                  winnerCaption={censusMetricWinnerCaption(metricSlug)}
                  nationalContextNote={nationalContextNote}
                  winnerRankLabel={currentMetricMeta?.label ?? metricSlug}
                  winnerMetricHelp={metricFullHelp}
                  readingCalloutLines={narrativePack.barChartCallouts}
                  dataQualityNote={censusStaleDataNote}
                  selectedRowId={leaderboardPinnedId}
                  onRowClick={toggleLeaderboardPin}
                />
              </div>
            </motion.div>

            <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden flex flex-col max-h-[min(420px,50vh)]">
              <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b border-slate-100 bg-slate-50/90">
                <TableCellsIcon className="h-4 w-4 text-slate-600 shrink-0" />
                <LabelWithInfo
                  label="All states"
                  help={`${metricFullHelp}\n\n${CENSUS_MAP_UI_HELP.allGeographiesTable}`}
                />
                <span className="text-[10px] text-slate-500 ml-auto">{sortedStateRows.length} rows</span>
              </div>
              <div className="overflow-auto flex-1">
                <table className="min-w-full text-xs">
                  <thead className="sticky top-0 bg-white shadow-sm z-10">
                    <tr className="text-left text-slate-500 border-b border-slate-200">
                      <th className="px-2 py-2 font-medium">
                        <button type="button" className="hover:text-slate-900" onClick={() => toggleTableSort('geoid')}>
                          FIPS {tableSort.key === 'geoid' ? (tableSort.dir === 'asc' ? '↑' : '↓') : ''}
                        </button>
                      </th>
                      <th className="px-2 py-2 font-medium">
                        <button type="button" className="hover:text-slate-900" onClick={() => toggleTableSort('name')}>
                          Name {tableSort.key === 'name' ? (tableSort.dir === 'asc' ? '↑' : '↓') : ''}
                        </button>
                      </th>
                      <th className="px-2 py-2 font-medium text-right">
                        <button type="button" className="hover:text-slate-900" onClick={() => toggleTableSort('value')}>
                          Value {tableSort.key === 'value' ? (tableSort.dir === 'asc' ? '↑' : '↓') : ''}
                        </button>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {sortedStateRows.map((row) => (
                      <tr
                        key={row.geoid}
                        className="hover:bg-slate-50 cursor-pointer"
                        onClick={() => onStateClick(row.geoid)}
                      >
                        <td className="px-2 py-1.5 font-mono text-slate-600">{row.geoid}</td>
                        <td className="px-2 py-1.5 text-slate-800 leading-snug">{row.name}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums text-slate-800">
                          {formatMetricValue(metricSlug, row.value, metrics, valueMode)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </aside>
        </div>
        </div>
      )}

      {mode === 'stateCounty' && stateFips && wrapExplorerMap(
        <div className="flex min-w-0 flex-col gap-3">
          <CensusExplorerFilterBar
            leadingSlot={mapToolbarDrillNav}
            metricFullHelp={metricFullHelp}
            metricChoices={selectableMetrics}
            metricSlug={metricSlug}
            onMetricChange={onMetricChange}
            vintages={vintages}
            displayVintage={displayVintage}
            singleVintage={singleVintage}
            showPlay={showPlay}
            playing={playing}
            setPlaying={setPlaying}
            onVintageChange={onVintageChange}
            onBeginPlay={() => setAnimIndex(0)}
            yearHelp={`${CENSUS_MAP_UI_HELP.year}\n\n${metricFullHelp}`}
            onOpenAdvanced={(section) => {
              setAdvancedFocusSection(section)
              setAdvancedMapOptionsOpen(true)
            }}
          />
          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(300px,26rem)] gap-3 items-start">
          <div
            className="flex min-w-0 flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
            role="region"
            aria-labelledby="census-explorer-map-title-county"
          >
            <CensusMapHeadingStrip
              titleId="census-explorer-map-title-county"
              title={narrativePack.mapTitle}
              insight={narrativePack.mapTitleInsight}
              selectionActive={mapHeadingSelectionActive}
            />
            <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 bg-white px-3 py-1.5 text-xs text-slate-600">
                {!countyPayload && countyPayloadLoading && <span className="text-slate-500">Loading metrics…</span>}
                {countyTopoLoading && <span className="text-slate-500">Loading boundaries…</span>}
                {countyPayloadError && (
                  <span className="text-amber-800 text-sm">
                    Missing <code className="text-xs">county_metrics.json</code> for this year — run census export
                    with county ACS cached.
                  </span>
                )}
                {countyPayload && countyTopo && !stateCountyGeo && (
                  <span className="text-amber-800 text-sm">No county features for this state (check state FIPS).</span>
                )}
              </div>
            <CensusMapExplainerDetails
              subtitle={narrativePack.mapSubtitle}
              calloutLines={narrativePack.mapCallouts}
            />
            <div className="h-[min(78vh,620px)] w-full bg-white relative z-0">
                {stateCountyGeo && (
                  <MapContainer
                    center={[37.8, -86.8]}
                    zoom={7}
                    minZoom={5}
                    maxZoom={13}
                    className="h-full w-full census-choropleth-map"
                    scrollWheelZoom={false}
                    style={{ height: '100%', width: '100%', minHeight: 400 }}
                  >
                    {viz === 'filled' && (
                      <GeoJSON
                        key={`${metricSlug}-${scale}-county-filled`}
                        data={stateCountyGeo}
                        style={countyFilledGeoJsonStyle}
                        onEachFeature={(feature, layer) => {
                          const p = feature.properties as Record<string, unknown>
                          const gid = countyGeoidFromFeature(feature as GeoJSON.Feature)
                          const name = String(p?.NAME ?? gid ?? '')
                          const disp = countyDisplayByGeoid[gid] ?? null
                          const rk = countyRankByGeoid.get(gid)
                          const rankLine = rk
                            ? `<br/><span style="font-size:11px;color:#475569;">Ranked #${rk.rank} of ${rk.total}</span>`
                            : ''
                          layer.bindPopup(
                            `<div><strong>${name}</strong><br/>${metricValueTooltipLine(
                              currentMetricMeta?.label ?? metricSlug,
                              metricSlug,
                              disp,
                              metrics,
                              valueMode,
                            )}${rankLine}</div>`,
                          )
                          layer.on('mouseover', () => {
                            setCountyHover({ id: gid, name, value: disp })
                          })
                          layer.on('mouseout', () => setCountyHover(null))
                        }}
                      />
                    )}
                    {viz === 'bubble' &&
                      stateCountyGeo.features.map((f, idx) => {
                        const p = f.properties as Record<string, unknown> | null
                        const id = countyGeoidFromFeature(f as GeoJSON.Feature) || String(p?.GEOID ?? idx)
                        const num = countyDisplayByGeoid[id] ?? null
                        if (num == null || f.geometry == null) return null
                        const ll = featureLatLng(f)
                        if (!ll) return null
                        // Smaller cap than the legend (4..22) on purpose: state-fit views
                        // jam many counties into a narrow frame, and a 16px-radius disk
                        // covers a whole county at that scale. 2..9 keeps neighbors visible.
                        const r = bubbleRadiusPx(num, countyBubbleExtent.min, countyBubbleExtent.max, scale, 2, 9)
                        const bt =
                          metricToDisplayT(num, countyBubbleExtent.min, countyBubbleExtent.max, scale) ?? 0
                        const name = String(p?.NAME ?? id)
                        const isHL = leaderboardPinnedId != null && id === leaderboardPinnedId
                        return (
                          <CircleMarker
                            key={id}
                            center={[ll.lat, ll.lng]}
                            radius={r}
                            pathOptions={{
                              color: isHL ? '#b45309' : '#fff',
                              weight: isHL ? 3 : 1,
                              fillColor: bubbleFillFromT(bt, 0.82),
                              fillOpacity: 1,
                            }}
                          >
                            <LeafletTooltip
                              direction="top"
                              offset={[0, -6]}
                              opacity={1}
                              className="!bg-white !text-slate-900 !border !border-slate-300 !rounded-lg !px-2.5 !py-2 !shadow-lg"
                            >
                              <div className="text-xs text-slate-900">
                                <div className="font-semibold text-slate-950">{name}</div>
                                <div className="tabular-nums text-slate-800">
                                  {formatMetricValueCompact(metricSlug, num, metrics, valueMode)}
                                </div>
                                {(() => {
                                  const rk = countyRankByGeoid.get(id)
                                  if (!rk) return null
                                  return (
                                    <div className="mt-0.5 text-[10px] font-medium text-slate-600">
                                      Ranked #{rk.rank} of {rk.total}
                                    </div>
                                  )
                                })()}
                              </div>
                            </LeafletTooltip>
                          </CircleMarker>
                        )
                      })}
                    {viz === 'bubble' && (
                      <GeoJSON
                        data={stateCountyGeo}
                        interactive={false}
                        style={{
                          fillColor: 'transparent',
                          color: '#64748b',
                          weight: 0.4,
                          fillOpacity: 0,
                        }}
                      />
                    )}
                    <DrilldownMapBoundsController data={stateCountyGeo} />
                  </MapContainer>
                )}
              </div>
          </div>

          <aside className="flex flex-col gap-4 xl:sticky xl:top-4">
            {viz === 'filled' && (
              <ChoroplethLegend
                min={countyChoroExtent.min}
                max={countyChoroExtent.max}
                scale={scale}
                format={fmt}
                valueMode={valueMode}
                extentPoolsAllVintages={countyChoroPooledForLegend != null}
                metricHelp={metricFullHelp}
                semantics={choroLegendSemantics}
                letterGradeLegend={giniRawLetterLegend}
              />
            )}
            {viz === 'bubble' && (
              <BubbleLegend
                min={countyBubbleExtent.min}
                max={countyBubbleExtent.max}
                scale={scale}
                format={fmt}
                metricHelp={metricFullHelp}
                letterGradeLegend={giniRawLetterLegend}
              />
            )}
            {countyTrends && countyHover && stateFips
              ? (() => {
                  const trendPts = trendPointsFromSeries(
                    countyTrends.vintages,
                    countyTrends.byGeoid[countyHover.id]?.[metricSlug] as Record<string, unknown> | undefined,
                  )
                  return (
                    <AcTrendChart
                      title={buildCensusTrendChartTitle(
                        countyHover.name,
                        metricSlug,
                        metrics.find((m) => m.slug === metricSlug)?.label ?? metricSlug,
                        trendPts,
                      )}
                      subtitle={narrativePack.trendChartSubtitle}
                      readingLines={narrativePack.trendChartCallouts}
                      chartTitleId="census-explorer-trend-chart-county"
                      points={trendPts}
                      format={fmt}
                      metricHelp={metricFullHelp}
                      metricTooltipLabel={currentMetricMeta?.label ?? metricSlug}
                    />
                  )
                })()
              : null}
            {stateCountyGeo && (
              <>
                <motion.div
                  className="flex min-h-0 flex-col rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
                  initial={false}
                  animate={{ opacity: trendChartOpenCounty ? 0 : 1 }}
                  transition={trendFadeTransition}
                  style={{ pointerEvents: trendChartOpenCounty ? 'none' : undefined }}
                >
                  <div className="mb-2 flex shrink-0 gap-2 border-b border-slate-100 pb-2">
                    <ChartBarSquareIcon className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                    <div className="flex min-w-0 flex-1 items-start gap-1.5">
                      <h3 className="min-w-0 flex-1 text-sm font-semibold leading-snug text-slate-900 [overflow-wrap:anywhere]">
                        {narrativePack.leaderboardSectionTitle}
                      </h3>
                      <InfoHelpTrigger
                        topic="Leaderboard strip"
                        align="left"
                        help={`${metricFullHelp}\n\nClick a bar to highlight that county on the map (click again to clear).`}
                        buttonClassName="shrink-0 self-start rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
                      />
                    </div>
                  </div>
                  <PlaceBarChart
                    className="min-h-0 flex-1"
                    rowsScrollClassName="max-h-[min(20rem,48vh)]"
                    features={stateCountyGeo.features}
                    metricSlug={metricSlug}
                    metrics={metrics}
                    valueMode={valueMode}
                    displayByGeoid={countyDisplayByGeoid}
                    playing={playing}
                    narrativePack={narrativePack}
                    geoLevel="county"
                    pinnedRowId={leaderboardPinnedId}
                    onTogglePinnedRow={toggleLeaderboardPin}
                    leaderSilhouetteUsps={stateUsps ?? null}
                    displayVintage={displayVintage}
                  />
                </motion.div>
                <PlaceTable
                  features={stateCountyGeo.features}
                  geoLevel="county"
                  displayByGeoid={countyDisplayByGeoid}
                  metricSlug={metricSlug}
                  metrics={metrics}
                  valueMode={valueMode}
                  tableLabel="All counties"
                />
              </>
            )}
          </aside>
        </div>
        </div>
      )}

      {mode === 'place' && wrapExplorerMap(
        <div className="flex min-w-0 flex-col gap-3">
          <CensusExplorerFilterBar
            leadingSlot={mapToolbarDrillNav}
            metricFullHelp={metricFullHelp}
            metricChoices={selectableMetrics}
            metricSlug={metricSlug}
            onMetricChange={onMetricChange}
            vintages={vintages}
            displayVintage={displayVintage}
            singleVintage={singleVintage}
            showPlay={showPlay}
            playing={playing}
            setPlaying={setPlaying}
            onVintageChange={onVintageChange}
            onBeginPlay={() => setAnimIndex(0)}
            yearHelp={`${CENSUS_MAP_UI_HELP.year}\n\n${metricFullHelp}`}
            onOpenAdvanced={(section) => {
              setAdvancedFocusSection(section)
              setAdvancedMapOptionsOpen(true)
            }}
          />
          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(300px,26rem)] gap-3 items-start">
          <div
            className="flex min-w-0 flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
            role="region"
            aria-labelledby="census-explorer-map-title-place"
          >
            <CensusMapHeadingStrip
              titleId="census-explorer-map-title-place"
              title={narrativePack.mapTitle}
              insight={narrativePack.mapTitleInsight}
              selectionActive={mapHeadingSelectionActive}
            />
            <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 bg-white px-3 py-1.5 text-xs text-slate-600">
                {!placeGeo && !placeGeoError && <span className="text-slate-500">Loading…</span>}
                {placeGeoError && (
                  <span className="text-amber-800 text-sm leading-snug">
                    Missing <code className="text-xs">place_{stateFips}.geojson</code>
                    <span className="block mt-1 text-xs font-normal text-amber-900/90">
                      From repo root: cache place ACS, then export —{' '}
                      <code className="rounded bg-amber-50 px-1 text-[11px]">
                        .venv/bin/python scripts/datasources/census/download_census_acs_data.py --geography place
                        --state {stateFips} --year {effectiveVintage}
                      </code>{' '}
                      then{' '}
                      <code className="rounded bg-amber-50 px-1 text-[11px]">
                        .venv/bin/python scripts/datasources/census/export_census_map_static.py --year{' '}
                        {effectiveVintage} --place-states {stateFips}
                      </code>
                    </span>
                  </span>
                )}
              </div>
            <CensusMapExplainerDetails
              subtitle={narrativePack.mapSubtitle}
              calloutLines={narrativePack.mapCallouts}
            />
            <div className="h-[min(78vh,620px)] w-full bg-white relative z-0">
                {placeGeoMerged && (
                  <MapContainer
                    center={[37.8, -86.8]}
                    zoom={7}
                    minZoom={5}
                    maxZoom={13}
                    className="h-full w-full census-choropleth-map"
                    scrollWheelZoom={false}
                    style={{ height: '100%', width: '100%', minHeight: 400 }}
                  >
                    {viz === 'filled' && (
                      <GeoJSON
                        key={`${metricSlug}-${scale}-place-filled`}
                        data={placeGeoMerged}
                        style={placeFilledGeoJsonStyle}
                        onEachFeature={(feature, layer) => {
                          const p = feature.properties as Record<string, unknown>
                          const gid7 = placeGeoid7FromProperties(p, 0)
                          const name = String(p?.NAME ?? gid7 ?? '')
                          const disp = placeDisplayByGeoid[gid7] ?? null
                          const rk = placeRankByGeoid.get(gid7)
                          const rankLine = rk
                            ? `<br/><span style="font-size:11px;color:#475569;">Ranked #${rk.rank} of ${rk.total}</span>`
                            : ''
                          layer.bindPopup(
                            `<div><strong>${name}</strong><br/>${metricValueTooltipLine(
                              currentMetricMeta?.label ?? metricSlug,
                              metricSlug,
                              disp,
                              metrics,
                              valueMode,
                            )}${rankLine}</div>`,
                          )
                          layer.on('mouseover', () => {
                            setPlaceHover({ id: gid7, name, value: disp })
                          })
                          layer.on('mouseout', () => setPlaceHover(null))
                        }}
                      />
                    )}
                    {viz === 'bubble' &&
                      placeGeoMerged.features.map((f, idx) => {
                        const p = f.properties as Record<string, unknown> | null
                        const rawId = String(p?.GEOID ?? idx).replace(/\D/g, '')
                        const gid7 =
                          rawId.length <= 7 ? rawId.padStart(7, '0') : rawId.slice(-7).padStart(7, '0')
                        const num = placeDisplayByGeoid[gid7] ?? null
                        if (num == null || f.geometry == null) return null
                        const ll = featureLatLng(f)
                        if (!ll) return null
                        const r = bubbleRadiusPx(num, placeBubbleExtent.min, placeBubbleExtent.max, scale, 4, 22)
                        const bt =
                          metricToDisplayT(num, placeBubbleExtent.min, placeBubbleExtent.max, scale) ?? 0
                        const name = String(p?.NAME ?? gid7)
                        const isHL = leaderboardPinnedId != null && gid7 === leaderboardPinnedId
                        return (
                          <CircleMarker
                            key={gid7}
                            center={[ll.lat, ll.lng]}
                            radius={r}
                            pathOptions={{
                              color: isHL ? '#b45309' : '#fff',
                              weight: isHL ? 3 : 1,
                              fillColor: bubbleFillFromT(bt, 0.82),
                              fillOpacity: 1,
                            }}
                          >
                            <LeafletTooltip
                              direction="top"
                              offset={[0, -6]}
                              opacity={1}
                              className="!bg-white !text-slate-900 !border !border-slate-300 !rounded-lg !px-2.5 !py-2 !shadow-lg"
                            >
                              <div className="text-xs text-slate-900">
                                <div className="font-semibold text-slate-950">{name}</div>
                                <div className="tabular-nums text-slate-800">
                                  {formatMetricValueCompact(metricSlug, num, metrics, valueMode)}
                                </div>
                                {(() => {
                                  const rk = placeRankByGeoid.get(gid7)
                                  if (!rk) return null
                                  return (
                                    <div className="mt-0.5 text-[10px] font-medium text-slate-600">
                                      Ranked #{rk.rank} of {rk.total}
                                    </div>
                                  )
                                })()}
                              </div>
                            </LeafletTooltip>
                          </CircleMarker>
                        )
                      })}
                    {viz === 'bubble' && (
                      <GeoJSON
                        data={placeGeoMerged}
                        interactive={false}
                        style={{
                          fillColor: 'transparent',
                          color: '#64748b',
                          weight: 0.4,
                          fillOpacity: 0,
                        }}
                      />
                    )}
                    <DrilldownMapBoundsController data={placeGeoMerged} />
                  </MapContainer>
                )}
              </div>
          </div>

          <aside className="flex flex-col gap-4 xl:sticky xl:top-4">
            {viz === 'filled' && (
              <ChoroplethLegend
                min={placeChoroExtent.min}
                max={placeChoroExtent.max}
                scale={scale}
                format={fmt}
                valueMode={valueMode}
                extentPoolsAllVintages={placeChoroPooledForLegend != null}
                metricHelp={metricFullHelp}
                semantics={choroLegendSemantics}
                letterGradeLegend={giniRawLetterLegend}
              />
            )}
            {viz === 'bubble' && (
              <BubbleLegend
                min={placeBubbleExtent.min}
                max={placeBubbleExtent.max}
                scale={scale}
                format={fmt}
                metricHelp={metricFullHelp}
                letterGradeLegend={giniRawLetterLegend}
              />
            )}
            {placeTrends && placeTrendSubject
              ? (() => {
                  const trendPts = trendPointsFromSeries(
                    placeTrends.vintages,
                    placeTrends.byGeoid[placeTrendSubject.id]?.[metricSlug] as Record<string, unknown> | undefined,
                  )
                  const stateLabel = stateName && String(stateName).trim() ? String(stateName) : 'this state'
                  const placeTrendNarr = buildPlaceTrendNarrative(
                    placeTrendSubject.name,
                    stateLabel,
                    narrativePack.trendChartCallouts,
                  )
                  return (
                    <AcTrendChart
                      title={buildCensusTrendChartTitle(
                        placeTrendSubject.name,
                        metricSlug,
                        metrics.find((m) => m.slug === metricSlug)?.label ?? metricSlug,
                        trendPts,
                      )}
                      subtitle={placeTrendNarr.subtitle}
                      readingLines={placeTrendNarr.readingLines}
                      chartTitleId="census-explorer-trend-chart-place"
                      points={trendPts}
                      format={fmt}
                      metricHelp={metricFullHelp}
                      metricTooltipLabel={currentMetricMeta?.label ?? metricSlug}
                    />
                  )
                })()
              : null}
            {placeGeoMerged && (
              <>
                <motion.div
                  className="flex min-h-0 flex-col rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
                  initial={false}
                  animate={{ opacity: trendChartOpenPlace ? 0 : 1 }}
                  transition={trendFadeTransition}
                  style={{ pointerEvents: trendChartOpenPlace ? 'none' : undefined }}
                >
                  <div className="mb-2 flex shrink-0 gap-2 border-b border-slate-100 pb-2">
                    <ChartBarSquareIcon className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                    <div className="flex min-w-0 flex-1 items-start gap-1.5">
                      <h3 className="min-w-0 flex-1 text-sm font-semibold leading-snug text-slate-900 [overflow-wrap:anywhere]">
                        {narrativePack.leaderboardSectionTitle}
                      </h3>
                      <InfoHelpTrigger
                        topic="Leaderboard strip"
                        align="left"
                        help={`${metricFullHelp}\n\nClick a bar to highlight that place on the map (click again to clear).`}
                        buttonClassName="shrink-0 self-start rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
                      />
                    </div>
                  </div>
                  <PlaceBarChart
                    className="min-h-0 flex-1"
                    rowsScrollClassName="max-h-[min(20rem,48vh)]"
                    features={placeGeoMerged.features}
                    metricSlug={metricSlug}
                    metrics={metrics}
                    valueMode={valueMode}
                    displayByGeoid={placeDisplayByGeoid}
                    playing={playing}
                    narrativePack={narrativePack}
                    geoLevel="place"
                    pinnedRowId={leaderboardPinnedId}
                    onTogglePinnedRow={toggleLeaderboardPin}
                    leaderSilhouetteUsps={stateUsps ?? null}
                    displayVintage={displayVintage}
                  />
                </motion.div>
                <PlaceTable
                  features={placeGeoMerged.features}
                  geoLevel="place"
                  displayByGeoid={placeDisplayByGeoid}
                  metricSlug={metricSlug}
                  metrics={metrics}
                  valueMode={valueMode}
                />
              </>
            )}
          </aside>
        </div>
        </div>
      )}
    </div>
  )
}

type PlaceBarChartProps = {
  className?: string
  rowsScrollClassName?: string
  features: GeoJSON.Feature[]
  metricSlug: string
  metrics: CensusMetric[]
  valueMode: CensusValueMode
  displayByGeoid: Record<string, number | null>
  playing?: boolean
  topN?: number
  narrativePack?: CensusNarrativePack | null
  geoLevel: 'county' | 'place'
  pinnedRowId?: string | null
  onTogglePinnedRow?: (id: string) => void
  /** State silhouette at top of strip while #1 row may be a county or place. */
  leaderSilhouetteUsps?: string | null
  displayVintage: string
}

function PlaceBarChart(props: PlaceBarChartProps) {
  const {
    className = '',
    rowsScrollClassName,
    features,
    metricSlug,
    metrics,
    valueMode,
    displayByGeoid,
    playing = false,
    topN = CENSUS_TOP_BAR_ROW_LIMIT,
    narrativePack,
    geoLevel,
    pinnedRowId = null,
    onTogglePinnedRow,
    leaderSilhouetteUsps = null,
    displayVintage,
  } = props
  const rows = useMemo(() => {
    return features
      .map((f, i) => {
        const p = f.properties as Record<string, unknown> | null
        const id =
          geoLevel === 'county'
            ? countyGeoidFromFeature(f as GeoJSON.Feature) || `idx_${i}`
            : placeGeoid7FromProperties(p, i)
        const name = String(p?.NAME ?? p?.GEOID ?? i)
        const disp = displayByGeoid[id] ?? null
        return { id, name, fullName: name, value: disp }
      })
      .filter((r) => r.value != null)
      .sort((a, b) => compareRankedMetricValues(a.value!, b.value!, metricSlug))
      .slice(0, topN)
      .map((r) => ({
        id: r.id,
        label: truncateStateLabel(r.name, 20),
        fullName: r.fullName,
        value: r.value!,
      }))
  }, [features, metricSlug, topN, geoLevel, displayByGeoid])

  const formatAxisTick = useCallback(
    (x: number, span?: number) => formatCensusMapAxisTickForMetric(metricSlug, metrics, x, span, valueMode),
    [metricSlug, metrics, valueMode],
  )

  const metricMeta = useMemo(() => metrics.find((m) => m.slug === metricSlug), [metrics, metricSlug])
  const winnerRankLabel = metricMeta?.label ?? metricSlug
  const winnerMetricHelp = useMemo(() => censusMetricFullHelp(metricSlug, metricMeta), [metricSlug, metricMeta])

  const dataQualityNote = useMemo(() => {
    if (valueMode !== 'raw') return null
    const raw = features.map((f) => {
      const v = (f.properties as Record<string, unknown> | null)?.[metricSlug]
      return typeof v === 'number' && Number.isFinite(v) ? v : null
    })
    return censusMetricStaleDataNote(metricSlug, valueMode, raw)
  }, [features, metricSlug, valueMode])

  return (
    <CensusRaceBarChart
      className={className}
      rowsScrollClassName={rowsScrollClassName}
      rows={rows}
      formatValue={(v) => formatMetricValue(metricSlug, v, metrics, valueMode)}
      formatBarEnd={(v) => formatMetricValueCompact(metricSlug, v, metrics, valueMode)}
      formatAxisTick={formatAxisTick}
      playing={playing}
      leaderSilhouetteUsps={leaderSilhouetteUsps}
      vintageYear={displayVintage}
      yearHelp={CENSUS_MAP_UI_HELP.year}
      winnerCaption={censusMetricWinnerCaption(metricSlug)}
      winnerRankLabel={winnerRankLabel}
      winnerMetricHelp={winnerMetricHelp}
      readingCalloutLines={narrativePack?.barChartCallouts ?? null}
      dataQualityNote={dataQualityNote}
      selectedRowId={pinnedRowId}
      onRowClick={onTogglePinnedRow}
    />
  )
}

type PlaceTableProps = {
  features: GeoJSON.Feature[]
  geoLevel: 'county' | 'place'
  displayByGeoid: Record<string, number | null>
  metricSlug: string
  metrics: CensusMetric[]
  valueMode: CensusValueMode
  tableLabel?: string
}

function PlaceTable(props: PlaceTableProps) {
  const { features, geoLevel, displayByGeoid, metricSlug, metrics, valueMode, tableLabel = 'All places' } = props
  const [sort, setSort] = useState<{ key: 'name' | 'value' | 'geoid'; dir: 'asc' | 'desc' }>(() => ({
    key: 'value',
    dir: censusMetricRankDirection(metricSlug) === 'lower' ? 'asc' : 'desc',
  }))

  useEffect(() => {
    setSort((prev) =>
      prev.key === 'value'
        ? { key: 'value', dir: censusMetricRankDirection(metricSlug) === 'lower' ? 'asc' : 'desc' }
        : prev,
    )
  }, [metricSlug])

  const rows = useMemo(() => {
    return features.map((f, i) => {
      const p = f.properties as Record<string, unknown> | null
      const id =
        geoLevel === 'county'
          ? countyGeoidFromFeature(f as GeoJSON.Feature) || `idx_${i}`
          : placeGeoid7FromProperties(p, i)
      const name = String(p?.NAME ?? id)
      const disp = displayByGeoid[id] ?? null
      return { geoid: id, name, value: disp }
    })
  }, [features, metricSlug, displayByGeoid, geoLevel])

  const sorted = useMemo(() => {
    const arr = [...rows]
    const mul = sort.dir === 'asc' ? 1 : -1
    arr.sort((a, b) => {
      if (sort.key === 'geoid') return mul * a.geoid.localeCompare(b.geoid)
      if (sort.key === 'name') return mul * a.name.localeCompare(b.name)
      const av = a.value ?? -Infinity
      const bv = b.value ?? -Infinity
      return mul * (av - bv)
    })
    return arr
  }, [rows, sort])

  const toggle = (key: 'name' | 'value' | 'geoid') => {
    setSort((prev) => {
      if (prev.key === key) return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
      const valueDir = censusMetricRankDirection(metricSlug) === 'lower' ? 'asc' : 'desc'
      return { key, dir: key === 'value' ? valueDir : 'asc' }
    })
  }

  const tableHelp = useMemo(
    () =>
      `${censusMetricFullHelp(metricSlug, metrics.find((m) => m.slug === metricSlug))}\n\n${CENSUS_MAP_UI_HELP.allGeographiesTable}`,
    [metricSlug, metrics],
  )

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden flex flex-col max-h-[min(420px,50vh)]">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b border-slate-100 bg-slate-50/90">
        <TableCellsIcon className="h-4 w-4 text-slate-600 shrink-0" />
        <LabelWithInfo label={tableLabel} help={tableHelp} />
        <span className="text-[10px] text-slate-500 ml-auto">{sorted.length} rows</span>
      </div>
      <div className="overflow-auto flex-1">
        <table className="min-w-full text-xs">
          <thead className="sticky top-0 bg-white shadow-sm z-10">
            <tr className="text-left text-slate-500 border-b border-slate-200">
              <th className="px-2 py-2 font-medium">
                <button type="button" className="hover:text-slate-900" onClick={() => toggle('geoid')}>
                  GEOID {sort.key === 'geoid' ? (sort.dir === 'asc' ? '↑' : '↓') : ''}
                </button>
              </th>
              <th className="px-2 py-2 font-medium">
                <button type="button" className="hover:text-slate-900" onClick={() => toggle('name')}>
                  Name {sort.key === 'name' ? (sort.dir === 'asc' ? '↑' : '↓') : ''}
                </button>
              </th>
              <th className="px-2 py-2 font-medium text-right">
                <button type="button" className="hover:text-slate-900" onClick={() => toggle('value')}>
                  Value {sort.key === 'value' ? (sort.dir === 'asc' ? '↑' : '↓') : ''}
                </button>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sorted.map((row) => (
              <tr key={row.geoid} className="hover:bg-slate-50">
                <td className="px-2 py-1.5 font-mono text-slate-600">{row.geoid}</td>
                <td className="px-2 py-1.5 text-slate-800 leading-snug">{row.name}</td>
                <td className="px-2 py-1.5 text-right tabular-nums text-slate-800">
                  {formatMetricValue(metricSlug, row.value, metrics, valueMode)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default CensusMapPage
