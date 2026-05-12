// @ts-nocheck — react-simple-maps ships without TypeScript types (same as USMap.tsx)
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
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
  formatMinutesDisplay,
  metricToDisplayT,
  minMaxExtent,
  quantileExtent,
  type CensusScaleId,
} from '../utils/censusMapTransforms'
import {
  type CensusValueMode,
  displayValueForMode,
  nationalBaseline,
  prevVintageInList,
  trendCell,
} from '../utils/censusMapValueMode'
import {
  censusMetricFullHelp,
  censusMetricRankDirection,
  censusMetricWinnerCaption,
  compareRankedMetricValues,
  CENSUS_MAP_UI_HELP,
} from '../utils/censusDataDictionary'
import {
  buildCensusNarrativePack,
  buildCensusTrendChartTitle,
  type CensusNarrativePack,
} from '../utils/censusMapNarrative'
import { CensusRaceBarChart } from '../components/CensusRaceBarChart'
import { InfoHelpTrigger } from '../components/InfoHelpTrigger'

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
  const mv = manifestVintagesFromManifest(args.manifest)
  if (args.mode === 'us') {
    if (args.stateTrends?.vintages?.length) return stateTrendSliderVintages(args.stateTrends, args.metricSlug)
    return mv.length ? mv : ['2022']
  }
  if (args.mode === 'stateCounty' && args.stateFips && args.countyTrends?.vintages?.length) {
    return countyPlaceSliderVintages(args.countyTrends, args.stateFips, args.metricSlug)
  }
  if (args.mode === 'place' && args.stateFips && args.placeTrends?.vintages?.length) {
    return countyPlaceSliderVintages(args.placeTrends, args.stateFips, args.metricSlug)
  }
  return mv.length ? mv : ['2022']
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
    const nat = nationalBaseline(nationalRef, vy, metricSlug)
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
): number[] {
  const stp = stateFips.padStart(2, '0')
  const vals: number[] = []
  for (const vy of vintages) {
    const prevV = prevVintageInList(vintages, vy)
    const nat = nationalBaseline(nationalRef, vy, metricSlug)
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
): number[] {
  const stp = stateFips.padStart(2, '0')
  const vals: number[] = []
  for (const vy of vintages) {
    const prevV = prevVintageInList(vintages, vy)
    const nat = nationalBaseline(nationalRef, vy, metricSlug)
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
}: {
  metricFullHelp: string
  metrics: CensusMetric[]
  metricSlug: string
  onPickMetric: (slug: string) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 min-w-0 max-w-full">
      <LabelWithInfo label="Metric" help={metricFullHelp} />
      <select
        className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-900 shadow-sm max-w-[min(20rem,calc(100vw-10rem))]"
        value={metricSlug}
        onChange={(e) => onPickMetric(e.target.value)}
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

/** Thin heading row directly above the map (keeps `aria-labelledby` target). */
function CensusMapHeadingStrip({
  titleId,
  title,
  insight,
}: {
  titleId: string
  title: string
  /** Extra context (e.g. selected state vs national) shown under the title. */
  insight?: string | null
}) {
  return (
    <div className="border-b border-slate-100 bg-slate-50/60 px-3 py-1.5 sm:px-3">
      <h2 id={titleId} className="text-sm font-semibold text-slate-900 leading-snug tracking-tight">
        {title}
      </h2>
      {insight ? (
        <p className="mt-1 text-xs leading-snug text-slate-600" id={`${titleId}-insight`}>
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
      <div className="flex items-center justify-end gap-2 px-3 py-1.5">
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

  if (!open || typeof document === 'undefined') return null

  return createPortal(
    <div className="fixed inset-0 z-[200] flex justify-end">
      <button
        type="button"
        className="absolute inset-0 z-0 bg-slate-900/45"
        aria-label="Close advanced map options"
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
            Advanced — map display
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
          <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-3">
            <div className="mb-2">
              <LabelWithInfo
                label="View"
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
          <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-3">
            <div className="mb-2">
              <LabelWithInfo label="Scale" help={`${CENSUS_MAP_UI_HELP.scale}\n\n${metricFullHelp}`} />
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
          <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-3">
            <div className="mb-2">
              <LabelWithInfo label="Map value" help={`${CENSUS_MAP_UI_HELP.mapValue}\n\n${metricFullHelp}`} />
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
  yearHelp = CENSUS_MAP_UI_HELP.year,
}: {
  vintages: string[]
  displayVintage: string
  singleVintage: boolean
  showPlay: boolean
  playing: boolean
  setPlaying: (v: boolean) => void
  onVintageChange: (v: string) => void
  yearHelp?: string
}) {
  const vintageIndex = Math.max(0, vintages.indexOf(displayVintage))
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex items-center gap-2">
        <LabelWithInfo label="Year" help={yearHelp} />
        <input
          type="range"
          min={0}
          max={Math.max(0, vintages.length - 1)}
          step={1}
          value={vintageIndex}
          disabled={singleVintage}
          onChange={(e) => {
            setPlaying(false)
            onVintageChange(vintages[Number(e.target.value)]!)
          }}
          className="w-36 accent-[#354F52] disabled:opacity-40"
        />
        <span className="text-sm font-mono text-slate-800 tabular-nums min-w-[44px]" title="ACS 5-year end year">
          {displayVintage}
        </span>
      </div>
      {showPlay ? (
        <button
          type="button"
          onClick={() => setPlaying(!playing)}
          className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 shrink-0"
          title={playing ? 'Pause animation' : CENSUS_MAP_UI_HELP.play}
        >
          {playing ? <PauseIcon className="h-4 w-4" /> : <PlayIcon className="h-4 w-4" />}
          {playing ? 'Pause' : 'Play'}
        </button>
      ) : null}
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
}: {
  title: string
  subtitle?: string
  readingLines?: string[]
  chartTitleId?: string
  points: { year: string; value: number | null }[]
  format: (v: number) => string
  metricHelp?: string
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
      <div className="mb-2 flex min-w-0 items-start gap-1 border-b border-slate-100 pb-2">
        <div className="min-w-0 flex-1">
          <div
            id={chartTitleId}
            className="text-xs font-semibold uppercase tracking-wide text-slate-800 leading-snug"
            title={title}
          >
            {title}
          </div>
          {subtitle ? (
            <p className="mt-1 text-xs font-normal normal-case text-slate-600 leading-relaxed">{subtitle}</p>
          ) : null}
        </div>
        {metricHelp ? <InfoHelpTrigger help={metricHelp} topic="Trend chart" align="right" /> : null}
      </div>
      {readingLines?.length ? (
        <div className="mb-2">
          <button
            type="button"
            className="mb-2 inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-amber-200/90 bg-amber-50/60 px-2.5 py-1.5 text-xs font-medium text-amber-950/90 shadow-sm hover:bg-amber-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2 sm:w-auto sm:justify-start"
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
              formatter={(value: number) => [format(value), '']}
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
  if (v == null || !Number.isFinite(v)) return '—'
  if (valueMode === 'yoy' || valueMode === 'vs_natl') return `${v.toFixed(1)}%`
  const m = metrics.find((x) => x.slug === slug)
  if (m?.format === 'minutes' || slug === 'travel_time_to_work_minutes') {
    return formatMinutesDisplay(v)
  }
  if (m?.format === 'currency') return `$${Math.round(v).toLocaleString()}`
  if (m?.format === 'count') return `${Math.round(v).toLocaleString()}`
  if (m?.format === 'percent') return `${v.toFixed(1)}%`
  if (m?.format === 'ratio') return v.toFixed(3)
  if (m?.format === 'years') return `${v.toFixed(1)} yrs`
  return String(v)
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
    const fitPad = L.point(20, 20)

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

      // Initial view: fit the whole area in the map (inside=false). Using inside=true behaves like
      // CSS "cover" and zooms in until the view is filled — too tight for wide states (e.g. AL) in a tall pane.
      const zFit = map.getBoundsZoom(b.pad(0.035), false, fitPad)
      if (!Number.isFinite(zFit)) return

      let safeMax = Math.min(13, Math.max(Math.ceil(zIn) + 1, Math.ceil(zFit) + 2))
      if (safeMax <= safeMin) safeMax = safeMin + 1

      let z = Math.max(safeMin, Math.min(safeMax, zFit))
      // Tall panes letterbox “contain” fits; one extra integer zoom fills the view better when allowed.
      const portraitPane = size.y > size.x * 1.08
      if (portraitPane && z < safeMax) z += 1

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
}: {
  min: number
  max: number
  scale: CensusScaleId
  format: (v: number) => string
  valueMode?: CensusValueMode
  /** When trend sidecars are used, min/max are from all vintages pooled (still ~4th–96th pct.). */
  extentPoolsAllVintages?: boolean
  metricHelp?: string
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
          <LabelWithInfo label="Color scale (filled map)" help={metricHelp} />
        ) : (
          <span>Color scale (filled map)</span>
        )}
      </div>
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
}: {
  min: number
  max: number
  scale: CensusScaleId
  format: (v: number) => string
  metricHelp?: string
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

  const mode = useMemo(() => {
    if (location.pathname.includes('/census-map/place/')) return 'place'
    if (location.pathname.includes('/census-map/state/')) return 'stateCounty'
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

  useEffect(() => {
    const ix = vintages.indexOf(effectiveVintage)
    setAnimIndex(ix >= 0 ? ix : 0)
  }, [effectiveVintage, vintages.join(',')])

  const canPlayMultiVintage =
    vintages.length > 1 &&
    (mode === 'us' || (mode === 'stateCounty' && !!stateFips) || (mode === 'place' && !!stateFips))

  const canTrendAnimate = canPlayMultiVintage

  const displayVintage =
    playing && canTrendAnimate ? vintages[animIndex % vintages.length]! : effectiveVintage

  useEffect(() => {
    if (!playing || !canTrendAnimate) return
    const t = window.setInterval(() => {
      setAnimIndex((i) => {
        const list = vintagesRef.current
        if (!list.length) return 0
        return (i + 1) % list.length
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
  })

  const placeGeoMerged = useMemo(
    () => mergePlaceGeoWithTrends(placeGeo, placeTrends ?? undefined, displayVintage, metricSlugsList),
    [placeGeo, placeTrends, displayVintage, metricSlugsList],
  )

  const metrics = manifest?.metrics ?? []
  const placeStates = manifest?.place_states ?? []

  const currentMetricMeta = useMemo(() => metrics.find((m) => m.slug === metricSlug), [metrics, metricSlug])
  const metricFullHelp = useMemo(
    () => censusMetricFullHelp(metricSlug, currentMetricMeta),
    [metricSlug, currentMetricMeta],
  )

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
  ])

  const [hoverRegion, setHoverRegion] = useState<{
    id: string
    name: string
    value: number | null
  } | null>(null)

  const usMapInnerRef = useRef<HTMLDivElement | null>(null)
  const [usMapTipPos, setUsMapTipPos] = useState<{ x: number; y: number } | null>(null)

  const updateUsMapTip = useCallback((clientX: number, clientY: number) => {
    const el = usMapInnerRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const lx = clientX - r.left + el.scrollLeft
    const ly = clientY - r.top + el.scrollTop
    const estW = 280
    const estH = 102
    let left = lx + 14
    let top = ly + 14
    if (left + estW > el.scrollWidth - 8) left = Math.max(8, lx - estW - 14)
    if (top + estH > el.scrollTop + el.clientHeight - 8) top = Math.max(8, ly - estH - 14)
    left = Math.max(8, Math.min(left, Math.max(8, el.scrollWidth - estW - 8)))
    top = Math.max(8, Math.min(top, Math.max(8, el.scrollTop + el.clientHeight - estH - 8)))
    setUsMapTipPos({ x: left, y: top })
  }, [])

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
  const trendChartOpenUs = Boolean(stateTrends && hoverRegion)
  const trendChartOpenCounty = Boolean(countyTrends && countyHover && stateFips)
  const trendChartOpenPlace = Boolean(placeTrends && placeHover)
  const trendFadeTransition = { duration: reduceMotion ? 0 : 0.28, ease: 'easeInOut' }

  const stateDisplayById = useMemo(() => {
    const out: Record<string, number | null> = {}
    if (!statePayload || !metricSlug) return out
    const prevV = prevVintageInList(vintages, displayVintage)
    const nat = nationalBaseline(manifest?.national_ref, displayVintage, metricSlug)
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
    const vals = Object.values(statePayload.values)
      .map((row) => row[metricSlug])
      .filter((x): x is number => typeof x === 'number' && Number.isFinite(x))
    if (!vals.length) return { min: 0, max: 1 }
    return minMaxExtent(vals)
  }, [statePayload, metricSlug])

  const placeDisplayByGeoid = useMemo(() => {
    const out: Record<string, number | null> = {}
    const g = placeGeoMerged
    if (!g || !metricSlug) return out
    const prevV = prevVintageInList(vintages, displayVintage)
    const nat = nationalBaseline(manifest?.national_ref, displayVintage, metricSlug)
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
  ])

  const placeChoroPooledForLegend = useMemo((): number[] | null => {
    if (mode !== 'place' || !placeTrends || !stateFips || !metricSlug || vintages.length < 2) return null
    const arr = collectAllVintageDisplayValuesPlace(
      placeTrends,
      stateFips,
      vintages,
      metricSlug,
      valueMode,
      manifest?.national_ref,
    )
    return arr.length >= 20 ? arr : null
  }, [mode, placeTrends, stateFips, vintages.join(','), metricSlug, valueMode, manifest?.national_ref])

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
    const vals = g.features
      .map((f) => {
        const v = (f.properties as Record<string, unknown> | null)?.[metricSlug]
        return typeof v === 'number' && Number.isFinite(v) ? v : null
      })
      .filter((x): x is number => x != null)
    if (!vals.length) return { min: 0, max: 1 }
    return minMaxExtent(vals)
  }, [placeGeoMerged, metricSlug])

  const stateCountyGeo = useMemo(() => {
    if (mode !== 'stateCounty' || !stateFips || !countyTopo || !countyPayload?.values) return null
    return buildStateCountyGeoJson(countyTopo, countyPayload.values, stateFips, metricSlug)
  }, [mode, stateFips, countyTopo, countyPayload, metricSlug])

  const countyDisplayByGeoid = useMemo(() => {
    const out: Record<string, number | null> = {}
    if (!stateCountyGeo || !metricSlug) return out
    const prevV = prevVintageInList(vintages, displayVintage)
    const nat = nationalBaseline(manifest?.national_ref, displayVintage, metricSlug)
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
  ])

  const countyChoroPooledForLegend = useMemo((): number[] | null => {
    if (mode !== 'stateCounty' || !countyTrends || !stateFips || !metricSlug || vintages.length < 2) return null
    const arr = collectAllVintageDisplayValuesCounty(
      countyTrends,
      stateFips,
      vintages,
      metricSlug,
      valueMode,
      manifest?.national_ref,
    )
    return arr.length >= 20 ? arr : null
  }, [mode, countyTrends, stateFips, vintages.join(','), metricSlug, valueMode, manifest?.national_ref])

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
    const vals = stateCountyGeo.features
      .map((f) => {
        const v = (f.properties as Record<string, unknown> | null)?.[metricSlug]
        return typeof v === 'number' && Number.isFinite(v) ? v : null
      })
      .filter((x): x is number => x != null)
    if (!vals.length) return { min: 0, max: 1 }
    return minMaxExtent(vals)
  }, [stateCountyGeo, metricSlug])

  const fmt = useCallback(
    (v: number) => formatMetricValue(metricSlug, v, metrics, valueMode),
    [metricSlug, metrics, valueMode],
  )

  const fmtRaw = useCallback(
    (v: number) => formatMetricValue(metricSlug, v, metrics, 'raw'),
    [metricSlug, metrics],
  )

  const formatAxisTick = useCallback(
    (x: number, span?: number) => formatCensusMapAxisTickForMetric(metricSlug, metrics, x, span),
    [metricSlug, metrics],
  )

  const stateRows = useMemo(() => {
    if (!statePayload) return []
    return Object.entries(statePayload.values).map(([st, row]) => {
      const name = typeof row.NAME === 'string' ? row.NAME : st
      const v = row[metricSlug]
      const num = typeof v === 'number' && Number.isFinite(v) ? v : null
      return { geoid: st, name, value: num }
    })
  }, [statePayload, metricSlug])

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
      navigate(`/census-map/place/${stateFips}/${nextV}/${slug}?${q}`)
    } else if (mode === 'stateCounty' && stateFips) {
      navigate(`/census-map/state/${stateFips}/${nextV}/${slug}?${q}`)
    } else {
      navigate(`/census-map/us/${nextV}/${slug}?${q}`)
    }
  }

  const onVintageChange = (v: string) => {
    const q = searchParams.toString()
    if (mode === 'place' && stateFips) {
      navigate(`/census-map/place/${stateFips}/${v}/${metricSlug}?${q}`, { replace: true })
    } else if (mode === 'stateCounty' && stateFips) {
      navigate(`/census-map/state/${stateFips}/${v}/${metricSlug}?${q}`, { replace: true })
    } else {
      navigate(`/census-map/us/${v}/${metricSlug}?${q}`, { replace: true })
    }
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
    navigate(`/census-map/state/${fid}/${effectiveVintage}/${metricSlug}?${searchParams.toString()}`)
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

  const knownSlugs = new Set(metrics.map((m) => m.slug))
  if (metric && !knownSlugs.has(metric)) {
    const fallback = metrics[0]?.slug ?? 'median_household_income'
    if (mode === 'place' && stateFips) {
      return <Navigate to={`/census-map/place/${stateFips}/${effectiveVintage}/${fallback}`} replace />
    }
    if (mode === 'stateCounty' && stateFips) {
      return <Navigate to={`/census-map/state/${stateFips}/${effectiveVintage}/${fallback}`} replace />
    }
    return <Navigate to={`/census-map/us/${effectiveVintage}/${fallback}`} replace />
  }

  if (vintage && vintages.length && !vintages.includes(vintage)) {
    const q = searchParams.toString()
    if (mode === 'place' && stateFips) {
      return <Navigate to={`/census-map/place/${stateFips}/${effectiveVintage}/${metricSlug}?${q}`} replace />
    }
    if (mode === 'stateCounty' && stateFips) {
      return <Navigate to={`/census-map/state/${stateFips}/${effectiveVintage}/${metricSlug}?${q}`} replace />
    }
    return <Navigate to={`/census-map/us/${effectiveVintage}/${metricSlug}?${q}`} replace />
  }

  const singleVintage = vintages.length <= 1

  const mapToolbarDrillNav =
    (mode === 'place' || mode === 'stateCounty') && stateFips ? (
      <div className="flex flex-wrap items-center gap-2 shrink-0">
        <Link
          to={`/census-map/us/${effectiveVintage}/${metricSlug}?${searchParams.toString()}`}
          className="inline-flex items-center gap-2 rounded-md bg-[#354F52] px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-[#2d4245] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2 focus-visible:ring-offset-white"
        >
          <ArrowLeftIcon className="h-4 w-4 shrink-0" aria-hidden />
          Back to US map
        </Link>
        {mode === 'stateCounty' && placeStates.includes(stateFips) ? (
          <Link
            to={`/census-map/place/${stateFips}/${effectiveVintage}/${metricSlug}?${searchParams.toString()}`}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-800 shadow-sm hover:bg-slate-50"
          >
            Cities / places
          </Link>
        ) : null}
        {mode === 'place' ? (
          <Link
            to={`/census-map/state/${stateFips}/${effectiveVintage}/${metricSlug}?${searchParams.toString()}`}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-800 shadow-sm hover:bg-slate-50"
          >
            Counties
          </Link>
        ) : null}
      </div>
    ) : null

  return (
    <div className="max-w-[1600px] mx-auto p-4 md:p-6">
      <header className="mb-3 max-w-[60rem] border-b border-slate-200/80 pb-3">
        <h1 className="text-xl font-semibold text-slate-900">Census explorer</h1>
        <p className="mt-1 max-w-[60rem] text-xs leading-snug text-slate-600">
          American Community Survey (5-year) estimates. Choose a metric and year, then use the map — click a state to
          open counties or cities when that data is bundled.
        </p>
      </header>

      <CensusMapAdvancedMapOptionsFlyout
        open={advancedMapOptionsOpen}
        onClose={() => setAdvancedMapOptionsOpen(false)}
        metricFullHelp={metricFullHelp}
        viz={viz}
        setViz={setViz}
        scale={scale}
        setScale={setScale}
        valueMode={valueMode}
        setValueMode={setValueMode}
      />

      {mode === 'us' && (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(300px,26rem)] gap-5 items-start">
          <div
            className="flex min-w-0 flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
            role="region"
            aria-labelledby="census-explorer-map-title-us"
          >
            <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-3 py-2">
              <CensusMetricToolbarControl
                metricFullHelp={metricFullHelp}
                metrics={metrics}
                metricSlug={metricSlug}
                onPickMetric={onMetricChange}
              />
              <div className="hidden h-6 w-px bg-slate-200 sm:block" />
              <VintageAndPlayControls
                vintages={vintages}
                displayVintage={displayVintage}
                singleVintage={singleVintage}
                showPlay={showPlay}
                playing={playing}
                setPlaying={setPlaying}
                onVintageChange={onVintageChange}
                yearHelp={`${CENSUS_MAP_UI_HELP.year}\n\n${metricFullHelp}`}
              />
              <div className="hidden h-6 w-px bg-slate-200 sm:block" />
              <button
                type="button"
                title="Map display: filled vs bubbles, color scale, and map value mode"
                onClick={() => setAdvancedMapOptionsOpen(true)}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-800 shadow-sm hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2"
              >
                <AdjustmentsHorizontalIcon className="h-4 w-4 shrink-0 text-slate-600" aria-hidden />
                Advanced
              </button>
            </div>
            <CensusMapHeadingStrip
              titleId="census-explorer-map-title-us"
              title={narrativePack.mapTitle}
              insight={narrativePack.mapTitleInsight}
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
                        setHoverRegion(null)
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
                                      const v = row?.[metricSlug]
                                      const disp =
                                        stateDisplayById[sid] ??
                                        (typeof v === 'number' && Number.isFinite(v) ? v : null)
                                      setHoverRegion({
                                        id: sid,
                                        name: typeof name === 'string' ? name : sid,
                                        value: disp,
                                      })
                                      updateUsMapTip(e.clientX, e.clientY)
                                    }}
                                    onMouseLeave={() => setHoverRegion(null)}
                                    onClick={() => onStateClick(sid)}
                                  />
                                )
                              })}
                              {viz === 'bubble' &&
                                geographies.map((geo) => {
                                  const sid = normalizeStateFips(geo.id) ?? String(geo.id)
                                  const row = statePayload.values[sid]
                                  const v = row?.[metricSlug]
                                  const num = typeof v === 'number' && Number.isFinite(v) ? v : null
                                  if (num == null) return null
                                  const geom = geo.geometry
                                  if (!geom) return null
                                  let raw
                                  try {
                                    raw = geoCentroid({
                                      type: 'Feature',
                                      properties: {},
                                      geometry: geom,
                                    } as GeoJSON.Feature)
                                  } catch {
                                    return null
                                  }
                                  const pair = toLonLatPair(raw)
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
                          <div className="mt-0.5 text-slate-100 tabular-nums">
                            {formatMetricValue(metricSlug, hoverRegion.value, metrics, valueMode)}
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
            {viz === 'filled' && (
              <ChoroplethLegend
                min={stateChoroExtent.min}
                max={stateChoroExtent.max}
                scale={scale}
                format={fmt}
                valueMode={valueMode}
                extentPoolsAllVintages={stateChoroPooledForLegend != null}
                metricHelp={metricFullHelp}
              />
            )}
            {viz === 'bubble' && (
              <BubbleLegend
                min={stateBubbleExtent.min}
                max={stateBubbleExtent.max}
                scale={scale}
                format={fmtRaw}
                metricHelp={metricFullHelp}
              />
            )}

            {stateTrends && hoverRegion
              ? (() => {
                  const trendPts = trendPointsFromSeries(
                    stateTrends.vintages,
                    stateTrends.by_state[hoverRegion.id]?.[metricSlug] as Record<string, unknown> | undefined,
                  )
                  return (
                    <AcTrendChart
                      title={buildCensusTrendChartTitle(
                        hoverRegion.name,
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
                    />
                  )
                })()
              : null}

            <motion.div
              className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm relative"
              initial={false}
              animate={{ opacity: trendChartOpenUs ? 0 : 1 }}
              transition={trendFadeTransition}
              style={{ pointerEvents: trendChartOpenUs ? 'none' : undefined }}
            >
              <div className="mb-2 flex flex-wrap items-start justify-between gap-2 border-b border-slate-100 pb-2">
                <div className="flex min-w-0 gap-2">
                  <ChartBarSquareIcon className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold leading-snug text-slate-900">
                      {narrativePack.leaderboardSectionTitle}
                    </h3>
                    <p className="mt-0.5 text-xs leading-snug text-slate-600">
                      {narrativePack.leaderboardSectionSubtitle}
                    </p>
                  </div>
                </div>
                <InfoHelpTrigger
                  topic="Leaderboard strip"
                  align="right"
                  help={`${metricFullHelp}\n\nStrip shows the top-ranked states using the same values as the map for the selected year and map value mode. Click a bar to highlight that state on the map (click again to clear); click the map to drill down.`}
                />
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
                  winnerUsps={barData[0] ? FIPS2_TO_USPS[barData[0].geoid] : null}
                  vintageYear={displayVintage}
                  yearHelp={CENSUS_MAP_UI_HELP.year}
                  winnerCaption={censusMetricWinnerCaption(metricSlug, currentMetricMeta?.label ?? metricSlug)}
                  winnerMetricHelp={metricFullHelp}
                  readingCalloutLines={narrativePack.barChartCallouts}
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
      )}

      {mode === 'stateCounty' && stateFips && (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(300px,26rem)] gap-5 items-start">
          <div
            className="flex min-w-0 flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
            role="region"
            aria-labelledby="census-explorer-map-title-county"
          >
            <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-3 py-2">
              {mapToolbarDrillNav}
              {mapToolbarDrillNav ? <div className="hidden h-6 w-px bg-slate-200 sm:block" /> : null}
              <CensusMetricToolbarControl
                metricFullHelp={metricFullHelp}
                metrics={metrics}
                metricSlug={metricSlug}
                onPickMetric={onMetricChange}
              />
              <div className="hidden h-6 w-px bg-slate-200 sm:block" />
              <VintageAndPlayControls
                vintages={vintages}
                displayVintage={displayVintage}
                singleVintage={singleVintage}
                showPlay={showPlay}
                playing={playing}
                setPlaying={setPlaying}
                onVintageChange={onVintageChange}
                yearHelp={`${CENSUS_MAP_UI_HELP.year}\n\n${metricFullHelp}`}
              />
              <div className="hidden h-6 w-px bg-slate-200 sm:block" />
              <button
                type="button"
                title="Map display: filled vs bubbles, color scale, and map value mode"
                onClick={() => setAdvancedMapOptionsOpen(true)}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-800 shadow-sm hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2"
              >
                <AdjustmentsHorizontalIcon className="h-4 w-4 shrink-0 text-slate-600" aria-hidden />
                Advanced
              </button>
            </div>
            <CensusMapHeadingStrip
              titleId="census-explorer-map-title-county"
              title={narrativePack.mapTitle}
              insight={narrativePack.mapTitleInsight}
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
            <div className="h-[min(70vh,560px)] w-full bg-white relative z-0">
                {stateCountyGeo && (
                  <MapContainer
                    center={[37.8, -86.8]}
                    zoom={7}
                    minZoom={5}
                    maxZoom={13}
                    className="h-full w-full census-choropleth-map"
                    scrollWheelZoom
                    style={{ height: '100%', width: '100%', minHeight: 400 }}
                  >
                    {viz === 'filled' && (
                      <GeoJSON
                        key={`${metricSlug}-${scale}-county-filled`}
                        data={stateCountyGeo}
                        style={(feature) => {
                          const p = feature?.properties as Record<string, unknown> | undefined
                          const gid = countyGeoidFromFeature(feature as GeoJSON.Feature)
                          const disp = countyDisplayByGeoid[gid]
                          const t = metricToDisplayT(disp, countyChoroExtent.min, countyChoroExtent.max, scale)
                          const isHL = leaderboardPinnedId != null && gid === leaderboardPinnedId
                          return {
                            fillColor: colorFromT(t),
                            color: isHL ? '#b45309' : '#334155',
                            weight: isHL ? 3 : 0.5,
                            fillOpacity: 0.88,
                          }
                        }}
                        onEachFeature={(feature, layer) => {
                          const p = feature.properties as Record<string, unknown>
                          const gid = countyGeoidFromFeature(feature as GeoJSON.Feature)
                          const name = String(p?.NAME ?? gid ?? '')
                          const v = p?.[metricSlug]
                          const num = typeof v === 'number' && Number.isFinite(v) ? v : null
                          layer.bindPopup(
                            `<div><strong>${name}</strong><br/>${formatMetricValue(metricSlug, num, metrics, valueMode)}</div>`,
                          )
                          layer.on('mouseover', () => {
                            setCountyHover({ id: gid, name, value: num })
                          })
                          layer.on('mouseout', () => setCountyHover(null))
                        }}
                      />
                    )}
                    {viz === 'bubble' &&
                      stateCountyGeo.features.map((f, idx) => {
                        const p = f.properties as Record<string, unknown> | null
                        const id = countyGeoidFromFeature(f as GeoJSON.Feature) || String(p?.GEOID ?? idx)
                        const v = p?.[metricSlug]
                        const num = typeof v === 'number' && Number.isFinite(v) ? v : null
                        if (num == null || f.geometry == null) return null
                        const ll = featureLatLng(f)
                        if (!ll) return null
                        const r = bubbleRadiusPx(num, countyBubbleExtent.min, countyBubbleExtent.max, scale, 2.5, 16)
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
                                  {formatMetricValue(metricSlug, num, metrics, valueMode)}
                                </div>
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
              />
            )}
            {viz === 'bubble' && (
              <BubbleLegend
                min={countyBubbleExtent.min}
                max={countyBubbleExtent.max}
                scale={scale}
                format={fmtRaw}
                metricHelp={metricFullHelp}
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
                    />
                  )
                })()
              : null}
            {stateCountyGeo && (
              <>
                <motion.div
                  className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
                  initial={false}
                  animate={{ opacity: trendChartOpenCounty ? 0 : 1 }}
                  transition={trendFadeTransition}
                  style={{ pointerEvents: trendChartOpenCounty ? 'none' : undefined }}
                >
                  <div className="mb-2 flex flex-wrap items-start justify-between gap-2 border-b border-slate-100 pb-2">
                    <div className="flex min-w-0 gap-2">
                      <ChartBarSquareIcon className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold leading-snug text-slate-900">
                          {narrativePack.leaderboardSectionTitle}
                        </h3>
                        <p className="mt-0.5 text-xs leading-snug text-slate-600">
                          {narrativePack.leaderboardSectionSubtitle}
                        </p>
                      </div>
                    </div>
                    <InfoHelpTrigger
                      topic="Leaderboard strip"
                      align="right"
                      help={`${metricFullHelp}\n\nStrip shows the top-ranked counties using the same values as the map for the selected year and map value mode. Click a bar to highlight that county on the map (click again to clear).`}
                    />
                  </div>
                  <div className="w-full min-h-0 max-h-[min(28rem,52vh)] overflow-y-auto overflow-x-hidden overscroll-contain [scrollbar-gutter:stable]">
                    <PlaceBarChart
                      features={stateCountyGeo.features}
                      metricSlug={metricSlug}
                      metrics={metrics}
                      valueMode={valueMode}
                      playing={playing}
                      narrativePack={narrativePack}
                      geoLevel="county"
                      pinnedRowId={leaderboardPinnedId}
                      onTogglePinnedRow={toggleLeaderboardPin}
                      leaderPlateUsps={stateUsps ?? null}
                    />
                  </div>
                </motion.div>
                <PlaceTable
                  features={stateCountyGeo.features}
                  metricSlug={metricSlug}
                  metrics={metrics}
                  valueMode={valueMode}
                  tableLabel="All counties"
                />
              </>
            )}
          </aside>
        </div>
      )}

      {mode === 'place' && (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(300px,26rem)] gap-5 items-start">
          <div
            className="flex min-w-0 flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
            role="region"
            aria-labelledby="census-explorer-map-title-place"
          >
            <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-3 py-2">
              {mapToolbarDrillNav}
              {mapToolbarDrillNav ? <div className="hidden h-6 w-px bg-slate-200 sm:block" /> : null}
              <CensusMetricToolbarControl
                metricFullHelp={metricFullHelp}
                metrics={metrics}
                metricSlug={metricSlug}
                onPickMetric={onMetricChange}
              />
              <div className="hidden h-6 w-px bg-slate-200 sm:block" />
              <VintageAndPlayControls
                vintages={vintages}
                displayVintage={displayVintage}
                singleVintage={singleVintage}
                showPlay={showPlay}
                playing={playing}
                setPlaying={setPlaying}
                onVintageChange={onVintageChange}
                yearHelp={`${CENSUS_MAP_UI_HELP.year}\n\n${metricFullHelp}`}
              />
              <div className="hidden h-6 w-px bg-slate-200 sm:block" />
              <button
                type="button"
                title="Map display: filled vs bubbles, color scale, and map value mode"
                onClick={() => setAdvancedMapOptionsOpen(true)}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-800 shadow-sm hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2"
              >
                <AdjustmentsHorizontalIcon className="h-4 w-4 shrink-0 text-slate-600" aria-hidden />
                Advanced
              </button>
            </div>
            <CensusMapHeadingStrip
              titleId="census-explorer-map-title-place"
              title={narrativePack.mapTitle}
              insight={narrativePack.mapTitleInsight}
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
            <div className="h-[min(70vh,560px)] w-full bg-white relative z-0">
                {placeGeoMerged && (
                  <MapContainer
                    center={[37.8, -86.8]}
                    zoom={7}
                    minZoom={5}
                    maxZoom={13}
                    className="h-full w-full census-choropleth-map"
                    scrollWheelZoom
                    style={{ height: '100%', width: '100%', minHeight: 400 }}
                  >
                    {viz === 'filled' && (
                      <GeoJSON
                        key={`${metricSlug}-${scale}-place-filled`}
                        data={placeGeoMerged}
                        style={(feature) => {
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
                        }}
                        onEachFeature={(feature, layer) => {
                          const p = feature.properties as Record<string, unknown>
                          const gid7 = placeGeoid7FromProperties(p, 0)
                          const name = String(p?.NAME ?? gid7 ?? '')
                          const v = p?.[metricSlug]
                          const num = typeof v === 'number' && Number.isFinite(v) ? v : null
                          layer.bindPopup(
                            `<div><strong>${name}</strong><br/>${formatMetricValue(metricSlug, num, metrics, valueMode)}</div>`,
                          )
                          layer.on('mouseover', () => {
                            setPlaceHover({ id: gid7, name, value: num })
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
                        const v = p?.[metricSlug]
                        const num = typeof v === 'number' && Number.isFinite(v) ? v : null
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
                                  {formatMetricValue(metricSlug, num, metrics, valueMode)}
                                </div>
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
              />
            )}
            {viz === 'bubble' && (
              <BubbleLegend
                min={placeBubbleExtent.min}
                max={placeBubbleExtent.max}
                scale={scale}
                format={fmtRaw}
                metricHelp={metricFullHelp}
              />
            )}
            {placeTrends && placeHover
              ? (() => {
                  const trendPts = trendPointsFromSeries(
                    placeTrends.vintages,
                    placeTrends.byGeoid[placeHover.id]?.[metricSlug] as Record<string, unknown> | undefined,
                  )
                  return (
                    <AcTrendChart
                      title={buildCensusTrendChartTitle(
                        placeHover.name,
                        metricSlug,
                        metrics.find((m) => m.slug === metricSlug)?.label ?? metricSlug,
                        trendPts,
                      )}
                      subtitle={narrativePack.trendChartSubtitle}
                      readingLines={narrativePack.trendChartCallouts}
                      chartTitleId="census-explorer-trend-chart-place"
                      points={trendPts}
                      format={fmt}
                      metricHelp={metricFullHelp}
                    />
                  )
                })()
              : null}
            {placeGeoMerged && (
              <>
                <motion.div
                  className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
                  initial={false}
                  animate={{ opacity: trendChartOpenPlace ? 0 : 1 }}
                  transition={trendFadeTransition}
                  style={{ pointerEvents: trendChartOpenPlace ? 'none' : undefined }}
                >
                  <div className="mb-2 flex flex-wrap items-start justify-between gap-2 border-b border-slate-100 pb-2">
                    <div className="flex min-w-0 gap-2">
                      <ChartBarSquareIcon className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold leading-snug text-slate-900">
                          {narrativePack.leaderboardSectionTitle}
                        </h3>
                        <p className="mt-0.5 text-xs leading-snug text-slate-600">
                          {narrativePack.leaderboardSectionSubtitle}
                        </p>
                      </div>
                    </div>
                    <InfoHelpTrigger
                      topic="Leaderboard strip"
                      align="right"
                      help={`${metricFullHelp}\n\nStrip shows the top-ranked places using the same values as the map for the selected year and map value mode. Click a bar to highlight that place on the map (click again to clear).`}
                    />
                  </div>
                  <div className="w-full min-h-0 max-h-[min(28rem,52vh)] overflow-y-auto overflow-x-hidden overscroll-contain [scrollbar-gutter:stable]">
                    <PlaceBarChart
                      features={placeGeoMerged.features}
                      metricSlug={metricSlug}
                      metrics={metrics}
                      valueMode={valueMode}
                      playing={playing}
                      narrativePack={narrativePack}
                      geoLevel="place"
                      pinnedRowId={leaderboardPinnedId}
                      onTogglePinnedRow={toggleLeaderboardPin}
                      leaderPlateUsps={stateUsps ?? null}
                    />
                  </div>
                </motion.div>
                <PlaceTable features={placeGeoMerged.features} metricSlug={metricSlug} metrics={metrics} valueMode={valueMode} />
              </>
            )}
          </aside>
        </div>
      )}
    </div>
  )
}

function PlaceBarChart({
  features,
  metricSlug,
  metrics,
  valueMode,
  playing = false,
  topN = CENSUS_TOP_BAR_ROW_LIMIT,
  narrativePack,
  geoLevel,
  pinnedRowId = null,
  onTogglePinnedRow,
  leaderPlateUsps = null,
}: {
  features: GeoJSON.Feature[]
  metricSlug: string
  metrics: CensusMetric[]
  valueMode: CensusValueMode
  playing?: boolean
  topN?: number
  narrativePack?: CensusNarrativePack | null
  geoLevel: 'county' | 'place'
  pinnedRowId?: string | null
  onTogglePinnedRow?: (id: string) => void
  /** State plate at top of strip while #1 row may be a county or place. */
  leaderPlateUsps?: string | null
}) {
  const rows = useMemo(() => {
    return features
      .map((f, i) => {
        const p = f.properties as Record<string, unknown> | null
        const v = p?.[metricSlug]
        const num = typeof v === 'number' && Number.isFinite(v) ? v : null
        const name = String(p?.NAME ?? p?.GEOID ?? i)
        const id =
          geoLevel === 'county'
            ? countyGeoidFromFeature(f as GeoJSON.Feature) || `idx_${i}`
            : placeGeoid7FromProperties(p, i)
        return { id, name, fullName: name, value: num }
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
  }, [features, metricSlug, topN, geoLevel])

  const formatAxisTick = useCallback(
    (x: number, span?: number) => formatCensusMapAxisTickForMetric(metricSlug, metrics, x, span),
    [metricSlug, metrics],
  )

  return (
    <CensusRaceBarChart
      rows={rows}
      formatValue={(v) => formatMetricValue(metricSlug, v, metrics, valueMode)}
      formatBarEnd={(v) => formatMetricValueCompact(metricSlug, v, metrics, valueMode)}
      formatAxisTick={formatAxisTick}
      playing={playing}
      leaderPlateUsps={leaderPlateUsps}
      readingCalloutLines={narrativePack?.barChartCallouts ?? null}
      selectedRowId={pinnedRowId}
      onRowClick={onTogglePinnedRow}
    />
  )
}

function PlaceTable({
  features,
  metricSlug,
  metrics,
  valueMode,
  tableLabel = 'All places',
}: {
  features: GeoJSON.Feature[]
  metricSlug: string
  metrics: CensusMetric[]
  valueMode: CensusValueMode
  tableLabel?: string
}) {
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
      const geoid = String(p?.GEOID ?? i)
      const name = String(p?.NAME ?? geoid)
      const v = p?.[metricSlug]
      const num = typeof v === 'number' && Number.isFinite(v) ? v : null
      return { geoid, name, value: num }
    })
  }, [features, metricSlug])

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
