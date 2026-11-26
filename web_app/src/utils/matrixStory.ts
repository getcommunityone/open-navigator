/**
 * The story the Matrix map tells (issues #859, #883): five chapters, and one pure function per chapter and per section that
 * turns the data the page already computed into a sentence.
 *
 * Voice. The structure of the page is never shown: no "problem", "decision", "challenge", "implementation" or "call to
 * action". Each chapter's large title is the chapter's main finding, written so the five read as one story in order:
 * where things stand, what changed, what goes with it, over time, your move. Short sentences, contrast ("$102K in the
 * District of Columbia. $52K in Mississippi."), concrete gaps ("almost twice as much"), counts ("38 of 52 rose") and a
 * question as the lead-in to the next chart when that chart answers it.
 *
 * Rules, enforced by matrixStory.test.ts:
 *  - Only what the data in scope shows: rankings, counts, shares, changes, a correlation's direction and strength with its
 *    r². Never a cause, a forecast, a judgment ("should", "worrying", "good") or a claim about people.
 *  - Lower-is-better metrics still read "highest" / "lowest"; the copy never says "best" or "worst".
 *  - A ratio only when both values are positive and the smaller is not near zero; otherwise the difference.
 *  - Ties name every tied geography up to three, then "and N others"; the same names are used in every sentence of a section.
 *  - A figure that is missing is left out. With nothing to say, the sentence names the metric and its scope and nothing is
 *    filled in.
 *  - Numbers come from the page's own formatters (passed in as `fmt`), so a sentence matches the chart it sits beside.
 *  - Years are plain strings.
 */
import type { SectionId } from '../components/matrix/types'

export type ChapterId = 'problem' | 'decision' | 'challenge' | 'implementation' | 'action'

export interface Chapter {
  /** Stays as the `?chapter=` value in the URL and in the DOM id; never shown to the reader. */
  id: ChapterId
  /** Two or three plain words for the story bar and the small line above the chapter title. */
  bandLabel: string
  sections: readonly SectionId[]
}

export const CHAPTERS: readonly Chapter[] = [
  { id: 'problem', bandLabel: 'Where things stand', sections: ['tiles', 'dots', 'share'] },
  { id: 'decision', bandLabel: 'What changed', sections: ['dumbbell', 'diverging', 'bars'] },
  { id: 'challenge', bandLabel: 'What goes with it', sections: ['scatter', 'heatmap'] },
  { id: 'implementation', bandLabel: 'Over time', sections: ['trend', 'columns', 'pivot'] },
  { id: 'action', bandLabel: 'Go further', sections: ['table'] },
]

/** The DOM id of a chapter opener. */
export const chapterDomId = (id: ChapterId): string => `chapter-${id}`
export const isChapterId = (v: string | null | undefined): v is ChapterId => CHAPTERS.some((c) => c.id === v)
export const chapterById = (id: ChapterId): Chapter => CHAPTERS.find((c) => c.id === id)!
export const chapterOfSection = (s: SectionId): Chapter => CHAPTERS.find((c) => c.sections.includes(s)) ?? CHAPTERS[0]!
/** Section ids in reading order (chapter by chapter). */
export const SECTION_ORDER: readonly SectionId[] = CHAPTERS.flatMap((c) => c.sections)

// ---------- screens (what the reader pages through) ----------

export type ScreenSection = SectionId | 'action'
export interface Screen {
  /** The element to scroll to: the chapter opener for a chapter's first section, the section otherwise. */
  domId: string
  section: ScreenSection
  chapter: ChapterId
  /** The heading that takes focus when the reader pages here. */
  headingId: string
}
/** Thirteen screens in reading order: the twelve sections, then the closing action block. */
export const SCREENS: readonly Screen[] = [
  ...CHAPTERS.flatMap((c) =>
    c.sections.map(
      (section, i): Screen => ({
        domId: i === 0 ? chapterDomId(c.id) : section,
        section,
        chapter: c.id,
        headingId: i === 0 ? `${chapterDomId(c.id)}-h` : `${section}-h`,
      }),
    ),
  ),
  { domId: 'action', section: 'action', chapter: 'action', headingId: 'action-h' },
]

/** The screen a DOM id belongs to: a chapter opener, a section (a chapter's first section shares its opener's screen) or the action block. */
export function screenIndexOf(domId: string, screens: readonly Screen[] = SCREENS): number {
  return screens.findIndex((s) => s.domId === domId || s.section === domId)
}

