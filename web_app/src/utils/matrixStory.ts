/**
 * The story the Matrix map tells (issue #859): five chapters, and one pure function per section that turns the data the
 * section already computed into a headline and one supporting sentence.
 *
 * Copy rules, enforced by matrixStory.test.ts:
 *  - Only what the data in scope shows: rankings, counts, shares, changes, a correlation's direction and strength with its
 *    r². Never a cause, a forecast, a judgment ("should", "worrying", "good") or a claim about people.
 *  - Lower-is-better metrics still read "highest" / "lowest"; the copy never says "best" or "worst".
 *  - A figure that is missing is left out. With nothing to say, the headline names the chart and its scope and the lead is
 *    null; nothing is filled in.
 *  - Numbers come from the page's own formatters (passed in as `fmt`), so a sentence matches the chart it sits beside.
 *  - Years are plain strings.
 */
import type { SectionId } from '../components/matrix/types'

export type ChapterId = 'problem' | 'decision' | 'challenge' | 'implementation' | 'action'

export interface Chapter {
  id: ChapterId
  /** The public-meeting agenda item the chapter plays ("Call to order"). */
  meeting: string
  /** The plain title, and what the chapter is for. */
  title: string
  blurb: string
  /** Short label for the section band. */
  short: string
  sections: readonly SectionId[]
}

export const CHAPTERS: readonly Chapter[] = [
  { id: 'problem', meeting: 'Call to order', title: 'The problem', blurb: 'Where things stand', short: 'Problem', sections: ['tiles', 'dots', 'share'] },
  { id: 'decision', meeting: 'The motion', title: 'The decision', blurb: 'What changed and who sits above or below', short: 'Decision', sections: ['dumbbell', 'diverging', 'bars'] },
  { id: 'challenge', meeting: 'Public comment', title: 'The challenge', blurb: 'What complicates the picture', short: 'Challenge', sections: ['scatter', 'heatmap'] },
  { id: 'implementation', meeting: 'The vote and the work', title: 'Implementation', blurb: 'How it played out across the years', short: 'Implementation', sections: ['trend', 'columns', 'pivot'] },
  { id: 'action', meeting: 'New business', title: 'The call to action', blurb: 'What to do next', short: 'Action', sections: ['table'] },
]

/** The DOM id of a chapter card. */
export const chapterDomId = (id: ChapterId): string => `chapter-${id}`
export const isChapterId = (v: string | null | undefined): v is ChapterId => CHAPTERS.some((c) => c.id === v)
export const chapterById = (id: ChapterId): Chapter => CHAPTERS.find((c) => c.id === id)!
export const chapterOfSection = (s: SectionId): Chapter => CHAPTERS.find((c) => c.sections.includes(s)) ?? CHAPTERS[0]!
/** Section ids in reading order (chapter by chapter): the numbering 01 to 12. */
export const SECTION_ORDER: readonly SectionId[] = CHAPTERS.flatMap((c) => c.sections)

export interface Story {
  headline: string
  lead: string | null
}
export interface Item {
  name: string
  value: number | null
}
type Fmt = (v: number) => string

// ---------- helpers ----------

/** A label inside a sentence: lower-case, except words that are acronyms ("ACS", "SNAP"). */
export function lc(label: string): string {
  return label
    .split(' ')
    .map((w) => ((w.match(/[A-Z]/g)?.length ?? 0) >= 2 ? w : w.toLowerCase()))
    .join(' ')
}
const plural = (n: number, one: string, many: string): string => `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`
/** "A", "A and B", "A, B and C"; more than three become a count. */
export function nameList(names: string[]): string {
  if (names.length <= 1) return names[0] ?? ''
  if (names.length === 2) return `${names[0]} and ${names[1]}`
  if (names.length === 3) return `${names[0]}, ${names[1]} and ${names[2]}`
  return `${names.length} geographies`
}
const have = (names: string[], one: string, many: string): string => (names.length === 1 ? one : many)

