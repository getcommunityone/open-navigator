import type { CensusRegionId } from './censusRegions'
import { STATE_FIPS_TO_CENSUS_REGION } from './censusRegions'

/** How choropleth values are derived from ACS estimates. */
export type CensusValueMode = 'raw' | 'yoy' | 'vs_natl'

export type NationalRefEntry = { us?: number | null; pop_weighted_states?: number | null }

export function nationalBaseline(
  nationalRef: Record<string, Record<string, NationalRefEntry>> | undefined,
  vintage: string,
  slug: string,
): number | null {
  const b = nationalRef?.[vintage]?.[slug]
  if (!b) return null
  const w = b.pop_weighted_states
  const u = b.us
  if (typeof w === 'number' && Number.isFinite(w) && w !== 0) return w
  if (typeof u === 'number' && Number.isFinite(u) && u !== 0) return u
  return null
}

/**
 * Population-weighted composite of a metric across state rows (matches export logic when
 * ``national_ref`` is absent).
 */
export function populationWeightedCompositeFromStateRows(
  rows: Record<string, Record<string, unknown>> | undefined,
  valueKey: string,
  weightKey = 'total_population',
): number | null {
  if (!rows) return null
  let num = 0
  let den = 0
  for (const row of Object.values(rows)) {
    const pop = row[weightKey]
    const v = row[valueKey]
    if (typeof pop !== 'number' || !Number.isFinite(pop) || pop <= 0) continue
    if (typeof v !== 'number' || !Number.isFinite(v)) continue
    num += v * pop
    den += pop
  }
  if (!(den > 0)) return null
  const out = num / den
  return Number.isFinite(out) && out !== 0 ? out : null
}

function coerceFiniteNumber(v: unknown): number | null {
  if (typeof v === 'number' && Number.isFinite(v)) return v
  if (typeof v === 'string' && v.trim() !== '') {
    const n = Number(v)
    return Number.isFinite(n) ? n : null
  }
  return null
}

/** Read one ACS vintage from a sidecar year→value object (numbers or numeric strings). */
export function trendCell(series: unknown, vy: string): number | null {
  if (!series || typeof series !== 'object' || Array.isArray(series)) return null
  const key = String(vy)
  const raw = (series as Record<string, unknown>)[key]
  return coerceFiniteNumber(raw)
}

/** Same weighting as ``populationWeightedCompositeFromStateRows`` using trend sidecar series. */
export function nationalWeightedCompositeFromStateTrends(
  trends: { by_state: Record<string, Record<string, unknown>> } | null | undefined,
  vintage: string,
  slug: string,
): number | null {
  if (!trends?.by_state) return null
  let num = 0
  let den = 0
  for (const row of Object.values(trends.by_state)) {
    const popSeries = row['total_population']
    const valSeries = row[slug]
    let pop: number | null = null
    if (typeof popSeries === 'object' && popSeries != null && !Array.isArray(popSeries)) {
      pop = trendCell(popSeries, vintage)
    } else if (typeof popSeries === 'number' && Number.isFinite(popSeries)) {
      pop = popSeries
    }
    let v: number | null = null
    if (typeof valSeries === 'object' && valSeries != null && !Array.isArray(valSeries)) {
      v = trendCell(valSeries, vintage)
    } else if (typeof valSeries === 'number' && Number.isFinite(valSeries)) {
      v = valSeries
    }
    if (typeof pop !== 'number' || !Number.isFinite(pop) || pop <= 0) continue
    if (typeof v !== 'number' || !Number.isFinite(v)) continue
    num += v * pop
    den += pop
  }
  if (!(den > 0)) return null
  const out = num / den
  return Number.isFinite(out) ? out : null
}

/**
 * Published ``national_ref`` from the static manifest when present; otherwise the same
 * population-weighted U.S. composite computed from state rows or the multi-year state sidecar
 * (fixes older bundles / missing US parquet rows so “% vs national” still maps).
 */
export function nationalBaselineWithFallback(
  nationalRef: Record<string, Record<string, NationalRefEntry>> | undefined,
  vintage: string,
  slug: string,
  opts?: {
    stateRows?: Record<string, Record<string, unknown>>
    stateTrends?: { by_state: Record<string, Record<string, unknown>> } | null
  },
): number | null {
  const direct = nationalBaseline(nationalRef, vintage, slug)
  if (direct != null && Number.isFinite(direct) && direct !== 0) return direct
  const fromRows = opts?.stateRows
    ? populationWeightedCompositeFromStateRows(opts.stateRows, slug)
    : null
  if (fromRows != null && Number.isFinite(fromRows) && fromRows !== 0) return fromRows
  const fromTrends = opts?.stateTrends
    ? nationalWeightedCompositeFromStateTrends(opts.stateTrends, vintage, slug)
    : null
  if (fromTrends != null && Number.isFinite(fromTrends) && fromTrends !== 0) return fromTrends
  return null
}

