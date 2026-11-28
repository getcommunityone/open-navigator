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

/**
 * Thin recording coverage (#1207). A year is thin when its recorded meetings are below THIN_RATIO of BOTH
 *   - the median of its neighbours' recorded meetings (up to THIN_WINDOW years on each side), so it is a dip, not a
 *     step on the ramp (2009–2011 nationally sit far below the scope's typical year but in line with their neighbours);
 *   - the median of every recorded year in the scope, so a ramp's step is not called a hole (Georgia 2024: 115
 *     recorded against 794 in 2025, but 2023 had 92 and the state's typical year is ~190).
 * It must also be a dip (some year on each side recorded more), so the first and last years never are, and flagged
 * years are left out of their neighbours' medians, so every year of a long hole is caught, not only its ends.
 * Ratios, not counts, so the same rule works for 16,873 meetings nationally and a dozen in a town. Nationally only 2024
 * qualifies (932 recorded against ~13,000 around it and a median of ~5,200).
 */
export const THIN_RATIO = 0.25
export const THIN_WINDOW = 2

function median(xs: number[]): number | null {
  if (!xs.length) return null
  const s = [...xs].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m]! : (s[m - 1]! + s[m]!) / 2
}

/** Years (as numbers) whose recorded meetings are thin under the rule above. Needs at least three recorded years. */
export function thinYears(years: TimelineYear[]): Set<number> {
  const rec = years
    .map((y) => ({ year: Number(y.year), n: y.all_recorded_meetings }))
    .filter((r): r is { year: number; n: number } => Number.isFinite(r.year) && r.n != null && r.n > 0)
    .sort((a, b) => a.year - b.year)
  const out = new Set<number>()
  const scopeMed = median(rec.map((r) => r.n))
  if (scopeMed == null || rec.length < 3) return out
  // Repeat with flagged years left out of the neighbours, so every year of a long hole is caught, not only its ends.
  // A year must be a dip: a neighbour on each side recorded more (so the start of a ramp and the last year never are).
  /** Unflagged years on one side: those within the window (or else the nearest one), and the most any of them recorded. */
  const side = (i: number, dir: -1 | 1): { near: number[]; most: number } => {
    const near: number[] = []
    let nearest: number | null = null
    let most = 0
    for (let j = i + dir; j >= 0 && j < rec.length; j += dir) {
      const o = rec[j]!
      if (out.has(o.year)) continue
      most = Math.max(most, o.n)
      if (Math.abs(o.year - rec[i]!.year) <= THIN_WINDOW) near.push(o.n)
      else if (nearest == null) nearest = o.n
    }
    return { near: near.length ? near : nearest != null ? [nearest] : [], most }
  }
  for (let grew = true; grew; ) {
    grew = false
    rec.forEach((r, i) => {
      if (out.has(r.year)) return
      const left = side(i, -1)
      const right = side(i, 1)
      if (left.most <= r.n || right.most <= r.n) return
      const localMed = median([...left.near, ...right.near])!
      if (r.n < THIN_RATIO * localMed && r.n < THIN_RATIO * scopeMed) {
        out.add(r.year)
        grew = true
      }
    })
  }
  return out
}

/**
 * The series the chart opens on: the share when it can be drawn and a year on the count line is thin (its count would
 * read as a real drop), otherwise the count. Not when a thin year's share rests on fewer than MIN_RECORDED_FOR_ZERO
 * recorded meetings: that share would be a spike of its own (1 of 2 meetings = 50%), so the count line stays.
 */
export function defaultSeriesMode(years: TimelineYear[], coverageAvailable: boolean): SeriesMode {
  if (!coverageAvailable || !years.some((y) => y.share != null)) return 'meetings'
  const drawn = new Set(buildSeries(years, 'meetings').flat().map((p) => p.year))
  const thin = years.filter((y) => drawn.has(Number(y.year)) && thinYears(years).has(Number(y.year)))
  if (!thin.length) return 'meetings'
  return thin.every((y) => y.share != null && (y.all_recorded_meetings ?? 0) >= MIN_RECORDED_FOR_ZERO) ? 'share' : 'meetings'
}

