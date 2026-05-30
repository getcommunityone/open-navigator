import { useCallback, useEffect, useMemo, type ReactElement, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import Select, { type GroupBase, type SingleValue } from 'react-select'
import { InfoHelpTrigger } from '../components/InfoHelpTrigger'
import { GiniIncomeCurrentCell } from '../components/GiniInequalityReadout'
import { ScorecardGiniLegend, ScorecardTrendLegend } from '../components/ScorecardTrendAndGiniLegend'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import {
  censusMetricRankDirection,
  type CensusMetricRankDirection,
} from '../utils/censusDataDictionary'
import {
  benchComparePillMeta,
  benchValueForSlug,
  benchWindowPctForSlug,
  compareCurrentToBenchmark,
  countyGeoid5FromParam,
  hasAnyTrendWindow,
  neutralTrendArrowPack,
  paceVsBenchOneLiner,
  placeGeoid7FromParam,
  primaryValueForSlug,
  trendArrowMagnitude,
  windowPctForSlug,
  type BenchPillNames,
  type CountyPlaceTrendsSidecar,
  type ScorecardLocationOpts,
  type ScorecardSubGeography,
} from '../utils/dataExplorerScorecardHelpers'
import type { TrendArrowPack } from '../utils/dataExplorerScorecardHelpers'
import { formatMetricValueDisplay, type CensusMetricFormatRow } from '../utils/censusMapTransforms'
import { CENSUS_METRIC_GROUPS } from '../utils/censusMetricGroups'
import { prevVintageForScorecardTrend } from '../utils/censusMapValueMode'
import {
  CENSUS_REGION_LABEL,
  type CensusRegionId,
  censusRegionForStateFips,
} from '../utils/censusRegions'
import { DATA_EXPLORER_MAP_BASE, mapPathPlace, mapPathState, mapPathUs } from '../utils/dataExplorerPaths'

const SCORECARD_VALUE_FMT = { uniformTableDecimals: true } as const
const SCORECARD_PCT_DECIMALS = 2

type ManifestMetric = { slug: string; label: string; format?: string }
type Manifest = {
  vintage?: string
  vintages?: string[]
  metrics?: ManifestMetric[]
  national_ref?: Record<string, Record<string, { us?: number | null; pop_weighted_states?: number | null }>>
}

type StateTrendsPayload = {
  vintages?: string[]
  by_state: Record<string, Record<string, unknown>>
}

function intersectVintageLists(base: string[], side: string[] | undefined): string[] {
  if (!side?.length) return base
  const s = new Set(side.map((x) => String(x).trim()))
  const out = base.map((x) => String(x).trim()).filter((x) => s.has(x))
  return out.length ? out : base
}

/** Compact toggle label: multi-year options are rolling ACS 5-year windows. */
function scorecardTrendToggleLabel(years: 1 | 3 | 5): string {
  if (years === 1) return '1yr'
  return years === 3 ? 'Roll 3yr' : 'Roll 5yr'
}

/** Short phrase for help copy (e.g. "rolling 5-year"). */
function scorecardRollingWindowAdjective(years: 1 | 3 | 5): string {
  if (years === 1) return '1-year'
  return `rolling ${years}-year`
}

/** Inline “over …” line under % change in the trend column. */
function scorecardTrendOverLine(trendYears: 1 | 3 | 5): string {
  if (trendYears === 1) return 'over 1 yr (successive ACS end-years)'
  return `over rolling ${trendYears}-yr window`
}

function scorecardTrendPercentTitle(trendYears: 1 | 3 | 5, neutral: boolean): string {
  const base = neutral ? 'Percent change in the published estimate' : 'Percent change'
  if (trendYears === 1) return `${base} (1-yr successive end-years)`
  return `${base} (rolling ${trendYears}-yr window)`
}

/** Caption under the trend window control. */
function scorecardTrendCompareCaption(years: 1 | 3 | 5, displayVintage: string, vy: string | null): string {
  if (!vy) {
    return `End year ${displayVintage} — comparison vintage for this window is not in the published bundle.`
  }
  if (years === 1) {
    return `Year-over-year on ACS end-years: ${vy} → ${displayVintage}.`
  }
  return `Rolling ${years}-year window: ACS 5-year estimates from survey ending ${vy} to ending ${displayVintage} (${years} years between end-years; each value is a full 5-year pooled rolling estimate).`
}

// Topic taxonomy lives in ../utils/censusMetricGroups so the map's metric
// browser sidebar groups the same slugs the same way (single source of truth).
const SCORECARD_GROUPS = CENSUS_METRIC_GROUPS

const US_STATE_OPTIONS: { fips: string; code: string }[] = [
  { fips: '01', code: 'AL' },
  { fips: '02', code: 'AK' },
  { fips: '04', code: 'AZ' },
  { fips: '05', code: 'AR' },
  { fips: '06', code: 'CA' },
  { fips: '08', code: 'CO' },
  { fips: '09', code: 'CT' },
  { fips: '10', code: 'DE' },
  { fips: '11', code: 'DC' },
  { fips: '12', code: 'FL' },
  { fips: '13', code: 'GA' },
  { fips: '15', code: 'HI' },
  { fips: '16', code: 'ID' },
  { fips: '17', code: 'IL' },
  { fips: '18', code: 'IN' },
  { fips: '19', code: 'IA' },
  { fips: '20', code: 'KS' },
  { fips: '21', code: 'KY' },
  { fips: '22', code: 'LA' },
  { fips: '23', code: 'ME' },
  { fips: '24', code: 'MD' },
  { fips: '25', code: 'MA' },
  { fips: '26', code: 'MI' },
  { fips: '27', code: 'MN' },
  { fips: '28', code: 'MS' },
  { fips: '29', code: 'MO' },
  { fips: '30', code: 'MT' },
  { fips: '31', code: 'NE' },
  { fips: '32', code: 'NV' },
  { fips: '33', code: 'NH' },
  { fips: '34', code: 'NJ' },
  { fips: '35', code: 'NM' },
  { fips: '36', code: 'NY' },
  { fips: '37', code: 'NC' },
  { fips: '38', code: 'ND' },
  { fips: '39', code: 'OH' },
  { fips: '40', code: 'OK' },
  { fips: '41', code: 'OR' },
  { fips: '42', code: 'PA' },
  { fips: '44', code: 'RI' },
  { fips: '45', code: 'SC' },
  { fips: '46', code: 'SD' },
  { fips: '47', code: 'TN' },
  { fips: '48', code: 'TX' },
  { fips: '49', code: 'UT' },
  { fips: '50', code: 'VT' },
  { fips: '51', code: 'VA' },
  { fips: '53', code: 'WA' },
  { fips: '54', code: 'WV' },
  { fips: '55', code: 'WI' },
  { fips: '56', code: 'WY' },
]

function trendStatus(pct: number | null, dir: CensusMetricRankDirection): 'good' | 'bad' | 'flat' | 'na' {
  if (pct == null || !Number.isFinite(pct)) return 'na'
  if (Math.abs(pct) < 0.02) return 'flat'
  if (dir === 'neutral') return 'flat'
  if (dir === 'higher') return pct > 0 ? 'good' : 'bad'
  return pct < 0 ? 'good' : 'bad'
}

function favorabilityPill(s: ReturnType<typeof trendStatus>): ReactNode {
  if (s === 'na') return <span className="text-slate-400">—</span>
  if (s === 'flat')
    return <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">Flat</span>
  if (s === 'good')
    return <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800">Favorable</span>
  return <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-900">Unfavorable</span>
}

function directedTrendHeadline(
  st: ReturnType<typeof trendStatus>,
  arrows: TrendArrowPack,
  dir: CensusMetricRankDirection,
  pctWindow: number | null,
): string | null {
  if (st === 'na' || arrows.arrow === '—') return null
  if (st === 'flat') return null

  const mag =
    pctWindow != null && Number.isFinite(pctWindow)
      ? ` (~${pctWindow > 0 ? '+' : ''}${pctWindow.toFixed(SCORECARD_PCT_DECIMALS)}% change in the ACS estimate)`
      : ''

  if (st === 'good') {
    return arrows.label === 'Strong' ? `Strong improvement${mag}` : `Slight improvement${mag}`
  }
  if (st === 'bad') {
    // “Decline” only reads well when the estimate actually fell (higher-is-better). For lower-is-better, unfavorable
    // usually means the estimate rose — say “worse” so it matches the signed % line.
    if (dir === 'lower') {
      return arrows.label === 'Strong' ? `Clearly worse for this metric${mag}` : `Slightly worse for this metric${mag}`
    }
    return arrows.label === 'Strong' ? `Notable decline${mag}` : `Slight decline${mag}`
  }
  return null
}

function neutralChangeBadge(arrows: TrendArrowPack, trendYears: 1 | 3 | 5): ReactNode {
  if (!arrows.label || arrows.arrow === '—') return <span className="text-slate-400">—</span>
  const win =
    trendYears === 1 ? '1-yr step' : trendYears === 3 ? 'rolling 3-yr window' : 'rolling 5-yr window'
  if (arrows.label === 'Flat') {
    return (
      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">
        Flat ({win})
      </span>
    )
  }
  const up = arrows.arrow.includes('↑')
  return (
    <span
      className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${
        up ? 'border-indigo-200 bg-indigo-50 text-indigo-950' : 'border-amber-200 bg-amber-50 text-amber-950'
      }`}
      title="Directional change for the selected window. This metric has no built-in “higher is better” rule — interpret with context."
    >
      {up ? `Up (${win})` : `Down (${win})`}
      <span className="font-normal text-slate-600"> · {arrows.label}</span>
    </span>
  )
}

function TrendPanoramaBar({
  ratio,
  zone,
}: {
  ratio: number
  zone: 'declining' | 'mostly' | 'improving'
}): ReactNode {
  const widthPct = Math.round(Math.min(100, Math.max(6, ratio * 100)))
  return (
    <div className="w-full min-w-0">
      <div className="grid grid-cols-3 gap-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        <span className={zone === 'declining' ? 'text-slate-800' : ''}>Declining</span>
        <span className={`text-center ${zone === 'mostly' ? 'text-emerald-800' : ''}`}>Mostly improving</span>
        <span className={`text-right ${zone === 'improving' ? 'text-emerald-800' : ''}`}>Improving</span>
      </div>
      <div className="relative mt-2 h-2.5 overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full bg-emerald-600 transition-[width] duration-500 ease-out"
          style={{ width: `${widthPct}%` }}
        />
      </div>
    </div>
  )
}

function BenchmarkComparePill({
  cmp,
  benchKind,
  pillNames,
}: {
  cmp: ReturnType<typeof compareCurrentToBenchmark>
  benchKind: 'country' | 'region' | 'state'
  pillNames: BenchPillNames | null
}): ReactNode {
  const { label, tone } = benchComparePillMeta(cmp, benchKind, pillNames)
  if (tone === 'na') return <span className="text-[11px] text-slate-400">{label}</span>
  const ring =
    tone === 'ahead'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
      : tone === 'behind'
        ? 'border-rose-200 bg-rose-50 text-rose-900'
        : 'border-slate-200 bg-slate-100 text-slate-800'
  const prefix = tone === 'ahead' ? '✓ ' : tone === 'behind' ? '↓ ' : ''
  return (
    <span
      className={`inline-flex max-w-full items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold leading-snug ${ring}`}
    >
      {prefix}
      {label}
    </span>
  )
}

function ScorecardColGroup({ showBench }: { showBench: boolean }) {
  if (showBench) {
    return (
      <colgroup>
        <col style={{ width: '34%' }} />
        <col style={{ width: '14%' }} />
        <col style={{ width: '30%' }} />
        <col style={{ width: '22%' }} />
      </colgroup>
    )
  }
  return (
    <colgroup>
      <col style={{ width: '38%' }} />
      <col style={{ width: '17%' }} />
      <col style={{ width: '45%' }} />
    </colgroup>
  )
}

function stateDisplayNameFromFips(fips: string | null | undefined): string | null {
  if (!fips) return null
  const fp = fips.replace(/\D/g, '').slice(0, 2).padStart(2, '0')
  const code = US_STATE_OPTIONS.find((s) => s.fips === fp)?.code
  if (!code) return null
  return STATE_CODE_TO_NAME[code] ?? code
}

type WithinPickOption = { value: string; label: string }

function scorecardWithinParamValue(sub: ScorecardSubGeography): string {
  if (sub.level === 'place') return `place:${sub.geoid7}`
  if (sub.level === 'county') return `county:${sub.geoid5}`
  return 'state'
}

function ScorecardWithinSelect({
  scoreSub,
  countyOptions,
  placeOptions,
  onPick,
}: {
  scoreSub: ScorecardSubGeography
  countyOptions: { gid: string; name: string }[]
  placeOptions: { gid: string; name: string }[]
  onPick: (paramValue: string) => void
}) {
  const grouped = useMemo(() => {
    const groups: { label: string; options: WithinPickOption[] }[] = [
      {
        label: 'Statewide',
        options: [{ value: 'state', label: 'Entire state (all counties)' }],
      },
    ]
    if (countyOptions.length) {
      groups.push({
        label: 'Counties',
        options: countyOptions.map(({ gid, name }) => ({ value: `county:${gid}`, label: name })),
      })
    }
    if (placeOptions.length) {
      groups.push({
        label: 'Cities, towns & CDPs',
        options: placeOptions.map(({ gid, name }) => ({ value: `place:${gid}`, label: name })),
      })
    }
    return groups
  }, [countyOptions, placeOptions])

  const flat = useMemo(() => grouped.flatMap((g) => g.options), [grouped])

  const value = useMemo(() => {
    const key = scorecardWithinParamValue(scoreSub)
    return flat.find((o) => o.value === key) ?? flat[0] ?? null
  }, [flat, scoreSub])

  return (
    <Select<WithinPickOption, false, GroupBase<WithinPickOption>>
      inputId="scorecard-within"
      instanceId="scorecard-within-select"
      aria-label="County, city, or whole state"
      options={grouped}
      value={value}
      onChange={(opt: SingleValue<WithinPickOption>) => {
        if (opt) onPick(opt.value)
      }}
      isSearchable
      isClearable={false}
      placeholder="Type to search counties and places…"
      menuPlacement="auto"
      maxMenuHeight={320}
      noOptionsMessage={({ inputValue }) =>
        inputValue.trim() ? `No match for “${inputValue.trim()}”` : 'Start typing to filter'
      }
      styles={{
        container: (base) => ({ ...base, minWidth: 0, flex: 1 }),
        control: (base, state) => ({
          ...base,
          minHeight: 40,
          borderRadius: 8,
          borderColor: state.isFocused ? '#0d9488' : '#cbd5e1',
          boxShadow: state.isFocused ? '0 0 0 2px rgba(13, 148, 136, 0.28)' : 'none',
          '&:hover': { borderColor: state.isFocused ? '#0d9488' : '#94a3b8' },
        }),
        valueContainer: (base) => ({ ...base, paddingLeft: 10, paddingRight: 6 }),
        singleValue: (base) => ({ ...base, color: '#0f172a', fontSize: 14 }),
        input: (base) => ({ ...base, color: '#0f172a', fontSize: 14 }),
        placeholder: (base) => ({ ...base, color: '#64748b', fontSize: 14 }),
        menu: (base) => ({ ...base, zIndex: 50, borderRadius: 8, overflow: 'hidden', border: '1px solid #e2e8f0' }),
        menuList: (base) => ({ ...base, maxHeight: 'min(45vh, 20rem)' }),
        groupHeading: (base) => ({
          ...base,
          fontSize: 11,
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          color: '#64748b',
          background: '#f8fafc',
          margin: 0,
          padding: '6px 10px',
        }),
        option: (base, state) => ({
          ...base,
          fontSize: 13,
          color: '#0f172a',
          backgroundColor: state.isSelected ? '#ccfbf1' : state.isFocused ? '#f1f5f9' : 'white',
          cursor: 'pointer',
        }),
        indicatorSeparator: () => ({ display: 'none' }),
        dropdownIndicator: (base, state) => ({
          ...base,
          color: state.isFocused ? '#0f766e' : '#64748b',
          padding: 6,
        }),
      }}
    />
  )
}

function sectionTrendGrade(favorable: number, counted: number): { letter: string; pill: string } {
  if (counted <= 0) return { letter: '—', pill: 'No trend data' }
  const ratio = favorable / counted
  const letter = ratio >= 0.67 ? 'A' : ratio >= 0.4 ? 'B' : 'C'
  return { letter, pill: `${favorable}/${counted} favorable trends` }
}

/** Compact “How to read trend arrows” beside Map links (avoids a full-width footer band). */
function ScorecardTrendArrowsHelpInline(): ReactElement {
  return (
    <details className="relative min-w-0 shrink-0 text-left text-[10px] leading-snug text-slate-600 sm:text-xs">
      <summary
        className="cursor-pointer select-none list-none whitespace-nowrap font-semibold text-teal-800 underline decoration-teal-600/35 underline-offset-2 hover:text-teal-950 [&::-webkit-details-marker]:hidden"
        title="How to read trend arrows in the scorecard table"
      >
        How to read arrows
      </summary>
      <div className="absolute right-0 top-full z-30 mt-1 w-[min(22rem,calc(100vw-2.5rem))] rounded-md border border-slate-200 bg-white p-2 text-left shadow-lg">
        <p className="text-[10px] leading-snug text-slate-600">
          <span className="font-semibold text-slate-800">Trend column</span> uses this area’s ACS values only (percent
          change over the window you picked)—<span className="font-semibold">not</span> vs the benchmark. ↑↓ = estimate rose
          or fell; double vs single arrow ≈ strong vs slight move (about 8%+ absolute change). For scored metrics, green
          “Favorable” / amber “Unfavorable” means that move is good or bad for{' '}
          <span className="font-semibold">that metric’s direction</span> (e.g. poverty down is good). Neutral metrics: arrows
          show magnitude; we do not label the move good or bad. Benchmark level and pace appear in the “vs.” column when
          shown. Section letter grades count favorable <span className="font-semibold">area</span> trends; changing the
          benchmark does not change them.
        </p>
      </div>
    </details>
  )
}

export default function DataExplorerScorecardPage() {
  const [sp, setSp] = useSearchParams()

  const selectedStateFips = (sp.get('state') ?? '').replace(/\D/g, '').slice(0, 2).padStart(2, '0')
  const validState = US_STATE_OPTIONS.some((s) => s.fips === selectedStateFips)
  const locationFips = validState ? selectedStateFips : null

  const benchKind = (['country', 'region', 'state'].includes(sp.get('bench') ?? '') ? sp.get('bench') : 'country') as
    | 'country'
    | 'region'
    | 'state'

  const benchStateRaw = (sp.get('benchState') ?? '').replace(/\D/g, '').slice(0, 2).padStart(2, '0')
  const benchStateFips = US_STATE_OPTIONS.some((s) => s.fips === benchStateRaw) ? benchStateRaw : null

  const benchRegionRaw = sp.get('benchRegion') as CensusRegionId | null
  const benchRegion: CensusRegionId | null =
    benchRegionRaw && ['NE', 'MW', 'S', 'W'].includes(benchRegionRaw) ? benchRegionRaw : null

  const setBenchKind = useCallback(
    (k: 'country' | 'region' | 'state') => {
      const next = new URLSearchParams(sp)
      next.set('bench', k)
      setSp(next, { replace: true })
    },
    [setSp, sp],
  )

  const setLocationFips = useCallback(
    (fips: string | '') => {
      const next = new URLSearchParams(sp)
      if (!fips) {
        next.delete('state')
      } else {
        next.set('state', fips.padStart(2, '0'))
      }
      next.delete('county')
      next.delete('place')
      setSp(next, { replace: true })
    },
    [setSp, sp],
  )

  const setBenchState = useCallback(
    (fips: string | '') => {
      const next = new URLSearchParams(sp)
      if (!fips) next.delete('benchState')
      else next.set('benchState', fips.padStart(2, '0'))
      setSp(next, { replace: true })
    },
    [setSp, sp],
  )

  const setTrendYears = useCallback(
    (y: 1 | 3 | 5) => {
      const next = new URLSearchParams(sp)
      if (y === 1) next.delete('trend')
      else next.set('trend', String(y))
      setSp(next, { replace: true })
    },
    [setSp, sp],
  )

  const trendYearsRaw = sp.get('trend')
  const trendYears: 1 | 3 | 5 = trendYearsRaw === '3' ? 3 : trendYearsRaw === '5' ? 5 : 1

  const countyParam = (sp.get('county') ?? '').trim()
  const placeParam = (sp.get('place') ?? '').trim()

  const { data: manifest, isError: manifestError } = useQuery({
    queryKey: ['data-explorer-manifest'],
    queryFn: async (): Promise<Manifest> => {
      const r = await fetch('/data/census-map/manifest.json')
      if (!r.ok) throw new Error('manifest')
      return r.json()
    },
  })

  const {
    data: stateTrends,
    isSuccess: trendsOk,
    isError: trendsError,
    error: trendsErr,
  } = useQuery({
    queryKey: ['data-explorer-state-trends'],
    queryFn: async (): Promise<StateTrendsPayload> => {
      const r = await fetch('/data/census-map/state_trends.json')
      if (!r.ok) throw new Error(`state_trends ${r.status}`)
      const j = (await r.json()) as StateTrendsPayload
      if (!j || typeof j !== 'object' || typeof j.by_state !== 'object') {
        throw new Error('state_trends: invalid JSON shape')
      }
      return j
    },
    enabled: !!manifest,
  })

  const {
    data: countyTrends,
    isFetched: countyFetched,
  } = useQuery({
    queryKey: ['data-explorer-county-trends', locationFips],
    queryFn: async (): Promise<CountyPlaceTrendsSidecar | null> => {
      if (!locationFips) return null
      const r = await fetch(`/data/census-map/county_trends_${locationFips}.json`)
      if (r.status === 404) return null
      if (!r.ok) throw new Error(`county_trends ${r.status}`)
      const j = (await r.json()) as CountyPlaceTrendsSidecar
      if (!j || typeof j !== 'object' || typeof j.byGeoid !== 'object') return null
      return j
    },
    enabled: !!manifest && !!locationFips,
    retry: false,
  })

  const {
    data: placeTrends,
    isFetched: placeFetched,
  } = useQuery({
    queryKey: ['data-explorer-place-trends', locationFips],
    queryFn: async (): Promise<CountyPlaceTrendsSidecar | null> => {
      if (!locationFips) return null
      const r = await fetch(`/data/census-map/place_trends_${locationFips}.json`)
      if (r.status === 404) return null
      if (!r.ok) throw new Error(`place_trends ${r.status}`)
      const j = (await r.json()) as CountyPlaceTrendsSidecar
      if (!j || typeof j !== 'object' || typeof j.byGeoid !== 'object') return null
      return j
    },
    enabled: !!manifest && !!locationFips,
    retry: false,
  })

  useEffect(() => {
    if (!locationFips || !countyFetched || !countyParam) return
    if (!countyTrends) {
      const next = new URLSearchParams(sp)
      next.delete('county')
      setSp(next, { replace: true })
      return
    }
    const g5 = countyGeoid5FromParam(countyParam, locationFips)
    if (g5 && !countyTrends.byGeoid[g5]) {
      const next = new URLSearchParams(sp)
      next.delete('county')
      setSp(next, { replace: true })
    }
  }, [locationFips, countyParam, countyFetched, countyTrends, sp, setSp])

  useEffect(() => {
    if (!locationFips || !placeFetched || !placeParam) return
    if (!placeTrends) {
      const next = new URLSearchParams(sp)
      next.delete('place')
      setSp(next, { replace: true })
      return
    }
    const g7 = placeGeoid7FromParam(placeParam, locationFips)
    if (g7 && !placeTrends.byGeoid[g7]) {
      const next = new URLSearchParams(sp)
      next.delete('place')
      setSp(next, { replace: true })
    }
  }, [locationFips, placeParam, placeFetched, placeTrends, sp, setSp])

  const scoreSub: ScorecardSubGeography = useMemo(() => {
    if (!locationFips) return { level: 'state' }
    const g7 = placeGeoid7FromParam(placeParam, locationFips)
    if (g7 && placeTrends?.byGeoid?.[g7]) return { level: 'place', geoid7: g7 }
    const g5 = countyGeoid5FromParam(countyParam, locationFips)
    if (g5 && countyTrends?.byGeoid?.[g5]) return { level: 'county', geoid5: g5 }
    return { level: 'state' }
  }, [locationFips, countyParam, placeParam, countyTrends, placeTrends])

  const locOpts: ScorecardLocationOpts | null = useMemo(() => {
    if (!locationFips) return null
    return {
      countyTrends,
      placeTrends,
      sub: scoreSub,
    }
  }, [locationFips, countyTrends, placeTrends, scoreSub])

  const countyOptions = useMemo(() => {
    if (!locationFips || !countyTrends?.byGeoid) return []
    const st = locationFips
    return Object.entries(countyTrends.byGeoid)
      .filter(([gid]) => gid.startsWith(st))
      .map(([gid, row]) => ({
        gid,
        name: typeof (row as Record<string, unknown>).NAME === 'string' ? String((row as Record<string, unknown>).NAME) : gid,
      }))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [locationFips, countyTrends])

  const placeOptions = useMemo(() => {
    if (!locationFips || !placeTrends?.byGeoid) return []
    const st = locationFips
    return Object.entries(placeTrends.byGeoid)
      .filter(([gid]) => gid.startsWith(st))
      .map(([gid, row]) => ({
        gid,
        name: typeof (row as Record<string, unknown>).NAME === 'string' ? String((row as Record<string, unknown>).NAME) : gid,
      }))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [locationFips, placeTrends])

  const selectedPlaceLabel = useMemo(() => {
    if (!locationFips) return 'Choose a state'
    const stateNm = stateDisplayNameFromFips(locationFips) ?? 'This state'
    if (scoreSub.level === 'county') {
      const nm = countyTrends?.byGeoid?.[scoreSub.geoid5]?.NAME
      return typeof nm === 'string' && nm.trim() ? nm.trim() : `${stateNm} (county ${scoreSub.geoid5})`
    }
    if (scoreSub.level === 'place') {
      const nm = placeTrends?.byGeoid?.[scoreSub.geoid7]?.NAME
      return typeof nm === 'string' && nm.trim() ? nm.trim() : `${stateNm} (place ${scoreSub.geoid7})`
    }
    return stateNm
  }, [locationFips, scoreSub, countyTrends, placeTrends])

  const vintages = useMemo(() => {
    const m = manifest?.vintages?.length ? manifest.vintages : []
    const t = stateTrends?.vintages?.length ? stateTrends.vintages : []
    let raw = t.length ? t : m
    raw = raw.map((x) => String(x).trim())
    if (scoreSub.level === 'county' && countyTrends?.vintages?.length) {
      raw = intersectVintageLists(raw, countyTrends.vintages)
    } else if (scoreSub.level === 'place' && placeTrends?.vintages?.length) {
      raw = intersectVintageLists(raw, placeTrends.vintages)
    }
    const uniq = Array.from(new Set(raw.map((x) => String(x).trim()).filter(Boolean)))
    uniq.sort((a, b) => Number(a) - Number(b))
    return uniq
  }, [manifest?.vintages, stateTrends?.vintages, scoreSub.level, countyTrends?.vintages, placeTrends?.vintages])

  const displayVintage = useMemo(() => {
    const mv = manifest?.vintage != null ? String(manifest.vintage).trim() : ''
    if (mv && vintages.includes(mv)) return mv
    return vintages.length ? String(vintages[vintages.length - 1]!).trim() : '2024'
  }, [manifest?.vintage, vintages])

  const manifestSlugSet = useMemo(() => new Set((manifest?.metrics ?? []).map((m) => m.slug)), [manifest?.metrics])

  const groups = useMemo(() => {
    return SCORECARD_GROUPS.map((g) => ({
      ...g,
      slugs: g.slugs.filter((s) => manifestSlugSet.has(s)),
    })).filter((g) => g.slugs.length > 0)
  }, [manifestSlugSet])

  const metricMeta = useMemo(() => {
    const m = new Map<string, ManifestMetric>()
    for (const x of manifest?.metrics ?? []) m.set(x.slug, x)
    return m
  }, [manifest?.metrics])

  const formatRows: CensusMetricFormatRow[] = useMemo(
    () => (manifest?.metrics ?? []).map((x) => ({ slug: x.slug, format: x.format ?? '' })),
    [manifest?.metrics],
  )

  const regionForBench: CensusRegionId | null = useMemo(() => {
    if (benchKind !== 'region') return null
    if (locationFips) return censusRegionForStateFips(locationFips)
    return benchRegion
  }, [benchKind, locationFips, benchRegion])

  const trendPanorama = useMemo(() => {
    if (!locationFips || !stateTrends || !manifest || groups.length === 0) {
      return {
        improving: 0,
        total: 0,
        ratio: 0,
        zone: 'mostly' as 'declining' | 'mostly' | 'improving',
      }
    }
    let improving = 0
    let total = 0
    for (const g of groups) {
      for (const slug of g.slugs) {
        const p = windowPctForSlug(
          stateTrends,
          manifest,
          locationFips,
          vintages,
          displayVintage,
          slug,
          trendYears,
          locOpts,
        )
        if (p == null || !Number.isFinite(p)) continue
        total += 1
        if (trendStatus(p, censusMetricRankDirection(slug)) === 'good') improving += 1
      }
    }
    const ratio = total > 0 ? improving / total : 0
    let zone: 'declining' | 'mostly' | 'improving'
    if (ratio >= 0.67) zone = 'improving'
    else if (ratio >= 0.34) zone = 'mostly'
    else zone = 'declining'
    return { improving, total, ratio, zone }
  }, [stateTrends, manifest, groups, locationFips, vintages, displayVintage, trendYears, locOpts])

  const sectionGradeByGroupId = useMemo(() => {
    const out = new Map<string, { letter: string; pill: string }>()
    if (!locationFips || !stateTrends || !manifest) return out
    for (const g of groups) {
      let favorable = 0
      let counted = 0
      for (const slug of g.slugs) {
        const p = windowPctForSlug(
          stateTrends,
          manifest,
          locationFips,
          vintages,
          displayVintage,
          slug,
          trendYears,
          locOpts,
        )
        if (p == null || !Number.isFinite(p)) continue
        counted += 1
        if (trendStatus(p, censusMetricRankDirection(slug)) === 'good') favorable += 1
      }
      out.set(g.id, sectionTrendGrade(favorable, counted))
    }
    return out
  }, [stateTrends, manifest, groups, locationFips, vintages, displayVintage, trendYears, locOpts])

  if (manifestError) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 text-slate-700 sm:max-w-4xl md:px-6">
        <p>
          Could not load manifest. Ensure the census map static bundle is present under{' '}
          <code className="text-xs">/data/census-map/</code>.
        </p>
      </div>
    )
  }

  if (trendsError) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 text-slate-800 sm:max-w-4xl md:px-6">
        <h2 className="text-lg font-semibold text-slate-900">Could not load scorecard data</h2>
        <p className="mt-2 text-sm text-slate-700">
          The app could not read <code className="rounded bg-slate-100 px-1 text-xs">/data/census-map/state_trends.json</code>.
          If you run the API server, ensure the census bundle exists under{' '}
          <code className="rounded bg-slate-100 px-1 text-xs">web_app/public/data/census-map/</code> and that the server exposes it (see{' '}
          <code className="rounded bg-slate-100 px-1 text-xs">/data/census-map</code> mount in the FastAPI app).
        </p>
        <p className="mt-2 text-xs text-red-700">{trendsErr instanceof Error ? trendsErr.message : String(trendsErr)}</p>
      </div>
    )
  }

  if (!manifest || !trendsOk || !stateTrends) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10 text-slate-600 sm:max-w-4xl md:px-6">Loading scorecard…</div>
    )
  }

  const defaultSlug = manifest.metrics?.[0]?.slug ?? 'median_household_income'
  const mapHref =
    !locationFips
      ? mapPathUs(DATA_EXPLORER_MAP_BASE, displayVintage, defaultSlug)
      : scoreSub.level === 'place'
        ? mapPathPlace(DATA_EXPLORER_MAP_BASE, locationFips, displayVintage, defaultSlug)
        : mapPathState(DATA_EXPLORER_MAP_BASE, locationFips, displayVintage, defaultSlug)

  const showBenchmarkColumn = locationFips != null
  const showBenchStatePicker = benchKind === 'state'

  const regionBenchLabel =
    regionForBench ? CENSUS_REGION_LABEL[regionForBench] : benchRegion ? CENSUS_REGION_LABEL[benchRegion] : null
  const benchmarkStateName = stateDisplayNameFromFips(benchStateFips)
  const pillNames: BenchPillNames = { region: regionBenchLabel, state: benchmarkStateName }

  const paceVersusLabel =
    benchKind === 'country'
      ? 'the U.S. average'
      : benchKind === 'region'
        ? regionBenchLabel
          ? `the ${regionBenchLabel} region average`
          : 'the region average'
        : benchmarkStateName ?? 'the benchmark state'

  const vsColumnShort =
    benchKind === 'country'
      ? 'U.S. avg'
      : benchKind === 'region'
        ? regionBenchLabel
          ? `${regionBenchLabel} avg`
          : 'Region avg'
        : benchmarkStateName ?? 'Benchmark state'

  const benchmarkEntitySentence =
    benchKind === 'country'
      ? 'the U.S. national average'
      : benchKind === 'region'
        ? regionBenchLabel
          ? `the ${regionBenchLabel} census region average`
          : 'a census region average'
        : benchmarkStateName
          ? `${benchmarkStateName} (statewide benchmark)`
          : "another state's values"

  function spokenBenchPosition(cmp: ReturnType<typeof compareCurrentToBenchmark>): string {
    const target =
      benchKind === 'country'
        ? 'the U.S. national average'
        : benchKind === 'region'
          ? regionBenchLabel
            ? `the ${regionBenchLabel} region average`
            : 'the selected census region average'
          : benchmarkStateName
            ? `${benchmarkStateName}'s statewide values`
            : "the benchmark state's values"
    switch (cmp) {
      case 'ahead':
        return `Ahead of ${target}`
      case 'behind':
        return `Behind ${target}`
      case 'inline':
        return `In line with ${target}`
      default:
        return 'No benchmark comparison'
    }
  }

  const vyPr1 = prevVintageForScorecardTrend(vintages, displayVintage, 1)
  const vyPr3 = prevVintageForScorecardTrend(vintages, displayVintage, 3)
  const vyPr5 = prevVintageForScorecardTrend(vintages, displayVintage, 5)
  const vyPrTrend = prevVintageForScorecardTrend(vintages, displayVintage, trendYears)
  const canTrend1 = !!prevVintageForScorecardTrend(vintages, displayVintage, 1)
  const canTrend3 = !!prevVintageForScorecardTrend(vintages, displayVintage, 3)
  const canTrend5 = !!prevVintageForScorecardTrend(vintages, displayVintage, 5)

  const helpCurrent = `Latest ACS 5-year estimate for the end year shown (${displayVintage}). Dollar amounts use the same compact formatting as the map.`
  const vyForTrendHelp = trendYears === 1 ? vyPr1 : trendYears === 3 ? vyPr3 : vyPr5
  const helpTrend =
    trendYears === 1
      ? `1yr trend: percent change between successive ACS 5-year estimates in this bundle (${vyPr1 ?? '…'} → ${displayVintage}). Each value is a full 5-year survey window, not a single calendar year. The ↑/↓ arrows follow the sign of that change; double arrows mean a large move (about 8%+ absolute change). “Favorable / unfavorable” uses each metric’s direction (e.g. higher income is usually better; longer commute time is worse).`
      : `Rolling ${trendYears}-year trend: percent change between two ACS 5-year estimates as the pooled rolling survey advances ${trendYears} years on the end-year—values ending ${vyForTrendHelp ?? '…'} and ${displayVintage}. Each endpoint is still a full 5-year pooled estimate (not a one-year tabulation). The ↑/↓ arrows follow the sign of that change; double arrows mean a large move (about 8%+ absolute change). “Favorable / unfavorable” uses each metric’s direction.`
  const paceWindowLabel = scorecardRollingWindowAdjective(trendYears)
  const helpVs = showBenchmarkColumn
    ? `“Ahead / behind” compares ${selectedPlaceLabel}'s latest ${displayVintage} value to ${benchmarkEntitySentence}. The smaller line compares ${paceWindowLabel} growth pace (percentage-point difference in % change) versus ${paceVersusLabel}.`
    : ''

  return (
    <div className="mx-auto w-full max-w-3xl min-w-0 space-y-2 px-4 pb-8 sm:max-w-4xl md:px-8">
      <div className="rounded-xl border border-slate-400/45 bg-slate-300/35 p-2 shadow-sm sm:p-2">
        <div className="rounded-lg border border-slate-300/80 bg-white p-2.5 shadow-sm sm:p-3">
          <div className="flex flex-col gap-2.5">
            <div className="min-w-0 space-y-0.5">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 leading-tight">
                {locationFips ? 'Selected area' : 'Location'}
              </p>
              <p className="text-base font-semibold leading-snug text-slate-900">{selectedPlaceLabel}</p>
              <p className="text-xs leading-snug text-slate-600">
                {locationFips
                  ? scoreSub.level === 'state'
                    ? 'ACS 5-year estimates for the whole state — same series as the Data Explorer map.'
                    : scoreSub.level === 'county'
                      ? 'ACS 5-year estimates for this county — sub-state series from the same static bundle as the map.'
                      : 'ACS 5-year estimates for this place (city, town, or CDP) — sub-state series from the same bundle as the map.'
                  : 'The scorecard is built for a single state (and optional county or place). Select a state to load values, trends, and benchmark columns.'}
              </p>
            </div>

            {locationFips ? (
              <div className="flex flex-col gap-2 lg:flex-row lg:items-stretch lg:gap-3">
                <div className="flex w-full min-w-0 flex-col gap-2 lg:max-w-[16rem] lg:flex-shrink-0">
                  <label className="sr-only" htmlFor="scorecard-state">
                    Change state
                  </label>
                  <select
                    id="scorecard-state"
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none ring-offset-0 focus:ring-2 focus:ring-teal-600/35"
                    value={locationFips}
                    onChange={(e) => setLocationFips(e.target.value)}
                  >
                    {US_STATE_OPTIONS.map(({ fips, code }) => (
                      <option key={fips} value={fips}>
                        {STATE_CODE_TO_NAME[code] ?? code}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex min-w-0 flex-1 flex-col justify-center gap-2">
                  <div
                    className="flex w-full min-w-0 flex-wrap gap-0.5 rounded-lg border border-slate-200 bg-slate-100 p-0.5 sm:flex-nowrap"
                    role="group"
                    aria-label="Comparison benchmark"
                  >
                    {(
                      [
                        ['country', 'Compare vs U.S.'] as const,
                        ['region', 'Compare vs Region'] as const,
                        ['state', 'Compare vs State avg'] as const,
                      ] as const
                    ).map(([k, label]) => (
                      <button
                        key={k}
                        type="button"
                        onClick={() => setBenchKind(k)}
                        className={[
                          'min-h-[2.75rem] min-w-0 flex-1 rounded-md border px-2 py-2 text-center text-[10px] font-semibold leading-snug transition-colors sm:min-h-0 sm:px-2.5 sm:text-xs',
                          benchKind === k
                            ? 'border-slate-900 bg-slate-900 text-white shadow-sm'
                            : 'border-transparent bg-white text-slate-800 hover:bg-slate-50',
                        ].join(' ')}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <p className="text-[10px] leading-snug text-slate-500">
                    The last table column and pace lines use this benchmark. Section letter grades are from{' '}
                    <span className="font-medium text-slate-600">favorable trends only</span>, not the benchmark toggle.
                  </p>
                  {benchKind === 'region' && regionBenchLabel ? (
                    <p className="text-[10px] font-medium text-slate-600">
                      Region benchmark: {regionBenchLabel} (your state&apos;s census region).
                    </p>
                  ) : null}
                  {showBenchStatePicker ? (
                    <div className="min-w-0">
                      <label className="text-[11px] font-medium text-slate-600" htmlFor="bench-state">
                        Benchmark state
                      </label>
                      <select
                        id="bench-state"
                        className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm shadow-sm outline-none focus:ring-2 focus:ring-teal-600/35"
                        value={benchStateFips ?? ''}
                        onChange={(e) => setBenchState(e.target.value)}
                      >
                        <option value="">Select state…</option>
                        {US_STATE_OPTIONS.map(({ fips, code }) => (
                          <option key={fips} value={fips}>
                            {STATE_CODE_TO_NAME[code] ?? code}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : null}
                </div>
              </div>
            ) : (
              <div className="flex min-w-0 flex-wrap items-center gap-2 sm:max-w-xl">
                <label className="sr-only" htmlFor="scorecard-state">
                  Select a state
                </label>
                <select
                  id="scorecard-state"
                  className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none ring-offset-0 focus:ring-2 focus:ring-teal-600/35"
                  value={locationFips ?? ''}
                  onChange={(e) => setLocationFips(e.target.value)}
                >
                  <option value="" disabled>
                    Select a state…
                  </option>
                  {US_STATE_OPTIONS.map(({ fips, code }) => (
                    <option key={fips} value={fips}>
                      {STATE_CODE_TO_NAME[code] ?? code}
                    </option>
                  ))}
                </select>
                <div className="ml-auto flex shrink-0 items-center gap-1.5">
                  <ScorecardTrendArrowsHelpInline />
                  <Link
                    to={mapHref}
                    title="Open in Data Explorer map"
                    className="inline-flex shrink-0 items-center rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-[11px] font-semibold text-teal-800 shadow-sm transition hover:border-teal-300 hover:bg-teal-50/90"
                  >
                    Map
                  </Link>
                </div>
              </div>
            )}

            <div className="flex w-full min-w-0 flex-col gap-1.5 sm:max-w-xl">
              {locationFips ? (
                <>
                  {!(countyFetched && placeFetched) ? (
                    <div className="flex min-w-0 items-start justify-between gap-2">
                      <p className="min-w-0 flex-1 text-[11px] leading-snug text-slate-500">Loading county &amp; place lists…</p>
                      <div className="flex shrink-0 items-center gap-1.5">
                        <ScorecardTrendArrowsHelpInline />
                        <Link
                          to={mapHref}
                          title="Open in Data Explorer map"
                          className="inline-flex shrink-0 items-center rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-[11px] font-semibold text-teal-800 shadow-sm transition hover:border-teal-300 hover:bg-teal-50/90"
                        >
                          Map
                        </Link>
                      </div>
                    </div>
                  ) : countyOptions.length === 0 && placeOptions.length === 0 ? (
                    <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
                      <p className="min-w-0 flex-1 text-[11px] leading-snug text-amber-900">
                        County/place trend files are not in this bundle for this state — statewide scorecard only.
                      </p>
                      <div className="flex shrink-0 items-center gap-1.5">
                        <ScorecardTrendArrowsHelpInline />
                        <Link
                          to={mapHref}
                          title="Open in Data Explorer map"
                          className="inline-flex shrink-0 items-center rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-[11px] font-semibold text-teal-800 shadow-sm transition hover:border-teal-300 hover:bg-teal-50/90"
                        >
                          Map
                        </Link>
                      </div>
                    </div>
                  ) : (
                    <div className="flex min-w-0 flex-nowrap items-center gap-1.5 sm:gap-2">
                      <label className="sr-only" htmlFor="scorecard-within">
                        County, city, or whole state
                      </label>
                      <div className="min-w-0 flex-1 overflow-hidden">
                        <ScorecardWithinSelect
                          scoreSub={scoreSub}
                          countyOptions={countyOptions}
                          placeOptions={placeOptions}
                          onPick={(v) => {
                            const next = new URLSearchParams(sp)
                            if (v === 'state') {
                              next.delete('county')
                              next.delete('place')
                            } else if (v.startsWith('county:')) {
                              next.set('county', v.slice(7))
                              next.delete('place')
                            } else if (v.startsWith('place:')) {
                              next.set('place', v.slice(6))
                              next.delete('county')
                            }
                            setSp(next, { replace: true })
                          }}
                        />
                      </div>
                      <div className="ml-auto flex shrink-0 items-center gap-1.5">
                        <ScorecardTrendArrowsHelpInline />
                        <Link
                          to={mapHref}
                          title="Open in Data Explorer map"
                          className="inline-flex shrink-0 items-center rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-[11px] font-semibold text-teal-800 shadow-sm transition hover:border-teal-300 hover:bg-teal-50/90"
                        >
                          Map
                        </Link>
                      </div>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      {locationFips ? (
        <div className="rounded-xl border border-slate-400/45 bg-slate-300/35 p-2 shadow-sm sm:p-2.5">
          <div className="rounded-lg border border-slate-300/80 bg-white p-3 shadow-sm sm:p-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between lg:gap-6">
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-slate-500">Overall picture for</p>
                <h2 className="mt-1 font-serif text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
                  {selectedPlaceLabel}
                </h2>
                <p className="mt-3 text-sm leading-snug text-slate-600">
                  {trendPanorama.total === 0 ? (
                    <span>
                      No trend values for the selected {scorecardRollingWindowAdjective(trendYears)} window in this
                      export (check older vintages or try another window).
                    </span>
                  ) : (
                    <>
                      <span className="font-semibold text-emerald-700">{trendPanorama.improving}</span>
                      <span> of </span>
                      <span className="font-semibold text-emerald-700">{trendPanorama.total}</span>
                      <span> tracked metrics </span>
                      <span>
                        {trendYears === 1
                          ? 'are improving on the 1-year (successive ACS end-year) trend.'
                          : `are improving on the rolling ${trendYears}-year trend window.`}
                      </span>
                    </>
                  )}
                </p>
              </div>
              <div className="w-full min-w-0 flex-1 lg:max-w-md">
                <TrendPanoramaBar ratio={trendPanorama.ratio} zone={trendPanorama.zone} />
              </div>
              <div className="flex w-full flex-col gap-2 lg:w-56 lg:flex-none">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Trend window</p>
                <div className="flex rounded-lg border border-slate-200 bg-slate-50/90 p-0.5">
                  {([1, 3, 5] as const).map((y) => {
                    const can = y === 1 ? canTrend1 : y === 3 ? canTrend3 : canTrend5
                    return (
                      <button
                        key={y}
                        type="button"
                        disabled={!can}
                        title={
                          y === 1
                            ? 'Successive ACS 5-year end-years in this bundle'
                            : `Rolling ${y}-year window: compare ACS 5-year estimates ${y} end-years apart`
                        }
                        onClick={() => can && setTrendYears(y)}
                        className={[
                          'flex-1 rounded-md px-2 py-2 text-center text-xs font-semibold transition-colors',
                          trendYears === y
                            ? 'bg-[#1e3a5f] text-white shadow-sm'
                            : can
                              ? 'text-slate-700 hover:bg-white'
                              : 'cursor-not-allowed text-slate-300',
                        ].join(' ')}
                      >
                        {scorecardTrendToggleLabel(y)}
                      </button>
                    )
                  })}
                </div>
                <p className="text-[11px] leading-snug text-slate-500">
                  {scorecardTrendCompareCaption(trendYears, displayVintage, vyPrTrend)}
                </p>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {locationFips ? (
        <div className="rounded-xl border border-slate-400/45 bg-slate-300/35 p-2 shadow-sm sm:p-2.5">
          <ScorecardTrendLegend />
        </div>
      ) : null}

      {locationFips
        ? groups.map((g) => {
        const { letter, pill } = sectionGradeByGroupId.get(g.id) ?? { letter: '—', pill: 'No trend data' }

        return (
          <div key={`${g.id}-trend-${trendYears}`} className="rounded-xl border border-slate-400/45 bg-slate-300/35 p-2 shadow-sm sm:p-2.5">
            <section className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50 px-4 py-2">
              <div className="min-w-0 flex-1 space-y-2">
                <h2 className="text-sm font-semibold text-slate-900">{g.title}</h2>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-600"
                  title="Favorable trend count for the selected window (matches table trend column)"
                >
                  {pill}
                </span>
                <span
                  className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-slate-300 bg-white text-sm font-bold text-slate-800"
                  title={`Trend-only section grade (${scorecardRollingWindowAdjective(trendYears)} window). Changing U.S. / region / state benchmark does not recalculate this letter.`}
                >
                  {letter}
                </span>
              </div>
            </div>
            <table className="w-full min-w-0 table-fixed border-collapse text-left text-xs">
              <ScorecardColGroup showBench={showBenchmarkColumn} />
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/90 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                  <th className="min-w-0 px-3 py-2 align-top">Metric</th>
                  <th className="min-w-0 px-2 py-2 text-right align-top">
                    <span className="inline-flex items-center justify-end gap-1">
                      Current ({displayVintage})
                      <InfoHelpTrigger topic="Current value" help={helpCurrent} align="left" />
                    </span>
                  </th>
                  <th className="min-w-0 px-2 py-2 align-top">
                    <span className="inline-flex items-center gap-1">
                      Trend ({scorecardTrendToggleLabel(trendYears)})
                      <InfoHelpTrigger topic="Trend window" help={helpTrend} align="left" />
                    </span>
                  </th>
                  {showBenchmarkColumn ? (
                    <th className="min-w-0 px-3 py-2 align-top">
                      <span className="inline-flex items-center gap-1">
                        vs. {vsColumnShort}
                        <InfoHelpTrigger topic="Versus benchmark" help={helpVs} align="right" />
                      </span>
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {g.slugs.map((slug) => {
                  const meta = metricMeta.get(slug)
                  const dir = censusMetricRankDirection(slug)
                  const raw = primaryValueForSlug(stateTrends, manifest, locationFips, displayVintage, slug, locOpts)
                  const p1 = windowPctForSlug(stateTrends, manifest, locationFips, vintages, displayVintage, slug, 1, locOpts)
                  const p3 = windowPctForSlug(stateTrends, manifest, locationFips, vintages, displayVintage, slug, 3, locOpts)
                  const p5 = windowPctForSlug(stateTrends, manifest, locationFips, vintages, displayVintage, slug, 5, locOpts)
                  const pW = windowPctForSlug(
                    stateTrends,
                    manifest,
                    locationFips,
                    vintages,
                    displayVintage,
                    slug,
                    trendYears,
                    locOpts,
                  )
                  const stW = trendStatus(pW, dir)
                  const arrows = trendArrowMagnitude(pW, stW)
                  const neutralArrows = dir === 'neutral' ? neutralTrendArrowPack(pW) : null
                  const anyTrend = hasAnyTrendWindow(p1, p3, p5)
                  const benchCur = showBenchmarkColumn
                    ? benchValueForSlug(
                        stateTrends,
                        manifest,
                        benchKind,
                        regionForBench,
                        benchStateFips,
                        displayVintage,
                        slug,
                      )
                    : null
                  const cmp = showBenchmarkColumn ? compareCurrentToBenchmark(raw, benchCur, dir) : 'na'
                  const bW = showBenchmarkColumn
                    ? benchWindowPctForSlug(
                        stateTrends,
                        manifest,
                        benchKind,
                        regionForBench,
                        benchStateFips,
                        vintages,
                        displayVintage,
                        slug,
                        trendYears,
                      )
                    : null
                  const benchStale =
                    showBenchmarkColumn &&
                    (benchKind === 'state' && !benchStateFips
                      ? 'Pick a benchmark state.'
                      : benchKind === 'state' && benchStateFips && locationFips === benchStateFips
                        ? 'Pick a different benchmark state than your location.'
                        : null)
                  const giniNoTrend = slug === 'gini_income_inequality' && !anyTrend
                  const trendHeadlineDirected =
                    giniNoTrend || !anyTrend || dir === 'neutral' ? null : directedTrendHeadline(stW, arrows, dir, pW)
                  const paceLine =
                    showBenchmarkColumn && !giniNoTrend
                      ? paceVsBenchOneLiner(pW, bW, paceVersusLabel, paceWindowLabel)
                      : null

                  return (
                    <tr key={slug} className="border-b border-slate-100 hover:bg-slate-50/60">
                      <td className="min-w-0 break-words px-3 py-2 align-top font-medium text-slate-900">
                        <div>{meta?.label ?? slug}</div>
                        {slug === 'gini_income_inequality' ? (
                          <p className="mt-0.5 text-[10px] font-normal leading-snug text-slate-500">
                            ACS Gini measures how unevenly income is spread (0 = everyone the same, 1 = maximally
                            uneven). The letter is about equality of spread, not how “rich” the area is.
                          </p>
                        ) : null}
                      </td>
                      <td className="min-w-0 px-2 py-2 text-right align-top tabular-nums text-slate-800">
                        {slug === 'gini_income_inequality' && raw != null && Number.isFinite(raw) ? (
                          <GiniIncomeCurrentCell
                            gini={raw}
                            numericText={formatMetricValueDisplay(slug, raw, formatRows, 'raw', SCORECARD_VALUE_FMT)}
                          />
                        ) : (
                          formatMetricValueDisplay(slug, raw, formatRows, 'raw', SCORECARD_VALUE_FMT)
                        )}
                      </td>
                      <td className="min-w-0 px-2 py-2 align-top text-slate-800">
                        {giniNoTrend ? (
                          <div className="space-y-1">
                            <p className="text-[11px] leading-snug text-slate-600">
                              Snapshot only. Multi-year trend for this metric is not available in the published bundle for
                              every year slot (often missing in older vintages).
                            </p>
                            <span className="inline-block rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-900">
                              Trend: N/A
                            </span>
                          </div>
                        ) : !anyTrend ? (
                          <span className="text-slate-400">—</span>
                        ) : dir === 'neutral' ? (
                          <div className="flex flex-col gap-1">
                            <div className="flex flex-wrap items-baseline gap-1.5 tabular-nums">
                              <span
                                className="font-mono text-base text-slate-800"
                                title={scorecardTrendPercentTitle(trendYears, true)}
                              >
                                {neutralArrows?.arrow ?? '—'}
                              </span>
                              <span className="text-sm font-semibold text-slate-900">
                                {pW == null ? '—' : `${pW > 0 ? '+' : ''}${pW.toFixed(SCORECARD_PCT_DECIMALS)}%`}
                              </span>
                              <span className="text-[11px] text-slate-500">{scorecardTrendOverLine(trendYears)}</span>
                            </div>
                            <div>{neutralChangeBadge(neutralArrows ?? { arrow: '—', label: '' }, trendYears)}</div>
                          </div>
                        ) : (
                          <div className="flex flex-col gap-1">
                            {trendHeadlineDirected ? (
                              <p className="text-[11px] font-semibold leading-snug text-slate-800">{trendHeadlineDirected}</p>
                            ) : null}
                            <div className="flex flex-wrap items-baseline gap-1.5 tabular-nums">
                              <span
                                className="font-mono text-base text-slate-800"
                                title={scorecardTrendPercentTitle(trendYears, false)}
                              >
                                {arrows.arrow}
                              </span>
                              <span className="text-sm font-semibold text-slate-900">
                                {pW == null ? '—' : `${pW > 0 ? '+' : ''}${pW.toFixed(SCORECARD_PCT_DECIMALS)}%`}
                              </span>
                              <span className="text-[11px] text-slate-500">{scorecardTrendOverLine(trendYears)}</span>
                            </div>
                            <div>{favorabilityPill(stW)}</div>
                          </div>
                        )}
                      </td>
                      {showBenchmarkColumn ? (
                        <td className="min-w-0 border-l border-slate-100 px-3 py-2 align-top text-[11px] leading-snug text-slate-700">
                          {benchStale ? (
                            <span className="text-slate-400">{benchStale}</span>
                          ) : (
                            <div className="space-y-1.5">
                              <BenchmarkComparePill cmp={cmp} benchKind={benchKind} pillNames={pillNames} />
                              <span className="sr-only">{spokenBenchPosition(cmp)}</span>
                              {giniNoTrend ? (
                                <p className="text-[10px] text-slate-500">
                                  Trend N/A; chip still reflects latest-year value vs benchmark.
                                </p>
                              ) : paceLine ? (
                                <p className="text-[10px] text-slate-500">{paceLine}</p>
                              ) : null}
                            </div>
                          )}
                        </td>
                      ) : null}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </section>
          </div>
        )
      })
        : null}

      {locationFips ? (
        <div className="rounded-xl border border-slate-400/45 bg-slate-300/35 p-2 shadow-sm sm:p-2.5">
          <ScorecardGiniLegend />
        </div>
      ) : null}
    </div>
  )
}
