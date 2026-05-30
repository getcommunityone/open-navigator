import type { CensusMetricRankDirection } from './censusDataDictionary'
import type { CensusRegionId } from './censusRegions'
import {
  nationalBaselineWithFallback,
  nationalWeightedCompositeFromStateTrends,
  pctChangeBetween,
  prevVintageForScorecardTrend,
  regionalWeightedCompositeFromStateTrends,
  trendCell,
} from './censusMapValueMode'

type ManifestLite = {
  national_ref?: Record<string, Record<string, { us?: number | null; pop_weighted_states?: number | null }>>
}

type TrendsLite = {
  vintages?: string[]
  by_state: Record<string, Record<string, unknown>>
}

/** County / place multi-year sidecar (``county_trends_{st}.json`` / ``place_trends_{st}.json``). */
export type CountyPlaceTrendsSidecar = {
  geography?: string
  state?: string
  vintages?: string[]
  byGeoid: Record<string, Record<string, unknown>>
}

export type ScorecardSubGeography =
  | { level: 'state' }
  | { level: 'county'; geoid5: string }
  | { level: 'place'; geoid7: string }

export type ScorecardLocationOpts = {
  countyTrends?: CountyPlaceTrendsSidecar | null
  placeTrends?: CountyPlaceTrendsSidecar | null
  sub: ScorecardSubGeography
}

/** 5-digit county GEOID (state FIPS + county code). */
export function countyGeoid5FromParam(raw: string | null | undefined, stateFips: string): string | null {
  if (raw == null || raw === '') return null
  const d = String(raw).replace(/\D/g, '')
  if (!d) return null
  const st = stateFips.replace(/\D/g, '').slice(0, 2).padStart(2, '0')
  if (d.length <= 3) return `${st}${d.padStart(3, '0')}`
  if (d.length === 5) return d
  return d.slice(-5).padStart(5, '0')
}

/** 7-digit place GEOID (must align with ``place_trends_{st}.json`` keys). */
export function placeGeoid7FromParam(raw: string | null | undefined, stateFips: string): string | null {
  if (raw == null || raw === '') return null
  const d = String(raw).replace(/\D/g, '')
  if (!d || d.length < 5) return null
  const st = stateFips.replace(/\D/g, '').slice(0, 2).padStart(2, '0')
  const g7 = d.length >= 7 ? d.slice(-7).padStart(7, '0') : d.padStart(7, '0')
  if (!g7.startsWith(st)) return null
  return g7
}

export function primarySeriesRowForScorecard(
  stateTrends: TrendsLite,
  countyTrends: CountyPlaceTrendsSidecar | null | undefined,
  placeTrends: CountyPlaceTrendsSidecar | null | undefined,
  stateFips: string,
  sub: ScorecardSubGeography,
): Record<string, unknown> | undefined {
  const st = stateFips.replace(/\D/g, '').slice(0, 2).padStart(2, '0')
  if (sub.level === 'state') {
    return primarySeriesRow(stateTrends, st)
  }
  if (sub.level === 'county') {
    const g = sub.geoid5.replace(/\D/g, '').slice(-5).padStart(5, '0')
    if (!g.startsWith(st)) return undefined
    return countyTrends?.byGeoid[g] as Record<string, unknown> | undefined
  }
  const g7 = sub.geoid7.replace(/\D/g, '').slice(-7).padStart(7, '0')
  if (!g7.startsWith(st)) return undefined
  return placeTrends?.byGeoid[g7] as Record<string, unknown> | undefined
}

export function seriesValue(
  row: Record<string, unknown> | undefined,
  slug: string,
  vy: string,
): number | null {
  if (!row) return null
  const ser = row[slug]
  return trendCell(ser, vy)
}

export function primarySeriesRow(
  trends: TrendsLite | null | undefined,
  stateFips: string | null,
): Record<string, unknown> | undefined {
  if (!trends?.by_state) return undefined
  if (!stateFips) return undefined
  const k = stateFips.padStart(2, '0')
  return trends.by_state[k] ?? trends.by_state[stateFips]
}

export function nationalValueForSlug(
  trends: TrendsLite | null | undefined,
  manifest: ManifestLite | undefined,
  vy: string,
  slug: string,
): number | null {
  const w = nationalWeightedCompositeFromStateTrends(trends, vy, slug)
  if (w != null) return w
  return nationalBaselineWithFallback(manifest?.national_ref, vy, slug, { stateTrends: trends ?? undefined })
}

