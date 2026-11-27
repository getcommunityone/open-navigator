// The display fits the amount of data (#1289): one shared rule picks every story panel's display from its count, so no
// panel makes its own choice. Rules and reasons: web_docs/docs/development/story-display-fit.md.
//
//   0 items                                   → empty: "No recorded <items> yet", with what was searched
//   1–5 items                                 → list: a sentence and the items (name, status, date, link)
//   2–7 categories, total under 20            → sentence: the numbers in words, no percentages
//   2–7 categories, total 20 or more          → bars: sorted horizontal bars labelled with counts
//   8 or more categories                      → top-bars: the top 7 plus "Other"
//   time series                               → line only with 6 or more points
//   dot or unit chart                         → only for about 20–200 individual items (one category)

/** Most items listed one by one. */
export const LIST_MAX = 5
/** Most categories drawn as their own bar before the rest fold into "Other". */
export const CATEGORY_MAX = 7
/** The total from which categories are drawn as bars rather than stated in a sentence. */
export const BARS_MIN_TOTAL = 20
/** The fewest points a line is drawn for. */
export const LINE_MIN_POINTS = 6
/** The range of individual items a dot or unit chart is drawn for. */
export const UNITS_MIN = 20
export const UNITS_MAX = 200

export type DisplayKind = 'empty' | 'list' | 'sentence' | 'bars' | 'top-bars' | 'line' | 'units'

export interface DisplayInput {
  /** Individual records in scope (the whole-scope total when known). */
  items: number
  /** The count in each category the records fall into (zero categories are ignored). */
  categories?: number[]
  /** For a time series: how many points (periods) it has. */
  seriesPoints?: number
}

export interface Display {
  kind: DisplayKind
  /** Categories with records, for the rule that picked the display. */
  categories: number
  total: number
}

/** The display for a panel, from its counts alone. */
export function pickDisplay(input: DisplayInput): Display {
  const cats = (input.categories ?? []).filter((n) => n > 0)
  const total = Math.max(0, input.items || 0, cats.reduce((a, n) => a + n, 0))
  const out = (kind: DisplayKind): Display => ({ kind, categories: cats.length, total })
  if (total <= 0) return out('empty')
  if (input.seriesPoints != null) {
    if (input.seriesPoints >= LINE_MIN_POINTS) return out('line')
    return out(total <= LIST_MAX ? 'list' : 'sentence')
  }
  if (total <= LIST_MAX) return out('list')
  if (cats.length > CATEGORY_MAX) return out('top-bars')
  if (cats.length >= 2) return out(total < BARS_MIN_TOTAL ? 'sentence' : 'bars')
  // One category (or none given): individual items.
  if (total < UNITS_MIN) return out('list')
  if (total <= UNITS_MAX) return out('units')
  return out('sentence')
}

export interface CategoryCount {
  label: string
  count: number
  /** The folded "Other" row. */
  other?: boolean
}

/** Categories with records, largest first (ties by label); 8 or more fold into the top 7 plus "Other". */
export function topCategories(rows: CategoryCount[]): CategoryCount[] {
  const sorted = rows.filter((r) => r.count > 0).sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
  if (sorted.length <= CATEGORY_MAX) return sorted
  const rest = sorted.slice(CATEGORY_MAX).reduce((a, r) => a + r.count, 0)
  return [...sorted.slice(0, CATEGORY_MAX), { label: 'Other', count: rest, other: true }]
}

const fmt = (n: number) => n.toLocaleString('en-US')
const lowerFirst = (s: string) => (/^[A-Z][a-z]/.test(s) ? s.charAt(0).toLowerCase() + s.slice(1) : s)

/** "Debated: 8; without debate: 2.": the counts in words, larger first, no percentages. */
export function countsSentence(rows: CategoryCount[]): string {
  const top = topCategories(rows)
  if (top.length === 0) return ''
  const parts = top.map((r, i) => `${i === 0 ? r.label : lowerFirst(r.label)}: ${fmt(r.count)}`)
  return `${parts.join('; ')}.`
}

/** The categories and record count a story chart's spec holds, with the display the rule picks for them. */
export function specDisplay(spec: { groups: Array<{ label: string; total: number | null; shown: number }>; grandTotal: number | null }): {
  display: Display
  rows: CategoryCount[]
  items: number
} {
  const rows = spec.groups.map((g) => ({ label: g.label, count: g.total ?? g.shown }))
  const items = spec.grandTotal ?? rows.reduce((a, r) => a + r.count, 0)
  return { display: pickDisplay({ items, categories: rows.map((r) => r.count) }), rows, items }
}
