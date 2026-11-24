/** Pure maths for the Data explorer Matrix map (tested in matrixMapMath.test.ts). */

/** 0..1 position of `v` between `lo` and `hi`; flipped when lower values rank better. Null when it can't be placed. */
export function shadeT(v: number | null | undefined, lo: number, hi: number, lowerIsBetter: boolean): number | null {
  if (v == null || !Number.isFinite(v) || hi === lo) return null
  const t = (v - lo) / (hi - lo)
  return lowerIsBetter ? 1 - t : t
}

/** Median of the finite values; the mean of the two middle values for an even count. Null when empty. */
export function medianOf(values: Array<number | null | undefined>): number | null {
  const xs = values.filter((x): x is number => x != null && Number.isFinite(x)).sort((a, b) => a - b)
  if (!xs.length) return null
  const mid = Math.floor(xs.length / 2)
  return xs.length % 2 ? xs[mid]! : (xs[mid - 1]! + xs[mid]!) / 2
}

/** Whole-number cells per part that always sum to `cells` (largest-remainder method). Empty for a zero total. */
export function largestRemainder(values: number[], cells = 100): number[] {
  const total = values.reduce((a, v) => a + v, 0)
  if (total <= 0) return []
  const raw = values.map((v) => (v / total) * cells)
  const out = raw.map(Math.floor)
  let left = cells - out.reduce((a, c) => a + c, 0)
  raw
    .map((r, i) => ({ i, f: r - Math.floor(r) }))
    .sort((a, b) => b.f - a.f || a.i - b.i)
    .forEach(({ i }) => {
      if (left > 0) {
        out[i]! += 1
        left -= 1
      }
    })
  return out
}

export interface OlsFit {
  slope: number
  intercept: number
  r2: number
  n: number
}

/** Ordinary least squares of y on x. Null with fewer than 3 points or no spread in x. */
export function olsFit(points: Array<{ x: number; y: number }>): OlsFit | null {
  const n = points.length
  if (n < 3) return null
  const mx = points.reduce((a, p) => a + p.x, 0) / n
  const my = points.reduce((a, p) => a + p.y, 0) / n
  const sxx = points.reduce((a, p) => a + (p.x - mx) ** 2, 0)
  const sxy = points.reduce((a, p) => a + (p.x - mx) * (p.y - my), 0)
  const syy = points.reduce((a, p) => a + (p.y - my) ** 2, 0)
  if (!sxx) return null
  const slope = sxy / sxx
  return { slope, intercept: my - slope * mx, r2: syy ? (sxy * sxy) / (sxx * syy) : 0, n }
}

/** Which key the rows are ordered by: the pivot's chosen header, otherwise the metric on screen. */
export function activeSortKey(layout: string, metricSlug: string, sortParam: string, cols: string[]): string {
  return layout === 'pivot' ? sortParam || cols[0] || '' : metricSlug
}