export interface Extremes {
  n: number
  high: { names: string[]; value: number } | null
  low: { names: string[]; value: number } | null
  median: number | null
}
/** Highest, lowest and median over the items with a value; every item that shares the extreme value is named (ties). */
export function extremes(items: Item[]): Extremes {
  const xs = items.flatMap((i) => (i.value != null && Number.isFinite(i.value) ? [{ name: i.name, value: i.value }] : []))
  if (!xs.length) return { n: 0, high: null, low: null, median: null }
  const sorted = [...xs].sort((a, b) => a.value - b.value)
  const hi = sorted[sorted.length - 1]!.value
  const lo = sorted[0]!.value
  const names = (v: number) => xs.filter((x) => x.value === v).map((x) => x.name).sort((a, b) => a.localeCompare(b))
  const mid = Math.floor(sorted.length / 2)
  const median = sorted.length % 2 ? sorted[mid]!.value : (sorted[mid - 1]!.value + sorted[mid]!.value) / 2
  return { n: xs.length, high: { names: names(hi), value: hi }, low: { names: names(lo), value: lo }, median }
}

const neutral = (headline: string): Story => ({ headline, lead: null })

// ---------- Chapter 1: the problem ----------

export function tilesStory(i: { metricLabel: string; vintage: string; items: Item[]; fmt: Fmt; lowerIsBetter: boolean }): Story {
  const e = extremes(i.items)
  const m = lc(i.metricLabel)
  if (!e.n || !e.high || !e.low) return neutral(`${i.metricLabel}, ${i.vintage}: no tile values are available.`)
  if (e.n === 1) return neutral(`Only ${e.high.names[0]} has a value for ${m}, ${i.fmt(e.high.value)}.`)
  if (e.high.value === e.low.value) return neutral(`All ${e.n} geographies have the same ${m}, ${i.fmt(e.high.value)}.`)
  const headline =
    e.high.names.length === 1
      ? `${e.high.names[0]} sits highest on ${m}, at ${i.fmt(e.high.value)}.`
      : `${nameList(e.high.names)} share the highest ${m}, at ${i.fmt(e.high.value)}.`
  const dark = i.lowerIsBetter ? ' Darker boxes are lower values.' : ''
  const lead = `Lowest is ${nameList(e.low.names)} at ${i.fmt(e.low.value)}; the median is ${i.fmt(e.median!)} across ${plural(e.n, 'geography', 'geographies')}.${dark}`
  return { headline, lead }
}

export function dotsStory(i: { metricLabel: string; vintage: string; drillName: string | null; items: Item[]; fmt: Fmt }): Story {
  // Inside one state the county values live in the map component, not in the state bundle, so there is nothing to quote.
  if (i.drillName) return neutral(`${i.metricLabel} across ${i.drillName} counties, ${i.vintage}.`)
  const e = extremes(i.items)
  const m = lc(i.metricLabel)
  if (!e.n || !e.high || !e.low) return neutral(`${i.metricLabel} on the map of the United States, ${i.vintage}: no values are available.`)
  if (e.n === 1) return neutral(`Only ${e.high.names[0]} has a value for ${m} on the map, ${i.fmt(e.high.value)}.`)
  if (e.high.value === e.low.value) return neutral(`Every state on the map has the same ${m}, ${i.fmt(e.high.value)}.`)
  const headline =
    e.high.names.length === 1
      ? `On the map, ${e.high.names[0]} shows the highest ${m}, at ${i.fmt(e.high.value)}.`
      : `On the map, ${nameList(e.high.names)} share the highest ${m}, at ${i.fmt(e.high.value)}.`
  return { headline, lead: `${plural(e.n, 'state or territory has', 'states and territories have')} a value; the lowest is ${nameList(e.low.names)}, at ${i.fmt(e.low.value)}.` }
}