export function benchValueForSlug(
  trends: TrendsLite,
  manifest: ManifestLite | undefined,
  benchKind: 'country' | 'region' | 'state',
  regionForBench: CensusRegionId | null,
  benchStateFips: string | null,
  vy: string,
  slug: string,
): number | null {
  if (benchKind === 'country') {
    return nationalValueForSlug(trends, manifest, vy, slug)
  }
  if (benchKind === 'region' && regionForBench) {
    return regionalWeightedCompositeFromStateTrends(trends, regionForBench, vy, slug)
  }
  if (benchKind === 'state' && benchStateFips) {
    const row = primarySeriesRow(trends, benchStateFips)
    return seriesValue(row, slug, vy)
  }
  return null
}

export function windowPctForSlug(
  trends: TrendsLite,
  manifest: ManifestLite | undefined,
  locationFips: string | null,
  vintages: string[],
  displayVintage: string,
  slug: string,
  yearsBack: 1 | 3 | 5,
  locOpts?: ScorecardLocationOpts | null,
): number | null {
  const cur = displayVintage
  const prev = prevVintageForScorecardTrend(vintages, cur, yearsBack)
  if (!prev) return null
  const a =
    locationFips != null
      ? primaryValueForSlug(trends, manifest, locationFips, cur, slug, locOpts ?? null)
      : nationalValueForSlug(trends, manifest, cur, slug)
  const b =
    locationFips != null
      ? primaryValueForSlug(trends, manifest, locationFips, prev, slug, locOpts ?? null)
      : nationalValueForSlug(trends, manifest, prev, slug)
  return pctChangeBetween(a, b)
}

export type TrendArrowPack = {
  arrow: string
  label: string
}

/** Arrow follows the signed ACS % change (↑ if the estimate rose, ↓ if it fell). Label is only magnitude (Strong / Slight). */
export function trendArrowMagnitude(
  pct: number | null,
  status: 'good' | 'bad' | 'flat' | 'na',
): TrendArrowPack {
  if (pct == null || !Number.isFinite(pct) || status === 'na') {
    return { arrow: '—', label: '' }
  }
  const a = Math.abs(pct)
  if (a < 0.02 || status === 'flat') {
    return { arrow: '→', label: 'Flat' }
  }
  const strong = a >= 8
  const up = pct > 0
  const arrow = up ? (strong ? '↑↑' : '↑') : strong ? '↓↓' : '↓'
  const label = strong ? 'Strong' : 'Slight'
  return { arrow, label }
}

/**
 * For metrics with no built-in “higher is better” rule: describe 5-year % move without calling it favorable.
 */
export function neutralTrendArrowPack(pct: number | null): TrendArrowPack {
  if (pct == null || !Number.isFinite(pct)) {
    return { arrow: '—', label: '' }
  }
  const a = Math.abs(pct)
  if (a < 0.02) {
    return { arrow: '→', label: 'Flat' }
  }
  const strong = a >= 8
  if (pct > 0) {
    return strong ? { arrow: '↑↑', label: 'Large rise' } : { arrow: '↑', label: 'Small rise' }
  }
  return strong ? { arrow: '↓↓', label: 'Large fall' } : { arrow: '↓', label: 'Small fall' }
}

export type BenchCompare = 'ahead' | 'behind' | 'inline' | 'na'

export type BenchComparePillTone = 'ahead' | 'behind' | 'inline' | 'na'

export type BenchPillNames = {
  /** Census region name, e.g. "Northeast" (not including the word "region"). */
  region?: string | null
  /** Full benchmark state name, e.g. "Massachusetts". */
  state?: string | null
}

/** Short labels for benchmark comparison chips (scorecard / map-adjacent UI). */
export function benchComparePillMeta(
  cmp: BenchCompare,
  benchKind: 'country' | 'region' | 'state',
  names?: BenchPillNames | null,
): { label: string; tone: BenchComparePillTone } {
  if (cmp === 'na') return { label: 'No benchmark', tone: 'na' }
  const region = names?.region?.trim() || null
  const state = names?.state?.trim() || null
  if (benchKind === 'country') {
    if (cmp === 'ahead') return { label: 'Above U.S. avg', tone: 'ahead' }
    if (cmp === 'behind') return { label: 'Below U.S. avg', tone: 'behind' }
    return { label: 'Near U.S. avg', tone: 'inline' }
  }
  if (benchKind === 'region') {
    const r = region ? `${region} avg` : 'region avg'
    if (cmp === 'ahead') return { label: `Above ${r}`, tone: 'ahead' }
    if (cmp === 'behind') return { label: `Below ${r}`, tone: 'behind' }
    return { label: `Near ${r}`, tone: 'inline' }
  }
  const s = state ?? 'benchmark state'
  if (cmp === 'ahead') return { label: `Above ${s}`, tone: 'ahead' }
  if (cmp === 'behind') return { label: `Below ${s}`, tone: 'behind' }
  return { label: `Near ${s}`, tone: 'inline' }
}