export interface Adjacent {
  index: number
  prev: Screen | null
  next: Screen | null
}
/**
 * What comes before and after the screen `domId` names. Before the first screen (null or an unknown id) nothing comes
 * before and the first screen is next; the first screen has no previous and the last has no next.
 */
export function adjacentScreens(domId: string | null, screens: readonly Screen[] = SCREENS): Adjacent {
  const index = domId == null ? -1 : screenIndexOf(domId, screens)
  return { index, prev: index > 0 ? screens[index - 1]! : null, next: index + 1 < screens.length ? screens[index + 1]! : null }
}

export interface LabelInput {
  metricLabel: string
  /** The earliest vintage when it is earlier than the selected one, else null. */
  base: string | null
  /** The second metric the scatter plots against. */
  yLabel: string | null
  stateName: string | null
}
/** A short phrase that says what a screen is about; it names the screen in the Continue and Back controls and the band's ticks. */
export function screenLabel(section: ScreenSection, d: LabelInput): string {
  const m = lc(d.metricLabel)
  switch (section) {
    case 'tiles':
      return 'where things stand'
    case 'dots':
      return 'the same numbers on the map'
    case 'share':
      return `how ${m} is divided`
    case 'dumbbell':
      return d.base ? `what changed since ${d.base}` : 'how the geographies compare'
    case 'diverging':
      return 'who sits above and below the median'
    case 'bars':
      return 'every geography side by side'
    case 'scatter':
      return d.yLabel ? `what goes with ${lc(d.yLabel)}` : `what goes with ${m}`
    case 'heatmap':
      return 'every metric at once'
    case 'trend':
      return `${m} over the years`
    case 'columns':
      return 'the split by region'
    case 'pivot':
      return 'every metric in one grid'
    case 'table':
      return 'the full table'
    case 'action':
      return d.stateName ? `what ${d.stateName} decided` : 'where to take it from here'
  }
}

/** The small line above a section headline: what the screen is, in plain words (never a number). */
export const SECTION_EYEBROW: Record<SectionId, string> = {
  tiles: 'At a glance',
  dots: 'On the map',
  share: 'Shares of the whole',
  dumbbell: 'Then and now',
  diverging: 'Above and below the median',
  bars: 'Side by side',
  scatter: 'Two metrics together',
  heatmap: 'Every metric at once',
  trend: 'Year by year',
  columns: 'By region',
  pivot: 'One grid',
  table: 'The full table',
}

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
/** "A", "A and B", "A, B and C"; more than three read "A, B, C and N others". */
export function nameList(names: string[]): string {
  if (names.length <= 1) return names[0] ?? ''
  if (names.length === 2) return `${names[0]} and ${names[1]}`
  if (names.length === 3) return `${names[0]}, ${names[1]} and ${names[2]}`
  const rest = names.length - 3
  return `${names[0]}, ${names[1]}, ${names[2]} and ${rest} ${rest === 1 ? 'other' : 'others'}`
}
const have = (names: string[], one: string, many: string): string => (names.length === 1 ? one : many)
const cap = (s: string): string => (s ? s[0]!.toUpperCase() + s.slice(1) : s)
const byName = (a: string, b: string): number => a.localeCompare(b)

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
  const names = (v: number) => xs.filter((x) => x.value === v).map((x) => x.name).sort(byName)
  const mid = Math.floor(sorted.length / 2)
  const median = sorted.length % 2 ? sorted[mid]!.value : (sorted[mid - 1]!.value + sorted[mid]!.value) / 2
  return { n: xs.length, high: { names: names(hi), value: hi }, low: { names: names(lo), value: lo }, median }
}

/**
 * How far apart two positive readings are, in words: "almost twice as much", "twice as much", "6.4 times as much". Null unless
 * both are positive and the smaller is not near zero (under a twentieth of the larger) or the two are within 10% of each other:
 * the caller then states the difference instead.
 */
export function ratioPhrase(hi: number, lo: number): string | null {
  if (!(hi > lo) || !(lo > 0) || lo < hi * 0.05) return null
  const r = hi / lo
  if (r < 1.1) return null
  if (r >= 1.9 && r < 2) return 'almost twice as much'
  if (r >= 2 && r <= 2.1) return 'twice as much'
  return `${(Math.round(r * 10) / 10).toFixed(1).replace(/\.0$/, '')} times as much`
}

