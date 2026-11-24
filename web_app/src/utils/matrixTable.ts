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