export interface ShareSegment {
  name: string
  value: number
  /** The whole-number share the chart prints for this segment. */
  pct: number
}
export function shareStory(i: {
  metricLabel: string
  vintage: string
  /** "the U.S. total (50 states + DC)" or "Alabama counties". */
  whole: string
  unit: 'states' | 'counties'
  /** Real parts only, as drawn (the "All others" group is not a part). */
  segments: ShareSegment[]
  /** Segments the reader has switched off with the legend. */
  hiddenCount: number
  partCount: number
}): Story {
  if (!i.segments.length) return neutral(`${i.metricLabel}, as a share of ${i.whole}, ${i.vintage}: no values are available.`)
  const top = Math.max(...i.segments.map((s) => s.value))
  const tops = i.segments.filter((s) => s.value === top)
  const names = tops.map((s) => s.name).sort((a, b) => a.localeCompare(b))
  const of = i.hiddenCount > 0 ? `the segments shown of ${i.whole}` : i.whole
  const headline =
    names.length === 1
      ? `${names[0]} holds the largest share of ${of}, ${tops[0]!.pct}%.`
      : `${nameList(names)} tie for the largest share of ${of}, ${tops[0]!.pct}% each.`
  const next = [...i.segments].filter((s) => s.value < top).sort((a, b) => b.value - a.value || a.name.localeCompare(b.name))[0]
  const lead = `${next ? `Next is ${next.name}, at ${next.pct}%; ` : ''}${i.unit === 'states' ? plural(i.partCount, 'geography', 'geographies') : plural(i.partCount, 'county', 'counties')} in all.`
  return { headline, lead }
}

// ---------- Chapter 2: the decision ----------

export interface Pair {
  name: string
  from: number | null
  to: number | null
}
export function compareStory(i: {
  metricLabel: string
  base: string | null
  vintage: string
  pairs: Pair[]
  fmt: Fmt
  /** The page's own change text between two readings, e.g. "+13 pp". */
  fmtChange: (from: number, to: number) => string
}): Story {
  if (!i.base || i.base === i.vintage) return neutral(`${i.metricLabel}, ${i.vintage}: there is no earlier vintage to compare with.`)
  const both = i.pairs.flatMap((p) => (p.from != null && p.to != null ? [{ name: p.name, from: p.from, to: p.to, d: p.to - p.from }] : []))
  if (!both.length) return neutral(`${i.metricLabel}, ${i.base} against ${i.vintage}: no geography has both values.`)
  const up = both.filter((p) => p.d > 0).length
  const down = both.filter((p) => p.d < 0).length
  const same = both.length - up - down
  const n = both.length
  const span = `between ${i.base} and ${i.vintage}`
  if (n === 1) {
    const p = both[0]!
    const verb = p.d === 0 ? `stayed at ${i.fmt(p.to)}` : `went from ${i.fmt(p.from)} in ${i.base} to ${i.fmt(p.to)} in ${i.vintage}`
    return neutral(`${p.name} ${verb}.`)
  }
  const headline =
    up === n ? `All ${n} geographies rose ${span}.` : down === n ? `All ${n} geographies fell ${span}.` : `${up} of ${n} geographies rose ${span}.`
  const big = Math.max(...both.map((p) => Math.abs(p.d)))
  const lead0 = both.find((p) => Math.abs(p.d) === big)!
  const movers = both.filter((p) => p.d === lead0.d) // the same move, in the same direction
  const change = i.fmtChange(lead0.from, lead0.to)
  const moveText =
    big === 0
      ? ''
      : movers.length === 1
        ? `the largest move is ${lead0.name} (${change}, from ${i.fmt(lead0.from)} to ${i.fmt(lead0.to)})`
        : movers.length <= 3
          ? `the largest move, ${change}, is shared by ${nameList(movers.map((p) => p.name).sort((a, b) => a.localeCompare(b)))}`
          : `the largest move, ${change}, is shared by ${movers.length} geographies`
  const parts = [down > 0 && down < n ? `${down} fell` : '', same > 0 && same < n ? `${same} did not change` : '', moveText].filter(Boolean)
  const lead = parts.length ? `${parts.join('; ').replace(/^./, (c) => c.toUpperCase())}.` : null
  return { headline, lead }
}