const neutral = (headline: string): Story => ({ headline, lead: null })

// ---------- Chapter titles: one finding per chapter, in story order ----------

export interface RegionRead {
  vintage: string
  /** Region totals as the Columns chart stacks them ("The South"). */
  shares: Array<{ label: string; value: number }>
}
export interface ChapterInput {
  metricLabel: string
  vintage: string
  /** Every vintage in the bundle, oldest first. */
  vintages: string[]
  fmt: Fmt
  /** The difference between two readings in the metric's unit ("19 pp", "$12K"), or null when it cannot be written. */
  fmtDiff: (hi: number, lo: number) => string | null
  /** The page's change text between two readings ("+13 pp"). */
  fmtChange: (from: number, to: number) => string
  /** The geographies in scope for the selected vintage. */
  items: Item[]
  /** The same geographies in the earliest vintage, when it is earlier than the selected one; else null. */
  baseItems: Item[] | null
  /** The earliest vintage's label when it is earlier than the selected one; else null. */
  base: string | null
  /** The one state in scope, or null for the whole country. */
  stateName: string | null
  yLabel: string | null
  fit: { slope: number; r2: number; n: number } | null
  /** Median across all geographies at the first and the last vintage. */
  medians: { first: number | null; last: number | null }
  /** Region totals at the first and last vintage for a count metric; null for any other metric. */
  regions: { first: RegionRead | null; last: RegionRead | null } | null
}

function titleStand(d: ChapterInput): string {
  const e = extremes(d.items)
  const m = lc(d.metricLabel)
  if (!e.n || !e.high || !e.low) return `${d.metricLabel}, ${d.vintage}: no values are available for this scope.`
  if (e.n === 1) return `Only ${e.high.names[0]} has a value for ${m}: ${d.fmt(e.high.value)}.`
  if (e.high.value === e.low.value) return `Every geography shows the same ${m}: ${d.fmt(e.high.value)}.`
  const ratio = ratioPhrase(e.high.value, e.low.value)
  const diff = d.fmtDiff(e.high.value, e.low.value)
  const gap = ratio ? ` That is ${ratio}.` : diff ? ` A gap of ${diff}.` : ''
  return `${d.metricLabel}: ${d.fmt(e.high.value)} in ${nameList(e.high.names)}. ${d.fmt(e.low.value)} in ${nameList(e.low.names)}.${gap}`
}

/** Who moved between two vintages, from items matched by name. */
export function movesOf(items: Item[], baseItems: Item[]): Array<{ name: string; from: number; to: number; d: number }> {
  const before = new Map(baseItems.map((i) => [i.name, i.value]))
  return items.flatMap((i) => {
    const from = before.get(i.name)
    return from != null && i.value != null ? [{ name: i.name, from, to: i.value, d: i.value - from }] : []
  })
}

function titleChanged(d: ChapterInput): string {
  const m = lc(d.metricLabel)
  if (d.base && d.base !== d.vintage && d.baseItems) {
    const both = movesOf(d.items, d.baseItems)
    if (!both.length) return `${d.metricLabel}: no geography has a value in both ${d.base} and ${d.vintage}.`
    const n = both.length
    if (n === 1) {
      const p = both[0]!
      return p.d === 0 ? `${p.name} stayed at ${d.fmt(p.to)} from ${d.base} to ${d.vintage}.` : `${p.name} went from ${d.fmt(p.from)} in ${d.base} to ${d.fmt(p.to)} in ${d.vintage}.`
    }
    const up = both.filter((p) => p.d > 0).length
    const down = both.filter((p) => p.d < 0).length
    const big = Math.max(...both.map((p) => Math.abs(p.d)))
    if (big === 0) return `Since ${d.base}, none of the ${n} geographies changed its ${m}.`
    const lead0 = both.find((p) => Math.abs(p.d) === big)!
    const counted = up === n ? `all ${n} rose` : down === n ? `all ${n} fell` : `${up} of ${n} rose${down ? ` and ${down} fell` : ''}`
    // The section below names who moved most; the title gives the size of the biggest move.
    return `Since ${d.base}, ${counted}. The biggest change was ${d.fmtChange(lead0.from, lead0.to)}.`
  }
  const earliest = d.vintages[0]
  if (earliest && earliest !== d.vintage && !d.baseItems) return `${d.metricLabel}: the ${earliest} file is not available, so there is nothing to compare with.`
  const e = extremes(d.items)
  const prefix = d.vintages.length < 2 ? `Only ${d.vintage} is loaded.` : `The earliest year loaded is ${d.vintage}.`
  if (e.n < 3 || e.median == null) return `${prefix} ${d.metricLabel}: too few geographies have a value to compare with the median.`
  const above = d.items.filter((i) => i.value != null && i.value > e.median!).length
  const below = d.items.filter((i) => i.value != null && i.value < e.median!).length
  return `${prefix} ${above} of ${e.n} geographies sit above the median of ${d.fmt(e.median)}, ${below} below.`
}