export function displayValueForMode(
  mode: CensusValueMode,
  raw: number | null,
  prevRaw: number | null,
  baseline: number | null,
): number | null {
  if (raw == null || !Number.isFinite(raw)) return null
  if (mode === 'raw') return raw
  if (mode === 'vs_natl') {
    if (baseline == null || baseline === 0) return null
    return ((raw / baseline) - 1) * 100
  }
  if (mode === 'yoy') {
    if (prevRaw == null || !Number.isFinite(prevRaw) || prevRaw === 0) return null
    return ((raw - prevRaw) / prevRaw) * 100
  }
  return raw
}

export function prevVintageInList(vintages: string[], current: string): string | null {
  const i = vintages.indexOf(String(current))
  return i > 0 ? vintages[i - 1]! : null
}

/** ``n`` steps earlier in the ascending vintage list (1 = prior year slot). */
export function prevVintageNBack(vintages: string[], current: string, n: number): string | null {
  const i = vintages.indexOf(String(current))
  if (i < 0 || n < 1) return null
  const j = i - n
  return j >= 0 ? vintages[j]! : null
}

/**
 * Comparison end-year exactly ``calendarYearsBack`` before ``current`` (e.g. 5 → 2024 vs 2019).
 * Used for scorecard 3yr / 5yr windows so we compare by calendar span on the ACS end-year axis,
 * not by “N rows back” in the vintage list (which misaligns when the bundle skips years).
 */
export function prevVintageCalendarYearsBack(
  vintages: string[],
  current: string,
  calendarYearsBack: number,
): string | null {
  const cur = String(current).trim()
  const y = Number(cur)
  if (!Number.isFinite(y) || calendarYearsBack < 1) return null
  const target = String(y - calendarYearsBack)
  return vintages.includes(target) ? target : null
}

/** Scorecard trend toggle: 1yr = successive published end-year in the list; 3yr/5yr = calendar gap. */
export function prevVintageForScorecardTrend(
  vintages: string[],
  current: string,
  trendYears: 1 | 3 | 5,
): string | null {
  if (trendYears === 1) return prevVintageInList(vintages, current)
  return prevVintageCalendarYearsBack(vintages, current, trendYears)
}

export function pctChangeBetween(now: number | null, prev: number | null): number | null {
  if (now == null || prev == null || !Number.isFinite(now) || !Number.isFinite(prev) || prev === 0) return null
  const p = ((now - prev) / prev) * 100
  return Number.isFinite(p) ? p : null
}

/** Population-weighted composite for one Census region (states in ``STATE_FIPS_TO_CENSUS_REGION``). */
export function regionalWeightedCompositeFromStateTrends(
  trends: { by_state: Record<string, Record<string, unknown>> } | null | undefined,
  region: CensusRegionId,
  vintage: string,
  slug: string,
): number | null {
  if (!trends?.by_state) return null
  let num = 0
  let den = 0
  for (const [fidRaw, row] of Object.entries(trends.by_state)) {
    const fid = String(fidRaw).replace(/\D/g, '').slice(-2).padStart(2, '0')
    const r = STATE_FIPS_TO_CENSUS_REGION[fid]
    if (r !== region) continue
    const popSeries = row['total_population']
    const valSeries = row[slug]
    let pop: number | null = null
    if (typeof popSeries === 'object' && popSeries != null && !Array.isArray(popSeries)) {
      pop = trendCell(popSeries, vintage)
    } else if (typeof popSeries === 'number' && Number.isFinite(popSeries)) {
      pop = popSeries
    }
    let v: number | null = null
    if (typeof valSeries === 'object' && valSeries != null && !Array.isArray(valSeries)) {
      v = trendCell(valSeries, vintage)
    } else if (typeof valSeries === 'number' && Number.isFinite(valSeries)) {
      v = valSeries
    }
    if (typeof pop !== 'number' || !Number.isFinite(pop) || pop <= 0) continue
    if (typeof v !== 'number' || !Number.isFinite(v)) continue
    num += v * pop
    den += pop
  }
  if (!(den > 0)) return null
  const out = num / den
  return Number.isFinite(out) ? out : null
}