export function divergingStory(i: { metricLabel: string; vintage: string; items: Item[]; median: number | null; fmt: Fmt }): Story {
  const xs = i.items.flatMap((x) => (x.value != null ? [{ name: x.name, value: x.value }] : []))
  if (xs.length < 3 || i.median == null) return neutral(`${i.metricLabel} against the median, ${i.vintage}: too few geographies have a value to draw it.`)
  const above = xs.filter((x) => x.value > i.median!).length
  const below = xs.filter((x) => x.value < i.median!).length
  const equal = xs.length - above - below
  const far = Math.max(...xs.map((x) => Math.abs(x.value - i.median!)))
  const widest = xs.filter((x) => Math.abs(x.value - i.median!) === far).map((x) => x)
  const headline = `${above} of ${xs.length} geographies sit above the median of ${i.fmt(i.median)}.`
  const wide = far === 0 ? '' : `; the widest gap is ${nameList(widest.map((w) => w.name).sort((a, b) => a.localeCompare(b)))}, at ${i.fmt(widest[0]!.value)}`
  return { headline, lead: `${below} sit below it${equal > 0 ? ` and ${equal} equal it` : ''}${wide}.` }
}

export function barsStory(i: { metricLabel: string; vintage: string; scopeLabel: string; items: Item[]; fmt: Fmt }): Story {
  const e = extremes(i.items)
  const m = lc(i.metricLabel)
  if (!e.n || !e.high || !e.low) return neutral(`${i.metricLabel} by geography, ${i.scopeLabel}, ${i.vintage}: no bar values are available.`)
  if (e.n === 1) return neutral(`Only ${e.high.names[0]} has a value for ${m}, ${i.fmt(e.high.value)}.`)
  if (e.high.value === e.low.value) return neutral(`Across ${i.scopeLabel}, every geography with a value has the same ${m}, ${i.fmt(e.high.value)}.`)
  return {
    headline: `Across ${i.scopeLabel}, ${m} runs from ${i.fmt(e.low.value)} (${nameList(e.low.names)}) to ${i.fmt(e.high.value)} (${nameList(e.high.names)}).`,
    lead: `The median is ${i.fmt(e.median!)} across ${plural(e.n, 'geography', 'geographies')} in ${i.vintage}.`,
  }
}

// ---------- Chapter 3: the challenge ----------

export function scatterStory(i: {
  xLabel: string
  yLabel: string
  /** Geographies drawn (with both values) and in scope. */
  n: number
  total: number
  fit: { slope: number; r2: number } | null
}): Story {
  const y = lc(i.yLabel)
  const x = lc(i.xLabel)
  if (!i.fit || i.n < 3) return neutral(`${i.yLabel} against ${i.xLabel}: too few geographies have both values to fit a line.`)
  const r2 = i.fit.r2.toFixed(2)
  const strength = i.fit.r2 < 0.1 ? 'very weakly' : i.fit.r2 < 0.3 ? 'weakly' : i.fit.r2 < 0.6 ? 'moderately' : 'strongly'
  const tail = `r² is ${r2} across ${i.n} geographies`
  let headline: string
  if (i.fit.slope === 0 || r2 === '0.00') headline = `${i.yLabel} shows no straight-line relationship with ${x}; ${tail}.`
  else if (i.fit.slope > 0) headline = `${i.yLabel} rises with ${x}, ${strength}; ${tail}.`
  else headline = `${i.yLabel} falls as ${x} rises, ${strength}; ${tail}.`
  return {
    headline,
    lead: `r² is the share of the spread in ${y} that a straight line on ${x} accounts for; ${i.n} of ${i.total} geographies have both values.`,
  }
}