export const STRENGTH_WORD = (r2: number): string => (r2 < 0.1 ? 'Barely' : r2 < 0.3 ? 'Weakly' : r2 < 0.6 ? 'Moderately' : 'Strongly')

function titleGoesWith(d: ChapterInput): string {
  if (!d.yLabel) return `${d.metricLabel}: no second metric is published to set beside it.`
  const x = lc(d.metricLabel)
  const y = lc(d.yLabel)
  if (!d.fit || d.fit.n < 3) return `${d.metricLabel} beside ${y}: too few geographies have both values to say.`
  const r2 = d.fit.r2.toFixed(2)
  const q = `Do ${x} and ${y} move together?`
  if (d.fit.slope === 0 || r2 === '0.00') return `${q} Not in a straight line: r² is ${r2} across ${d.fit.n} geographies.`
  const way = d.fit.slope > 0 ? `higher ${x} goes with higher ${y}` : `higher ${x} goes with lower ${y}`
  return `${q} ${STRENGTH_WORD(d.fit.r2)}: ${way}, r² ${r2} across ${d.fit.n} geographies.`
}

function titleOverTime(d: ChapterInput): string {
  const m = lc(d.metricLabel)
  const first = d.vintages[0]
  const last = d.vintages[d.vintages.length - 1]
  if (!first || !last) return `${d.metricLabel}: no vintages are published.`
  if (d.vintages.length < 2) {
    const med = d.medians.last
    return med == null ? `${d.metricLabel}: only ${first} is loaded, so there is no run of years yet.` : `Only ${first} is loaded, so there is no run of years yet. The median ${m} is ${d.fmt(med)}.`
  }
  const rs = d.regions
  if (rs?.first && rs.last && rs.first.shares.length && rs.last.shares.length) {
    const lead = (r: RegionRead) => {
      const sum = r.shares.reduce((a, s) => a + s.value, 0)
      const top = Math.max(...r.shares.map((s) => s.value))
      if (!(sum > 0)) return null
      const names = r.shares.filter((s) => s.value === top).map((s) => s.label).sort(byName)
      return { names, pct: `${((top / sum) * 100).toFixed(1)}%`, vintage: r.vintage }
    }
    const a = lead(rs.first)
    const b = lead(rs.last)
    if (a && b) {
      if (a.names.join('|') === b.names.join('|')) return `${nameList(b.names)} held the largest share of ${m} in ${a.vintage} (${a.pct}) and in ${b.vintage} (${b.pct}).`
      return `${nameList(a.names)} held the largest share of ${m} in ${a.vintage} (${a.pct}). By ${b.vintage} it was ${nameList(b.names)} (${b.pct}).`
    }
  }
  const { first: a, last: b } = d.medians
  if (a == null || b == null) return `${d.metricLabel}, ${first} to ${last}: the median is not available at both ends.`
  return a === b ? `From ${first} to ${last}, the median ${m} held at ${d.fmt(a)}.` : `From ${first} to ${last}, the median ${m} went from ${d.fmt(a)} to ${d.fmt(b)}.`
}

function titleYourMove(d: ChapterInput): string {
  return d.stateName ? `See what ${d.stateName} decided.` : 'See the decisions behind these numbers.'
}

/** The large title of a chapter: its main finding, from the data in scope. */
export function chapterTitle(id: ChapterId, d: ChapterInput): string {
  switch (id) {
    case 'problem':
      return titleStand(d)
    case 'decision':
      return titleChanged(d)
    case 'challenge':
      return titleGoesWith(d)
    case 'implementation':
      return titleOverTime(d)
    case 'action':
      return titleYourMove(d)
  }
}