/** A run cut into pieces for drawing: a piece touching a thin year is dashed (count mode only), the rest solid. */
export function splitRun(run: SeriesPoint[], thin: Set<number>): { dashed: boolean; points: SeriesPoint[] }[] {
  const out: { dashed: boolean; points: SeriesPoint[] }[] = []
  for (let i = 1; i < run.length; i++) {
    const a = run[i - 1]!
    const b = run[i]!
    const dashed = thin.has(a.year) || thin.has(b.year)
    const piece = out[out.length - 1]
    if (piece && piece.dashed === dashed) piece.points.push(b)
    else out.push({ dashed, points: [a, b] })
  }
  return out
}

/** A hollow marker: a thin year in count mode; in share mode, a share over fewer than MIN_RECORDED_FOR_ZERO meetings. */
export function isHollow(p: SeriesPoint, mode: SeriesMode, thin: Set<number>): boolean {
  if (mode === 'meetings') return thin.has(p.year)
  return (p.src.all_recorded_meetings ?? 0) < MIN_RECORDED_FOR_ZERO
}

/** "Only 932 meetings were recorded in 2024, so that year's count is not comparable." Null when no year is thin. */
export function thinNote(years: TimelineYear[], thin: Set<number>): string | null {
  const ys = years
    .filter((y) => thin.has(Number(y.year)) && y.all_recorded_meetings != null)
    .sort((a, b) => Number(a.year) - Number(b.year))
  if (!ys.length) return null
  const parts = ys.map((y, i) => `${y.all_recorded_meetings!.toLocaleString('en-US')}${i === 0 ? ' meetings were recorded' : ''} in ${y.year}`)
  const list = parts.length === 1 ? parts[0] : `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`
  return `Only ${list}, so ${ys.length === 1 ? "that year's count is" : "those years' counts are"} not comparable.`
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

/** The plot's side padding: room on the right for the end value and the milestone lane names ("Moratorium · 51"). */
export function timelinePads(w: number, hasMilestones: boolean): { padL: number; padR: number } {
  return { padL: 44, padR: hasMilestones ? (w < 420 ? 84 : 112) : w < 420 ? 64 : 58 }
}

/** Most boxes in one stacked year column (#1406): keeps the whole chart a few hundred marks at most. */
export const MAX_BOX_ROWS = 12

/**
 * What one box stands for: the smallest of 1, 2, 5, 10, 20, 50... that keeps the tallest column within `maxRows` boxes.
 * Counts of 12 or fewer stay 1 box = 1, so a small chart is every record.
 */
export function boxUnit(max: number, maxRows = MAX_BOX_ROWS): number {
  if (!(max > 0)) return 1
  for (let p = 1; ; p *= 10) {
    for (const m of [1, 2, 5]) {
      const u = m * p
      if (Math.ceil(max / u) <= maxRows) return u
    }
  }
}

export interface ColumnBox {
  /** 0 is the bottom box. */
  index: number
  /** Portion of a full box this one fills (1 except for a partial top box), so the stack's height is the value exactly. */
  fill: number
}

/** The boxes of one column: whole boxes of `unit` and a proportional partial box on top. Sums back to `value / unit`. */
export function columnBoxes(value: number, unit: number): ColumnBox[] {
  if (!(value > 0) || !(unit > 0)) return []
  const whole = Math.floor(value / unit + 1e-9)
  const out: ColumnBox[] = []
  for (let i = 0; i < whole; i++) out.push({ index: i, fill: 1 })
  const rest = value / unit - whole
  if (rest > 1e-6) out.push({ index: whole, fill: rest })
  return out
}

/** The year with the largest value, as a real sentence from the full yearly counts; null when tied or only one year. */
export function peakStatement(years: TimelineYear[], subject: string): string | null {
  const dated = years.filter((y) => Number.isFinite(Number(y.year)) && y.meetings > 0)
  if (dated.length < 2) return null
  const sorted = [...dated].sort((a, b) => b.meetings - a.meetings)
  if (sorted[0]!.meetings === sorted[1]!.meetings) return null
  const top = sorted[0]!
  const total = dated.reduce((a, y) => a + y.meetings, 0)
  const pct = Math.round((top.meetings / total) * 1000) / 10
  return `${top.year} has the most: ${top.meetings.toLocaleString('en-US')} ${top.meetings === 1 ? 'meeting' : 'meetings'} that discussed ${subject}, ${pct}% of all ${total.toLocaleString('en-US')}.`
}