export function heatmapStory(i: {
  vintage: string
  metricCount: number
  geoCount: number
  /** For each metric, the geographies whose cell is the darkest (rank 1); an empty list when the metric has no values. */
  leaders: string[][]
}): Story {
  const measured = i.leaders.filter((l) => l.length > 0).length
  if (!measured) return neutral(`${plural(i.metricCount, 'metric', 'metrics')} across ${plural(i.geoCount, 'geography', 'geographies')}, ${i.vintage}: no cells have a value.`)
  const counts = new Map<string, number>()
  for (const l of i.leaders) for (const name of l) counts.set(name, (counts.get(name) ?? 0) + 1)
  const top = Math.max(...counts.values())
  const names = [...counts].filter(([, c]) => c === top).map(([n]) => n).sort((a, b) => a.localeCompare(b))
  const metrics = plural(measured, 'metric', 'metrics')
  const headline =
    top === 1 && measured > 1
      ? `No geography has the darkest cell on more than one of ${measured} metrics.`
      : `${nameList(names)} ${have(names, 'has', 'each have')} the darkest cell on ${top} of ${metrics}.`
  return {
    headline,
    lead: `${plural(i.metricCount, 'metric', 'metrics')} across ${plural(i.geoCount, 'geography', 'geographies')}, ${i.vintage}; each column is ranked on its own.`,
  }
}

// ---------- Chapter 4: implementation ----------

export function trendStory(i: {
  metricLabel: string
  vintages: string[]
  /** Median across all geographies at the first and last vintage. */
  median: { first: number | null; last: number | null }
  /** The geographies drawn, with their first and last readings. */
  geos: Array<{ name: string; first: number | null; last: number | null }>
  fmt: Fmt
}): Story {
  const first = i.vintages[0]
  const last = i.vintages[i.vintages.length - 1]
  if (!first) return neutral(`${i.metricLabel}: no vintages are published.`)
  if (i.vintages.length < 2 || !last) return neutral(`${i.metricLabel}, ${first}: only one vintage is published, so there is no trend to draw.`)
  const { first: a, last: b } = i.median
  if (a == null || b == null) return neutral(`${i.metricLabel}, ${first} to ${last}: the median is not available at both ends.`)
  const m = lc(i.metricLabel)
  const headline = a === b ? `The median ${m} stayed at ${i.fmt(a)} from ${first} to ${last}.` : `The median ${m} went from ${i.fmt(a)} in ${first} to ${i.fmt(b)} in ${last}.`
  const both = i.geos.filter((g) => g.first != null && g.last != null)
  if (!both.length) return neutral(headline)
  const up = both.filter((g) => g.last! > g.first!).length
  const down = both.filter((g) => g.last! < g.first!).length
  const same = both.length - up - down
  const drawn = both.length === 1 ? 'The geography drawn' : `Of the ${both.length} geographies drawn`
  const lead = both.length === 1 ? `${drawn} ${up ? 'rose' : down ? 'fell' : 'did not change'} over the same years.` : `${drawn}, ${up} rose, ${down} fell${same ? `, ${same} did not change` : ''} over the same years.`
  return { headline, lead }
}

export function columnsStory(i: {
  metricLabel: string
  isCount: boolean
  /** The vintage whose column is read (the last with values). */
  vintage: string | null
  /** The regions shown in that column, with their totals. */
  regions: Array<{ label: string; value: number | null }>
}): Story {
  if (!i.isCount) return neutral(`${i.metricLabel} is not a count, so it cannot be stacked by Census region.`)
  const xs = i.regions.flatMap((r) => (r.value != null && r.value >= 0 ? [{ label: r.label, value: r.value }] : []))
  const sum = xs.reduce((a, r) => a + r.value, 0)
  if (!i.vintage || !xs.length || sum <= 0) return neutral(`${i.metricLabel} by Census region: no values are available.`)
  const pct = (v: number) => `${((v / sum) * 100).toFixed(1)}%`
  const top = Math.max(...xs.map((r) => r.value))
  const tops = xs.filter((r) => r.value === top).map((r) => `The ${r.label}`)
  const headline = tops.length === 1 ? `${tops[0]} holds the largest share, ${pct(top)}.` : `${nameList(tops)} tie for the largest share, ${pct(top)} each.`
  const next = [...xs].filter((r) => r.value < top).sort((a, b) => b.value - a.value)[0]
  const lead = next ? `The ${next.label} is next, at ${pct(next.value)}, among the ${xs.length} regions shown in ${i.vintage}.` : null
  return { headline, lead }
}