// ---------- Chapter 1: where things stand ----------

export function tilesStory(i: { metricLabel: string; vintage: string; items: Item[]; fmt: Fmt; lowerIsBetter: boolean }): Story {
  const e = extremes(i.items)
  const m = lc(i.metricLabel)
  if (!e.n || !e.high || !e.low) return neutral(`${i.metricLabel}, ${i.vintage}: no tile values are available.`)
  if (e.n === 1) return neutral(`Only ${e.high.names[0]} has a value for ${m}, ${i.fmt(e.high.value)}.`)
  if (e.high.value === e.low.value) return neutral(`All ${e.n} geographies have the same ${m}, ${i.fmt(e.high.value)}.`)
  const above = i.items.filter((x) => x.value != null && x.value > e.median!).length
  const headline = `The middle sits at ${i.fmt(e.median!)}, and ${above} of ${e.n} geographies are above it.`
  const dark = i.lowerIsBetter ? ' Darker boxes are lower values.' : ''
  const lead = `${cap(nameList(e.high.names))} ${have(e.high.names, 'is', 'are')} highest at ${i.fmt(e.high.value)}; ${nameList(e.low.names)} ${have(e.low.names, 'is', 'are')} lowest at ${i.fmt(e.low.value)}.${dark}`
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
  const headline = `Where on the map? ${cap(nameList(e.high.names))} ${have(e.high.names, 'is', 'are')} highest, at ${i.fmt(e.high.value)}.`
  return { headline, lead: `${cap(nameList(e.low.names))} ${have(e.low.names, 'is', 'are')} lowest, at ${i.fmt(e.low.value)}. ${plural(e.n, 'state or territory has', 'states and territories have')} a value.` }
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
  const names = tops.map((s) => s.name).sort(byName)
  const of = i.hiddenCount > 0 ? `the segments shown of ${i.whole}` : i.whole
  const headline =
    names.length === 1
      ? `${names[0]} holds the largest share of ${of}, ${tops[0]!.pct}%.`
      : `${nameList(names)} tie for the largest share of ${of}, ${tops[0]!.pct}% each.`
  const next = [...i.segments].filter((s) => s.value < top).sort((a, b) => b.value - a.value || a.name.localeCompare(b.name))[0]
  const lead = `${next ? `Next is ${next.name}, at ${next.pct}%; ` : ''}${i.unit === 'states' ? plural(i.partCount, 'geography', 'geographies') : plural(i.partCount, 'county', 'counties')} in all.`
  return { headline, lead }
}

// ---------- Chapter 2: what changed ----------

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
  if (!i.base || i.base === i.vintage) return neutral(`${i.metricLabel}, ${i.vintage}: there is no earlier year loaded to compare with.`)
  const both = i.pairs.flatMap((p) => (p.from != null && p.to != null ? [{ name: p.name, from: p.from, to: p.to, d: p.to - p.from }] : []))
  if (!both.length) return neutral(`${i.metricLabel}, ${i.base} against ${i.vintage}: no geography has both values.`)
  const up = both.filter((p) => p.d > 0).length
  const down = both.filter((p) => p.d < 0).length
  const same = both.length - up - down
  const n = both.length
  if (n === 1) {
    const p = both[0]!
    const verb = p.d === 0 ? `stayed at ${i.fmt(p.to)}` : `went from ${i.fmt(p.from)} in ${i.base} to ${i.fmt(p.to)} in ${i.vintage}`
    return neutral(`${p.name} ${verb}.`)
  }
  const big = Math.max(...both.map((p) => Math.abs(p.d)))
  const counted = up === n ? `all ${n} rose` : down === n ? `all ${n} fell` : `${up} of ${n} rose${down ? `, ${down} fell` : ''}${same ? `, ${same} did not change` : ''}`
  if (big === 0) return neutral(`Since ${i.base}, none of the ${n} geographies changed.`)
  const lead0 = both.find((p) => Math.abs(p.d) === big)!
  const movers = both.filter((p) => p.d === lead0.d) // the same move, in the same direction
  const change = i.fmtChange(lead0.from, lead0.to)
  const names = movers.map((p) => p.name).sort(byName)
  const headline =
    movers.length === 1
      ? `Which moved most? ${lead0.name}, ${change}, from ${i.fmt(lead0.from)} to ${i.fmt(lead0.to)}.`
      : `Which moved most? ${nameList(names)}, each by ${change}.`
  return { headline, lead: `Between ${i.base} and ${i.vintage}, ${counted}.` }
}

