/**
 * Pure helpers for the story's trend line, milestone track and period dumbbell (#1140).
 * Nothing here invents a value: a year with no data is a gap in the line, never a zero.
 */
import type { MilestoneKind, PeriodRow, TimelineMilestone, TimelineYear } from '../api/topicTimeline'

export type SeriesMode = 'meetings' | 'share'

/**
 * Fewest recorded meetings in a year for "none of them discussed the topic" to be drawn as a real 0. Below it (for
 * example 7 recorded Texas meetings in 2024) a year without topic meetings says nothing and is drawn as a gap.
 */
export const MIN_RECORDED_FOR_ZERO = 25

export interface SeriesPoint {
  year: number
  value: number
  src: TimelineYear
}

/** A year's value for the series, or null when the year is a gap. */
export function seriesValue(y: TimelineYear, mode: SeriesMode): number | null {
  if (mode === 'share') {
    if (y.share == null) return null
    if (y.meetings === 0 && (y.all_recorded_meetings ?? 0) < MIN_RECORDED_FOR_ZERO) return null
    return y.share * 100
  }
  if (y.meetings > 0) return y.meetings
  return (y.all_recorded_meetings ?? 0) >= MIN_RECORDED_FOR_ZERO ? 0 : null
}

/**
 * The line as runs of consecutive years. A run breaks at a missing year or a gap year, so the path never bridges a year
 * we know nothing about.
 */
export function buildSeries(years: TimelineYear[], mode: SeriesMode): SeriesPoint[][] {
  const sorted = years.filter((y) => Number.isFinite(Number(y.year))).sort((a, b) => Number(a.year) - Number(b.year))
  const runs: SeriesPoint[][] = []
  let run: SeriesPoint[] = []
  let prev: number | null = null
  for (const y of sorted) {
    const yr = Number(y.year)
    if (!Number.isFinite(yr)) continue
    const v = seriesValue(y, mode)
    if (v == null || (prev != null && yr !== prev + 1)) {
      if (run.length) runs.push(run)
      run = []
    }
    if (v != null) run.push({ year: yr, value: v, src: y })
    prev = yr
  }
  if (run.length) runs.push(run)
  return runs
}

/** Years that sit inside the drawn range but have no point: listed under the chart as gaps. */
export function gapYears(years: TimelineYear[], mode: SeriesMode): string[] {
  const runs = buildSeries(years, mode).flat()
  if (!runs.length) return []
  const have = new Set(runs.map((p) => p.year))
  const lo = Math.min(...have)
  const hi = Math.max(...have)
  const out: string[] = []
  for (let y = lo; y <= hi; y++) if (!have.has(y)) out.push(String(y))
  return out
}

/** "nice" upper bound for an axis. */
export function niceMax(v: number): number {
  if (!(v > 0)) return 1
  const p = 10 ** Math.floor(Math.log10(v))
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p
  return 10 * p
}

/** A date as a fractional year, for placing a milestone on the line's year axis (a year's point sits at its middle). */
export function dateToYearPos(iso: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return null
  const y = Number(m[1])
  const start = Date.UTC(y, 0, 1)
  const end = Date.UTC(y + 1, 0, 1)
  const t = Date.UTC(y, Number(m[2]) - 1, Number(m[3]))
  return y + (t - start) / (end - start)
}

/** Next selected marker for a key; null when the key doesn't move the selection. Clamped, not wrapped. */
export function stepMarker(index: number, key: string, count: number): number | null {
  if (count <= 0) return null
  if (key === 'Home') return 0
  if (key === 'End') return count - 1
  const d = key === 'ArrowRight' || key === 'ArrowDown' ? 1 : key === 'ArrowLeft' || key === 'ArrowUp' ? -1 : 0
  if (!d) return null
  return Math.min(count - 1, Math.max(0, index + d))
}

/** The marker selected first: the newest milestone (the list is oldest first). -1 when there are none. */
export function defaultMarker(ms: TimelineMilestone[]): number {
  return ms.length ? ms.length - 1 : -1
}

export const MILESTONE_ORDER: MilestoneKind[] = ['approved', 'denied', 'tabled', 'moratorium', 'bill_enacted']
export const MILESTONE_LABELS: Record<MilestoneKind, string> = {
  approved: 'Approved',
  denied: 'Denied',
  tabled: 'Tabled or deferred',
  moratorium: 'Moratorium',
  bill_enacted: 'State bill enacted',
}

/** The kinds present, in lane order: one lane per kind, never an empty lane. */
export function milestoneLanes(ms: TimelineMilestone[]): MilestoneKind[] {
  const have = new Set(ms.map((m) => m.kind))
  return MILESTONE_ORDER.filter((k) => have.has(k))
}

export type DumbbellSort = 'later' | 'change' | 'earlier'

/** Rows sorted for the dumbbell: by the later share, by change (largest rise first) or by the earlier share; label breaks ties. */
export function sortDumbbell(rows: PeriodRow[], by: DumbbellSort): PeriodRow[] {
  const v = (r: PeriodRow) => (by === 'later' ? r.later_share : by === 'earlier' ? r.earlier_share : r.later_share - r.earlier_share)
  return [...rows].sort((a, b) => v(b) - v(a) || a.label.localeCompare(b.label))
}

/** Change in percentage points, signed with a true minus: "+3.2 pp", "−1.0 pp". */
export function ppLabel(earlier: number, later: number): string {
  const d = Math.round((later - earlier) * 1000) / 10
  return `${d >= 0 ? '+' : '−'}${Math.abs(d).toFixed(1)} pp`
}

export const pctLabel = (share: number) => `${(Math.round(share * 1000) / 10).toFixed(1)}%`
