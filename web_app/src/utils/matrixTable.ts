/** Pure helpers for the Matrix map's data tables, CSV export and stacked columns (tested in matrixTable.test.ts). */

export interface CsvColumn {
  key: string
  label: string
}
export type CsvCell = string | number | null | undefined

/** One RFC 4180 field: quoted when it holds a comma, a double quote, CR or LF; embedded quotes are doubled. */
function csvField(v: CsvCell): string {
  if (v == null) return ''
  const s = typeof v === 'number' ? (Number.isFinite(v) ? String(v) : '') : v
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

/**
 * RFC 4180 CSV: a header row of the column labels, then one record per row, CRLF between records (no trailing CRLF).
 * A `null`/`undefined` (missing) value is an empty cell, never "0" or "—". Pass bare years as strings.
 */
export function toCsv(columns: CsvColumn[], rows: Array<Record<string, CsvCell>>): string {
  const head = columns.map((c) => csvField(c.label)).join(',')
  const body = rows.map((r) => columns.map((c) => csvField(r[c.key])).join(','))
  return [head, ...body].join('\r\n')
}

/** Case-insensitive "contains" over the named keys. A blank query keeps every row; null/undefined fields never match. */
export function filterRows<T>(rows: T[], query: string, keys: Array<keyof T>): T[] {
  const q = query.trim().toLowerCase()
  if (!q) return rows
  return rows.filter((r) =>
    keys.some((k) => {
      const v = r[k]
      return v != null && String(v).toLowerCase().includes(q)
    }),
  )
}

export interface VintageItems {
  vintage: string
  items: Array<{ region: string | null | undefined; value: number | null | undefined }>
}
export interface StackedVintage {
  vintage: string
  /** Sum of the values counted in each region; null when the region had no value at all (never 0). */
  byRegion: Record<string, number | null>
  /** How many values were counted in each region. */
  counts: Record<string, number>
  /** Sum over regions that have a value; null when none has. */
  total: number | null
}

/** Per-vintage totals per region. Missing and non-finite values are skipped, and a region with none is null, not zero. */
export function stackByRegion(data: VintageItems[], regionIds: string[]): StackedVintage[] {
  return data.map(({ vintage, items }) => {
    const sums: Record<string, number> = {}
    const counts: Record<string, number> = {}
    for (const id of regionIds) counts[id] = 0
    for (const it of items) {
      if (it.region == null || !regionIds.includes(it.region)) continue
      if (typeof it.value !== 'number' || !Number.isFinite(it.value)) continue
      sums[it.region] = (sums[it.region] ?? 0) + it.value
      counts[it.region] = (counts[it.region] ?? 0) + 1
    }
    const byRegion: Record<string, number | null> = {}
    let total: number | null = null
    for (const id of regionIds) {
      const s = counts[id]! > 0 ? sums[id]! : null
      byRegion[id] = s
      if (s != null) total = (total ?? 0) + s
    }
    return { vintage, byRegion, counts, total }
  })
}

/** Next set of hidden series after a legend click; a click that would hide the last visible series changes nothing. */
export function toggleSeries(off: ReadonlySet<string>, key: string, all: readonly string[]): Set<string> {
  const next = new Set([...off].filter((k) => all.includes(k)))
  if (next.has(key)) next.delete(key)
  else if (all.includes(key) && all.filter((k) => !next.has(k)).length > 1) next.add(key)
  return next
}

/** `?off=` value: "section:series,section:series". Unknown shapes are ignored. */
export function parseOff(raw: string | null, section: string): Set<string> {
  const out = new Set<string>()
  for (const part of (raw ?? '').split(',')) {
    const i = part.indexOf(':')
    if (i > 0 && part.slice(0, i) === section && part.length > i + 1) out.add(part.slice(i + 1))
  }
  return out
}

/** Rewrites `raw` so that the hidden series of `section` are exactly `off`; other sections are kept. Empty -> null. */
export function writeOff(raw: string | null, section: string, off: ReadonlySet<string>): string | null {
  const keep = (raw ?? '').split(',').filter((p) => p && !p.startsWith(`${section}:`))
  const next = [...keep, ...[...off].map((k) => `${section}:${k}`)]
  return next.length ? next.join(',') : null
}

const finite = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v)

/** Where `value` sits between `min` and `max`, 0..1, for the thin bar beside a number. Null for a missing value; 1 when min === max. */
export function barFraction(value: number | null | undefined, min: number, max: number): number | null {
  if (!finite(value) || !Number.isFinite(min) || !Number.isFinite(max)) return null
  if (min === max) return 1
  return Math.min(1, Math.max(0, (value - min) / (max - min)))
}

/**
 * Change between two readings in the metric's own unit: "+5.3 pp" for a percentage metric (`unit === 'pp'`), otherwise the
 * signed `format`ted magnitude. Null when either reading is missing: a change is never computed from a missing value.
 */