export function divergingStory(i: {
  metricLabel: string
  vintage: string
  items: Item[]
  median: number | null
  fmt: Fmt
  /** The difference between two readings in the metric's unit; null when it cannot be written. */
  fmtDiff?: (hi: number, lo: number) => string | null
}): Story {
  const xs = i.items.flatMap((x) => (x.value != null ? [{ name: x.name, value: x.value }] : []))
  if (xs.length < 3 || i.median == null) return neutral(`${i.metricLabel} against the median, ${i.vintage}: too few geographies have a value to draw it.`)
  const med = i.median
  const above = xs.filter((x) => x.value > med).length
  const below = xs.filter((x) => x.value < med).length
  const equal = xs.length - above - below
  const far = Math.max(...xs.map((x) => Math.abs(x.value - med)))
  const counts = `${above} of ${xs.length} sit above the median of ${i.fmt(med)} and ${below} below${equal > 0 ? `; ${equal} equal it` : ''}.`
  if (far === 0) return { headline: `Every geography sits at the median of ${i.fmt(med)}.`, lead: null }
  const upFar = Math.max(...xs.map((x) => x.value - med))
  const downFar = Math.max(...xs.map((x) => med - x.value))
  const upNames = upFar > 0 ? xs.filter((x) => x.value - med === upFar).map((x) => x.name).sort(byName) : []
  const downNames = downFar > 0 ? xs.filter((x) => med - x.value === downFar).map((x) => x.name).sort(byName) : []
  const dist = (hi: number, lo: number) => i.fmtDiff?.(hi, lo) ?? null
  const side = (names: string[], d: string | null, word: string, at: number, tail: string) =>
    names.length ? `${nameList(names)} ${have(names, 'is', 'are')} ${d ? `${d} ${word}${tail}` : `furthest ${word}, at ${i.fmt(at)}`}` : ''
  const upText = side(upNames, dist(med + upFar, med), 'above', med + upFar, ' the median')
  const downText = side(downNames, dist(med, med - downFar), 'below', med - downFar, '')
  const tied = upNames.length > 1 || downNames.length > 1
  if (tied && upNames.length && downNames.length && dist(med + upFar, med) && dist(med, med - downFar)) {
    return {
      headline: `Who sits furthest from the middle? The widest gaps are ${dist(med + upFar, med)} above the median and ${dist(med, med - downFar)} below.`,
      lead: `${cap(upText)}; ${downText}. ${counts}`,
    }
  }
  const far2 = [upText, downText].filter(Boolean).join(', ')
  return { headline: `Who sits furthest from the middle? ${far2}.`, lead: counts }
}

export function barsStory(i: { metricLabel: string; vintage: string; scopeLabel: string; items: Item[]; fmt: Fmt }): Story {
  const e = extremes(i.items)
  const m = lc(i.metricLabel)
  if (!e.n || !e.high || !e.low) return neutral(`${i.metricLabel} by geography, ${i.scopeLabel}, ${i.vintage}: no bar values are available.`)
  if (e.n === 1) return neutral(`Only ${e.high.names[0]} has a value for ${m}, ${i.fmt(e.high.value)}.`)
  if (e.high.value === e.low.value) return neutral(`Across ${i.scopeLabel}, every geography with a value has the same ${m}, ${i.fmt(e.high.value)}.`)
  const lo = i.fmt(e.low.value)
  const hi = i.fmt(e.high.value)
  const median = `Across ${i.scopeLabel} the median is ${i.fmt(e.median!)}, from ${plural(e.n, 'geography', 'geographies')} in ${i.vintage}.`
  // One geography at each end: name them in the headline. A tie moves the names to the line below so the headline stays short.
  if (e.low.names.length === 1 && e.high.names.length === 1) return { headline: `${cap(m)} runs from ${lo} in ${e.low.names[0]} to ${hi} in ${e.high.names[0]}.`, lead: median }
  return { headline: `${cap(m)} runs from ${lo} to ${hi}.`, lead: `${cap(nameList(e.low.names))} ${have(e.low.names, 'is', 'are')} lowest and ${nameList(e.high.names)} ${have(e.high.names, 'is', 'are')} highest. ${median}` }
}

