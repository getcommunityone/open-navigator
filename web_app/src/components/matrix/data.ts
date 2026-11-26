import type { CSSProperties } from 'react'
import { censusRegionForStateFips } from '../../utils/censusRegions'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'
import type { FolioTheme } from '../../utils/folioThemes'
import { labelOn } from '../../utils/folioRamp'
import { signedChange as signedChange0 } from '../../utils/matrixTable'
import { nameList, type Item } from '../../utils/matrixStory'
import type { MatrixCtx, Metric, Row, StatePayload } from './types'

export const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)

/** State rows from one vintage's `state_metrics.json` (only FIPS codes that map to a state/territory code). */
export function rowsFromPayload(payload: StatePayload | null | undefined): Row[] {
  const values = payload?.values ?? {}
  return Object.entries(values)
    .map(([fips, v]) => {
      const fips2 = fips.padStart(2, '0')
      const code = STATE_FIPS_TO_CODE[fips2] ?? ''
      return {
        fips: fips2,
        code,
        name: STATE_CODE_TO_NAME[code] ?? code ?? fips,
        region: censusRegionForStateFips(fips),
        vals: Object.fromEntries(Object.entries(v ?? {}).map(([k, x]) => [k, num(x)])),
      } satisfies Row
    })
    .filter((r) => r.code)
}

/** Same bins as the Folio reference heatmap (value 0..1 -> one of six steps). */
export const BIN_EDGES = [0.1, 0.25, 0.45, 0.65, 0.8]
export const stepOf = (t: number | null): number | null => (t == null ? null : BIN_EDGES.filter((e) => t >= e).length)
export const stepColor = (theme: FolioTheme, t: number | null): string => {
  const k = stepOf(t)
  return k == null ? theme.neutral : theme.ramp[k]!
}
export const inkOf = (theme: FolioTheme): string => theme.vars['--ink']!
/** Label colour for a filled cell: the best of the theme ink or white (AA checked per theme in folioRamp.test.ts). */
export const labelFor = (theme: FolioTheme, bg: string): string => labelOn(bg, [inkOf(theme)])
export const cellStyle = (theme: FolioTheme, t: number | null, minPct: number): CSSProperties => {
  const dim = minPct > 0 && (t == null || t * 100 < minPct)
  const bg = dim ? theme.neutral : stepColor(theme, t)
  return { background: bg, color: labelFor(theme, bg) }
}

/** Rows ordered by one metric (missing values last), ties by name. */
export function sortByMetric(rows: Row[], slug: string, dir: 'asc' | 'desc'): Row[] {
  const d = dir === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    const av = a.vals[slug]
    const bv = b.vals[slug]
    if (av == null && bv == null) return a.name.localeCompare(b.name)
    if (av == null) return 1
    if (bv == null) return -1
    return (av - bv) * d || a.name.localeCompare(b.name)
  })
}

/** Rows ordered by the shared `?sort=` key ("name" or a metric slug) and `?dir=`. */
export function sortByKey(rows: Row[], key: string, dir: 'asc' | 'desc'): Row[] {
  if (key === 'name') return [...rows].sort((a, b) => a.name.localeCompare(b.name) * (dir === 'asc' ? 1 : -1))
  return sortByMetric(rows, key, dir)
}

export const metricOf = (metrics: Metric[], slug: string): Metric | undefined => metrics.find((m) => m.slug === slug)

/**
 * Change between two readings in the metric's own unit: "+13 pp" for percentage metrics, a signed formatted number
 * otherwise. "—" when either reading is missing: a change is never computed from a missing value.
 */
export function signedChange(
  slug: string,
  base: number | null | undefined,
  latest: number | null | undefined,
  metrics: Metric[],
  fmt: (slug: string, v: number | null) => string,
): string {
  return signedChange0(latest, base, metricOf(metrics, slug)?.format === 'percent' ? 'pp' : 'number', (a) => fmt(slug, a)) ?? '—'
}

/** "52 states and territories" style count noun for the figures in scope. */
export const geoNounFor = (n: number): string => (n === 1 ? '1 state or territory' : `${n.toLocaleString('en-US')} states and territories`)

/** The rows as name + value pairs for one metric, the input the story sentences (utils/matrixStory.ts) read. */
export const itemsOf = (rows: Row[], slug: string): Item[] => rows.map((r) => ({ name: r.name, value: r.vals[slug] ?? null }))

/** Row for the shared scope text. */
export const scopeText = (ctx: Pick<MatrixCtx, 'vintage'>): string => `${ctx.vintage} ACS 5-year`

/**
 * Rank shade 0..1 for each geography on one metric: 1 = best rank, 0 = worst, equal values share a rank, missing values get
 * no shade. "Best" is the higher value unless lower is better for the metric.
 */
export function rankShade(rows: Row[], slug: string, lowerIsBetter: boolean): Map<string, number | null> {
  const withVal = rows.filter((r) => r.vals[slug] != null)
  const sorted = withVal.map((r) => r.vals[slug] as number).sort((a, b) => (lowerIsBetter ? a - b : b - a))
  const out = new Map<string, number | null>()
  for (const r of rows) {
    const v = r.vals[slug]
    if (v == null || sorted.length < 2) {
      out.set(r.fips, null)
      continue
    }
    out.set(r.fips, 1 - sorted.indexOf(v) / (sorted.length - 1))
  }
  return out
}

export interface MetricStats {
  n: number
  median: number | null
  high: { r: Row; v: number } | null
  low: { r: Row; v: number } | null
  /** Every geography that shares the highest / lowest value (ties), by name. */
  highNames: string[]
  lowNames: string[]
}
/** Count, median, highest and lowest of one metric over `rows` (missing values skipped). */
export function statsOf(rows: Row[], slug: string): MetricStats {
  const xs = rows.flatMap((r) => (r.vals[slug] != null ? [{ r, v: r.vals[slug] as number }] : []))
  const sorted = [...xs].sort((a, b) => a.v - b.v)
  const mid = Math.floor(sorted.length / 2)
  const median = !sorted.length ? null : sorted.length % 2 ? sorted[mid]!.v : (sorted[mid - 1]!.v + sorted[mid]!.v) / 2
  const high = sorted[sorted.length - 1] ?? null
  const low = sorted[0] ?? null
  const named = (v: number | undefined) => (v == null ? [] : xs.filter((x) => x.v === v).map((x) => x.r.name).sort((a, b) => a.localeCompare(b)))
  return { n: xs.length, median, high, low, highNames: named(high?.v), lowNames: named(low?.v) }
}

/** "Highest / lowest / median" sentence for the text column, all from the rows in scope. */
export function statsSentence(st: MetricStats, slug: string, fmt: (slug: string, v: number | null) => string): string {
  if (!st.n || !st.high || !st.low) return 'No data available for this metric in the scope shown.'
  return `Highest: ${nameList(st.highNames)} (${fmt(slug, st.high.v)}). Lowest: ${nameList(st.lowNames)} (${fmt(slug, st.low.v)}). Median: ${fmt(slug, st.median)}. ${st.n} ${st.n === 1 ? 'geography has' : 'geographies have'} a value.`
}