export function signedChange(
  latest: number | null | undefined,
  base: number | null | undefined,
  unit: 'pp' | 'number',
  format: (magnitude: number) => string = (a) => String(a),
): string | null {
  if (!finite(latest) || !finite(base)) return null
  const d = latest - base
  const sign = d > 0 ? '+' : d < 0 ? '−' : ''
  const a = Math.abs(d)
  return unit === 'pp' ? `${sign}${a.toFixed(a >= 10 ? 0 : 1)} pp` : `${sign}${format(a)}`
}

/** Good or bad for a change `d` (the Compare section's rule: rising is good unless lower is better for the metric). */
export function changeTone(d: number, lowerBetter: boolean): 'good' | 'bad' {
  return lowerBetter ? (d < 0 ? 'good' : 'bad') : d >= 0 ? 'good' : 'bad'
}

const SPARK_PAD = 3
/** The drawn position of every value (null for a missing one): evenly spaced across `width`, higher values higher up. */
export function sparklinePoints(values: Array<number | null>, width: number, height: number): Array<{ x: number; y: number } | null> {
  const xs = values.filter(finite)
  const lo = xs.length ? Math.min(...xs) : 0
  const hi = xs.length ? Math.max(...xs) : 0
  const n = values.length
  const x = (i: number) => (n < 2 ? width / 2 : SPARK_PAD + (i / (n - 1)) * (width - 2 * SPARK_PAD))
  const y = (v: number) => (hi === lo ? height / 2 : height - SPARK_PAD - ((v - lo) / (hi - lo)) * (height - 2 * SPARK_PAD))
  return values.map((v, i) => (finite(v) ? { x: x(i), y: y(v) } : null))
}
const r1 = (n: number) => String(Math.round(n * 10) / 10)

/**
 * SVG path for a sparkline over `values` (one per vintage). A missing value breaks the line: the next present value starts a
 * new `M` sub-path, so the line is never drawn across a gap. `last` is the point of the final present value.
 */
export function sparklinePath(values: Array<number | null>, width: number, height: number): { d: string; last: { x: number; y: number } | null } {
  const parts: string[] = []
  let pen = false
  let last: { x: number; y: number } | null = null
  for (const p of sparklinePoints(values, width, height)) {
    if (!p) {
      pen = false
      continue
    }
    parts.push(`${pen ? 'L' : 'M'}${r1(p.x)} ${r1(p.y)}`)
    pen = true
    last = p
  }
  return { d: parts.join(' '), last }
}

/** True when a value label fits inside its stacked-bar segment (13 px text) of `segWidth` px. */
export function fitsInside(segWidth: number, text: string): boolean {
  return segWidth >= text.length * 7.6 + 12
}
/** Rough width of an 11 px label, for placing share labels without measuring the DOM. */
export const labelWidth = (text: string): number => Math.ceil(text.length * 6.4) + 2

export interface LabelBox {
  /** Centre of the segment the label points at, in px. */
  cx: number
  /** Width of the label text, in px. */
  w: number
}
export interface LabelPlace {
  left: number
  /** 0 = the row nearest the bar; a label moves up a row when it, or its leader line, would collide. */
  row: number
}

/**
 * Places labels left to right in up to `maxRows` rows above a bar. A label takes the nearest row where neither it nor its
 * leader line (the vertical tick down to the segment centre) crosses a label or leader already placed. In each row it tries
 * centred on its segment, then ending at the segment, then starting at it, always keeping the leader under the text.
 * If no row keeps its leader clear it accepts a leader that crosses another label; if no row is free at all it goes in the top row.
 */
export function layoutLabels(boxes: LabelBox[], width: number, maxRows = 5, gap = 6): LabelPlace[] {
  const placed: Array<{ l: number; r: number; row: number; cx: number }> = []
  const clamp = (left: number, w: number) => Math.min(Math.max(0, left), Math.max(0, width - w))
  return boxes.map((b) => {
    const options = [b.cx - b.w / 2, b.cx + 4 - b.w, b.cx - 4].map((l) => clamp(l, b.w)).filter((l) => b.cx >= l && b.cx <= l + b.w)
    let pick: LabelPlace | null = null
    // First pass keeps leaders clear of other labels too; the second only keeps labels from overlapping each other.
    for (const strict of [true, false]) {
      for (let k = 0; k < maxRows && !pick; k++) {
        for (const left of options) {
          const right = left + b.w
          const clash = placed.some(
            (p) =>
              (p.row === k && left < p.r + gap && right > p.l - gap) ||
              (strict && p.row < k && b.cx >= p.l - 2 && b.cx <= p.r + 2) ||
              (strict && p.row > k && p.cx >= left - 2 && p.cx <= right + 2),
          )
          if (!clash) {
            pick = { left, row: k }
            break
          }
        }
      }
    }
    pick ??= { left: options[0] ?? clamp(b.cx - b.w / 2, b.w), row: maxRows - 1 }
    placed.push({ l: pick.left, r: pick.left + b.w, row: pick.row, cx: b.cx })
    return pick
  })
}