// ---------- Chapter 3: what goes with it ----------

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
  const share = Math.round(i.fit.r2 * 100)
  let headline: string
  if (i.fit.slope === 0 || r2 === '0.00') headline = `${i.yLabel} and ${x} show no straight-line pattern; a line accounts for none of the spread.`
  else {
    const way = i.fit.slope > 0 ? `higher ${x} goes with higher ${y}` : `higher ${x} goes with lower ${y}`
    headline = `${cap(way)}; a straight line accounts for ${share}% of the spread.`
  }
  return { headline, lead: `r² is ${r2}; ${i.n} of ${i.total} geographies have both values.` }
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
  const names = [...counts].filter(([, c]) => c === top).map(([n]) => n).sort(byName)
  const metrics = plural(measured, 'metric', 'metrics')
  const headline =
    top === 1 && measured > 1
      ? `No geography has the darkest cell on more than one of ${measured} metrics.`
      : `Who stands out? ${nameList(names)} ${have(names, 'has', 'each have')} the darkest cell on ${top} of ${metrics}.`
  return {
    headline,
    lead: `${plural(i.metricCount, 'metric', 'metrics')} across ${plural(i.geoCount, 'geography', 'geographies')}, ${i.vintage}; each column is ranked on its own.`,
  }
}

// ---------- Chapter 4: over time ----------

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
  if (i.vintages.length < 2 || !last) return neutral(`${i.metricLabel}, ${first}: this is the only year loaded, so there is no trend to draw yet.`)
  const { first: a, last: b } = i.median
  if (a == null || b == null) return neutral(`${i.metricLabel}, ${first} to ${last}: the median is not available at both ends.`)
  const m = lc(i.metricLabel)
  const medianText = a === b ? `The median ${m} held at ${i.fmt(a)} from ${first} to ${last}.` : `The median ${m} went from ${i.fmt(a)} in ${first} to ${i.fmt(b)} in ${last}.`
  const both = i.geos.filter((g) => g.first != null && g.last != null)
  if (!both.length) return neutral(medianText)
  const up = both.filter((g) => g.last! > g.first!).length
  const down = both.filter((g) => g.last! < g.first!).length
  const same = both.length - up - down
  const headline =
    both.length === 1
      ? `The geography drawn ${up ? 'rose' : down ? 'fell' : 'did not change'} from ${first} to ${last}.`
      : `Of the ${both.length} geographies drawn, ${up} rose, ${down} fell${same ? ` and ${same} did not change` : ''} from ${first} to ${last}.`
  return { headline, lead: medianText }
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
  if (!i.sortLabel) return neutral(`${cap(summary)}, sorted by name.`)
  const e = extremes(i.items)
  const end = i.sortDir === 'asc' ? e.low : e.high
  if (!e.n || !end) return neutral(`${cap(summary)}: ${lc(i.sortLabel)} has no values.`)
  const word = i.sortDir === 'asc' ? 'lowest' : 'highest'
  const who = nameList(end.names)
  const headline = end.names.length === 1 ? `${who} is ${word} of ${e.n} on ${lc(i.sortLabel)}, at ${i.fmt(end.value)}.` : `${who} share the ${word} ${lc(i.sortLabel)}, at ${i.fmt(end.value)}.`
  return { headline, lead: `${cap(summary)}; each column is shaded on its own scale.` }
}

// ---------- Chapter 5: your move ----------

export function tableStory(i: { vintage: string; base: string | null; total: number; shown: number; metricCount: number; query: string; withChange: number }): Story {
  if (i.total === 0) return neutral(`Table, ${i.vintage}: no rows are available.`)
  const q = i.query.trim()
  if (q && i.shown === 0) return neutral(`No geography matches “${q}”.`)
  const headline = q
    ? `Matching “${q}”: ${i.shown} of ${plural(i.total, 'geography', 'geographies')}.`
    : `Every number, in one table: ${plural(i.total, 'geography', 'geographies')} and ${plural(i.metricCount, 'metric', 'metrics')}, ${i.vintage}.`
  const lead = i.base && i.base !== i.vintage ? `${i.withChange} of ${plural(i.shown, 'row has', 'rows have')} a change between ${i.base} and ${i.vintage}.` : null
  return { headline, lead }
}
