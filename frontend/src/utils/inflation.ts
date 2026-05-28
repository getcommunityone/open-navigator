/**
 * Inflation deflator — converts nominal dollars from one year into constant
 * dollars of another year using an annual CPI index map.
 *
 * Math: ``value_in_target_year_dollars = value * (cpi[target] / cpi[from])``.
 *
 * One national CPI series is applied uniformly to every geography — see
 * ``api/routes/cpi.py`` and the design note in
 * ``scripts/datasources/bls/load_bls_cpi.py``: deflating each place by a
 * local CPI would bake regional inflation into the yardstick and break
 * cross-place real-dollar comparisons. One tape measure for everyone.
 */

export type CpiByYear = Record<string, number>

/** Deflate ``value`` from ``fromYear`` dollars into ``toYear`` dollars.
 *  Returns ``null`` if either CPI reading is missing or zero — callers
 *  should fall back to nominal in that case rather than show a misleading
 *  number. */
export function deflate(
  value: number | null | undefined,
  fromYear: number | string | null | undefined,
  toYear: number | string | null | undefined,
  cpi: CpiByYear | null | undefined,
): number | null {
  if (value == null || !Number.isFinite(value as number)) return null
  if (fromYear == null || toYear == null || !cpi) return null
  const fromIdx = cpi[String(fromYear)]
  const toIdx = cpi[String(toYear)]
  if (
    typeof fromIdx !== 'number' ||
    !Number.isFinite(fromIdx) ||
    fromIdx === 0 ||
    typeof toIdx !== 'number' ||
    !Number.isFinite(toIdx)
  )
    return null
  // Same year is a no-op (cpi[from]==cpi[to], ratio = 1) — but spelling it
  // out avoids a needless float multiply and the resulting trailing-digit
  // jitter when the headline value should be visually unchanged.
  if (String(fromYear) === String(toYear)) return value as number
  return (value as number) * (toIdx / fromIdx)
}

/** Year in ``points`` with the maximum ``y``, ``null`` if the series is
 *  empty or the peak coincides with the latest displayed year (in which
 *  case "peaked in YYYY" is not interesting — the value IS the peak). */
export function peakYearOf(
  points: { x: number; y: number }[],
  latestDisplayedYear: number | string | null | undefined,
): number | null {
  if (!points.length) return null
  let peakX = points[0]!.x
  let peakY = points[0]!.y
  for (const p of points) {
    if (p.y > peakY) {
      peakY = p.y
      peakX = p.x
    }
  }
  if (latestDisplayedYear != null && String(peakX) === String(latestDisplayedYear)) {
    return null
  }
  return peakX
}

/** Census metric slugs whose values are dollars and therefore subject to
 *  the Nominal / Real toggle. Anything not listed renders nominal-only. */
const DOLLAR_METRIC_SLUGS = new Set<string>([
  'median_home_value',
  'median_household_income',
  'median_gross_rent',
  'per_capita_income',
])

export function isDollarMetric(slug: string | null | undefined): boolean {
  if (!slug) return false
  return DOLLAR_METRIC_SLUGS.has(slug)
}