/** Current value vs benchmark value (same ACS year). */
export function compareCurrentToBenchmark(
  raw: number | null,
  bench: number | null,
  dir: CensusMetricRankDirection,
): BenchCompare {
  if (raw == null || bench == null || !Number.isFinite(raw) || !Number.isFinite(bench) || bench === 0) return 'na'
  const margin = 0.025
  const ratio = raw / bench
  if (dir === 'neutral') {
    if (Math.abs(ratio - 1) < 0.04) return 'inline'
    return ratio > 1 ? 'ahead' : 'behind'
  }
  if (dir === 'higher') {
    if (ratio > 1 + margin) return 'ahead'
    if (ratio < 1 - margin) return 'behind'
    return 'inline'
  }
  if (raw < bench * (1 - margin)) return 'ahead'
  if (raw > bench * (1 + margin)) return 'behind'
  return 'inline'
}

export function benchCompareLabel(c: BenchCompare): string {
  switch (c) {
    case 'ahead':
      return 'Ahead of benchmark'
    case 'behind':
      return 'Behind benchmark'
    case 'inline':
      return 'In line with benchmark'
    default:
      return '—'
  }
}

export function paceVsBenchOneLiner(
  areaPct: number | null,
  benchPct: number | null,
  /** e.g. "the U.S. average", "the Northeast region average", "Massachusetts" */
  versusLabel = 'the benchmark',
  /** e.g. "5-year", "1-year" — must match the trend window used for the two series */
  windowLabel = '5-year',
): string | null {
  if (areaPct == null || benchPct == null || !Number.isFinite(areaPct) || !Number.isFinite(benchPct)) return null
  const d = areaPct - benchPct
  if (!Number.isFinite(d)) return null
  if (Math.abs(d) < 0.15) return `Same ${windowLabel} pace as ${versusLabel}`
  if (d > 0) return `Faster ${windowLabel} pace than ${versusLabel} (+${d.toFixed(1)} pp)`
  return `Slower ${windowLabel} pace than ${versusLabel} (${d.toFixed(1)} pp)`
}

export function benchWindowPctForSlug(
  trends: TrendsLite,
  manifest: ManifestLite | undefined,
  benchKind: 'country' | 'region' | 'state',
  regionForBench: CensusRegionId | null,
  benchStateFips: string | null,
  vintages: string[],
  displayVintage: string,
  slug: string,
  yearsBack: 1 | 3 | 5,
): number | null {
  const cur = displayVintage
  const prev = prevVintageForScorecardTrend(vintages, cur, yearsBack)
  if (!prev) return null
  const a = benchValueForSlug(trends, manifest, benchKind, regionForBench, benchStateFips, cur, slug)
  const b = benchValueForSlug(trends, manifest, benchKind, regionForBench, benchStateFips, prev, slug)
  return pctChangeBetween(a, b)
}

export function primaryValueForSlug(
  trends: TrendsLite,
  manifest: ManifestLite | undefined,
  locationFips: string | null,
  vy: string,
  slug: string,
  locOpts?: ScorecardLocationOpts | null,
): number | null {
  if (locationFips != null) {
    const st = locationFips.replace(/\D/g, '').slice(0, 2).padStart(2, '0')
    const sub = locOpts?.sub ?? { level: 'state' as const }
    const row = primarySeriesRowForScorecard(
      trends,
      locOpts?.countyTrends,
      locOpts?.placeTrends,
      st,
      sub,
    )
    return seriesValue(row, slug, vy)
  }
  return nationalValueForSlug(trends, manifest, vy, slug)
}

export function hasAnyTrendWindow(
  p1: number | null,
  p3: number | null,
  p5: number | null,
): boolean {
  return [p1, p3, p5].some((x) => x != null && Number.isFinite(x))
}