export function pivotStory(i: {
  vintage: string
  colCount: number
  rowCount: number
  /** The column the rows are sorted by, as a metric label; null when sorted by name. */
  sortLabel: string | null
  sortDir: 'asc' | 'desc'
  items: Item[]
  fmt: Fmt
}): Story {
  const summary = `${plural(i.colCount, 'metric', 'metrics')} for ${plural(i.rowCount, 'geography', 'geographies')}, ${i.vintage}`
  if (!i.sortLabel) return neutral(`${summary[0]!.toUpperCase()}${summary.slice(1)}, sorted by name.`)
  const e = extremes(i.items)
  const end = i.sortDir === 'asc' ? e.low : e.high
  if (!e.n || !end) return neutral(`${summary[0]!.toUpperCase()}${summary.slice(1)}: ${lc(i.sortLabel)} has no values.`)
  const word = i.sortDir === 'asc' ? 'lowest' : 'highest'
  const who = nameList(end.names)
  const headline = end.names.length === 1 ? `${who} is ${word} of ${e.n} on ${lc(i.sortLabel)}, at ${i.fmt(end.value)}.` : `${who} share the ${word} ${lc(i.sortLabel)}, at ${i.fmt(end.value)}.`
  return { headline, lead: `${summary[0]!.toUpperCase()}${summary.slice(1)}; each column is shaded on its own scale.` }
}

// ---------- Chapter 5: the call to action ----------

export function tableStory(i: { vintage: string; base: string | null; total: number; shown: number; metricCount: number; query: string; withChange: number }): Story {
  if (i.total === 0) return neutral(`Table, ${i.vintage}: no rows are available.`)
  const q = i.query.trim()
  if (q && i.shown === 0) return neutral(`No geography matches “${q}”.`)
  const headline = q
    ? `${i.shown} of ${plural(i.total, 'geography', 'geographies')} match “${q}”.`
    : `${plural(i.total, 'geography', 'geographies')}, ${plural(i.metricCount, 'metric', 'metrics')}, ${i.vintage}.`
  const lead = i.base && i.base !== i.vintage ? `${i.withChange} of ${plural(i.shown, 'row has', 'rows have')} a change between ${i.base} and ${i.vintage}.` : null
  return { headline, lead }
}

// ---------- chapter cards ----------

export interface ChapterData {
  metricLabel: string
  vintage: string
  vintages: string[]
  /** "52 states and territories", or null when no geography has data. */
  geoNoun: string | null
  /** The second metric the scatter plots against, when there is one. */
  yLabel: string | null
  /** The single state in scope (dot-map drill or county share), or null for the whole country. */
  stateName: string | null
}

/** One sentence under each chapter title, from the metric, vintage and geographies in scope. */
export function chapterLead(id: ChapterId, d: ChapterData): string {
  const m = d.metricLabel
  switch (id) {
    case 'problem':
      return d.geoNoun ? `${m}, ${d.vintage} ACS 5-year: where things stand across ${d.geoNoun}.` : `${m}, ${d.vintage} ACS 5-year: no geography has data.`
    case 'decision': {
      const earlier = d.vintages.filter((v) => v < d.vintage)
      return earlier.length
        ? `What changed in ${lc(m)} between ${earlier[0]} and ${d.vintage}, and which geographies sit above or below the median.`
        : `Which geographies sit above or below the median ${lc(m)} in ${d.vintage}; no earlier vintage is published, so there is no change to show.`
    }
    case 'challenge':
      return `${m} set beside ${d.yLabel ? lc(d.yLabel) : 'the other published metrics'}, and beside every metric at once${d.geoNoun ? `, for ${d.geoNoun}` : ''}.`
    case 'implementation': {
      const first = d.vintages[0]
      const last = d.vintages[d.vintages.length - 1]
      if (!first || !last) return `${m}: no vintages are published.`
      return d.vintages.length < 2 ? `${m}: only ${first} is published, so there is no run of years to show.` : `${m} across ${d.vintages.length} vintages, ${first} to ${last}.`
    }
    case 'action':
      return `Scope: ${m}, ${d.vintage} ACS 5-year, ${d.stateName ?? 'all states and territories'}. Keep the table, or go to local government decisions.`
  }
}
