/** Pure motion maths for the Matrix map "Folio" look (tested in folioMotion.test.ts). */

/** Longest total reveal for a row-by-row chart, in ms (a 52-row chart finishes within about 1.2 s). */
export const ROW_STAGGER_BUDGET_MS = 600

/** Delay for a cell on the diagonal wave: 0 at the top-left corner, `spanMs` at the far corner. */
export function staggerDelayMs(col: number, row: number, maxDiag: number, spanMs = 900): number {
  if (!(maxDiag > 0) || !Number.isFinite(col) || !Number.isFinite(row)) return 0
  const d = ((col + row) / maxDiag) * spanMs
  return Math.min(spanMs, Math.max(0, d))
}

/** Per-row delay: `perRowMs` apart, but squeezed so the last row starts no later than `budgetMs`. */
export function rowDelayMs(index: number, count: number, perRowMs = 50, budgetMs = ROW_STAGGER_BUDGET_MS): number {
  if (count <= 1 || index <= 0) return 0
  const step = Math.min(perRowMs, budgetMs / (count - 1))
  return Math.min(budgetMs, Math.max(0, index * step))
}

export function easeOutCubic(t: number): number {
  const x = Math.min(1, Math.max(0, Number.isFinite(t) ? t : 0))
  return 1 - Math.pow(1 - x, 3)
}

/** Value shown `t` (0..1) of the way through a count-up; exactly `target` once t >= 1. Works for negatives and decimals. */
export function countUpValue(target: number, t: number): number {
  if (!Number.isFinite(target)) return target
  if (!(t < 1)) return target
  return target * easeOutCubic(t)
}

/**
 * Story-chart entrance delay for item `index` of `count` (#1228, the reference's §4.3 rows): 60 ms apart, like vizjb12's
 * `idx * 60`, but squeezed so the last item starts within `budgetMs` and a long list still finishes in about a second.
 */
export function revealDelayMs(index: number, count: number, budgetMs = 540): number {
  return Math.round(rowDelayMs(index, count, 60, budgetMs))
}
