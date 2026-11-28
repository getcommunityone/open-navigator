// The Data Center Story's "Over time" screen (#1348, #1428): pure helpers over GET /api/data-centers/sites-timeline.
// Every site is drawn. A site appears in the year of its start date (appear_basis announced / epoch_first_report); a site
// with no start date appears in the year a source first listed it (listed_by: an upper bound, it may be older) and is drawn
// as "start date not on record"; a site with no date at all (none) appears only at today. Never a guessed year.
// `phaseInYear` mirrors the API's PHASE_SQL (api/routes/data_center_sites_timeline.py), so a year's dots and its totals agree:
//   an Epoch AI site with a dated timeline: planned before its first dated row, under construction from it, operating
//   from its first row with a building operational (a year after this one is Epoch's projection);
//   any other site: its status today (the registry publishes no history).
import type { SitesTimelineResponse, TimelineSite, TimelineYear } from '../api/sitesTimeline'
import { pickDisplay, type DisplayKind } from './displayFit'

export type Phase = 'planned' | 'under_construction' | 'operating' | 'cancelled' | 'no_longer_listed' | 'status_not_published'

/** The phases in drawing order (the strip stacks them bottom-up in this order). */
export const PHASES: Phase[] = ['operating', 'under_construction', 'planned', 'cancelled', 'no_longer_listed', 'status_not_published']

export const PHASE_LABEL: Record<Phase, string> = {
  operating: 'Operating',
  under_construction: 'Under construction',
  planned: 'Proposed',
  cancelled: 'Cancelled',
  no_longer_listed: 'No longer listed',
  status_not_published: 'Status not published',
}

const num = (y: string | null | undefined): number | null => {
  if (y == null) return null
  const n = Number.parseInt(y, 10)
  return Number.isFinite(n) ? n : null
}

/** No start date on record: placed by the year a source listed it (listed_by), or only at today (none). */
export const isUndated = (site: TimelineSite): boolean => site.appear_basis === 'listed_by' || site.appear_basis === 'none'

/** The year the site enters the map: its appear year; a site with no date at all enters at `today` (null without one). */
export function enterYear(site: TimelineSite, today?: number | null): number | null {
  const appear = num(site.appear_year)
  if (appear != null) return appear
  return site.appear_basis === 'none' && today != null && Number.isFinite(today) ? today : null
}

/** The site's phase in `year`, or null before it appears. `today` places the sites with no date at all. */
export function phaseInYear(site: TimelineSite, year: number, today?: number | null): Phase | null {
  const appear = enterYear(site, today)
  if (appear == null || year < appear) return null
  const first = num(site.first_report_year)
  const oper = num(site.operating_year)
  if (site.source === 'epoch' && first != null) {
    if (oper != null && year >= oper) return 'operating'
    return year >= first ? 'under_construction' : 'planned'
  }
  return (site.status as Phase | null | undefined) ?? 'status_not_published'
}

export interface SiteInYear {
  site: TimelineSite
  phase: Phase
  /** First shown this year. */
  isNew: boolean
  /** No start date on record (drawn as an outlined square, never as an opening). */
  undated: boolean
}

/** The sites on record by `year`, with their phase then. */
export function sitesInYear(sites: TimelineSite[], year: number, today?: number | null): SiteInYear[] {
  const out: SiteInYear[] = []
  for (const site of sites) {
    const phase = phaseInYear(site, year, today)
    if (phase) out.push({ site, phase, isNew: enterYear(site, today) === year, undated: isUndated(site) })
  }
  return out
}

const hasPoint = (s: TimelineSite) => s.latitude != null && s.longitude != null

export interface FrameLegend {
  /** Mapped sites in the frame by phase: these sum to `mapped`. */
  byPhase: Record<Phase, number>
  mapped: number
  /** Of `mapped`: drawn as "start date not on record". */
  undatedMapped: number
  /** Sites in the frame not drawn: no coordinates, or a point off the map (a territory outside the US map). */
  notMapped: number
}

/**
 * The legend for a frame: phase counts of the mapped sites (summing to all mapped sites), plus the not-mapped line.
 * `isPlaced` says whether the map can draw a site (defaults to "has coordinates").
 */
export function frameLegend(inYear: SiteInYear[], isPlaced: (s: TimelineSite) => boolean = hasPoint): FrameLegend {
  const byPhase = Object.fromEntries(PHASES.map((p) => [p, 0])) as Record<Phase, number>
  let mapped = 0
  let undatedMapped = 0
  let notMapped = 0
  for (const s of inYear) {
    if (!isPlaced(s.site)) {
      notMapped += 1
      continue
    }
    mapped += 1
    byPhase[s.phase] += 1
    if (s.undated) undatedMapped += 1
  }
  return { byPhase, mapped, undatedMapped, notMapped }
}

export interface StripColumn {
  year: number
  /** Sites with a start date, by phase that year. */
  dated: Record<Phase, number>
  /** Sites with no start date on record in the frame (the API's per-year `undated`). */
  undated: number
  total: number
  isFuture: boolean
}

/** The strip's columns: the API's SQL totals per year, split into start-dated sites by phase and the undated rest. */
export function stripColumns(res: SitesTimelineResponse | null | undefined): StripColumn[] {
  const today = num(res?.current_year)
  const dated = (res?.sites ?? []).filter((s) => !isUndated(s))
  return (res?.years ?? []).flatMap((y) => {
    const year = num(y.year)
    if (year == null) return []
    const byPhase = Object.fromEntries(PHASES.map((p) => [p, 0])) as Record<Phase, number>
    for (const s of sitesInYear(dated, year, today)) byPhase[s.phase] += 1
    return [{ year, dated: byPhase, undated: y.undated ?? 0, total: y.total ?? 0, isFuture: Boolean(y.is_future) }]
  })
}

/** The years the slider runs over, as numbers (the API sends 4-digit strings). */
export function timelineYears(res: SitesTimelineResponse | null | undefined): number[] {
  return (res?.years ?? []).map((y) => num(y.year)).filter((y): y is number => y != null)
}

export function yearRow(res: SitesTimelineResponse | null | undefined, year: number): TimelineYear | undefined {
  return res?.years?.find((y) => num(y.year) === year)
}

const fmt = (n: number) => n.toLocaleString('en-US')
const sites = (n: number) => `${fmt(n)} data center ${n === 1 ? 'site' : 'sites'}`

/** The display the shared rule picks (#1289): 1–5 sites are a list, not an animation. */
export function timelineDisplay(res: SitesTimelineResponse | null | undefined): DisplayKind {
  // The categories are the phases in the latest year: one status only and under 20 sites is a list too (the shared rule).
  const last = res?.years?.[res.years.length - 1]
  const categories = last ? PHASES.map((p) => (last[p] as number | undefined) ?? 0) : []
  const d = pickDisplay({ items: res?.total ?? 0, categories })
  return d.kind === 'empty' || d.kind === 'list' ? d.kind : 'units'
}

/**
 * The screen's headline (#1428): every site on record, then how many have a start date and how many are only listed.
 * "2,379 data center sites on record across the country: 728 with a known start date, 1,651 listed by 2026 with no
 * earlier date on record". It never says when an undated site began.
 */
export function timelineHeadline(res: SitesTimelineResponse | null | undefined, label: string): string {
  const where = label === 'National' ? 'across the country' : `in ${label}`
  if (!res?.available) return 'Data center sites over time'
  const total = res.total ?? 0
  if (total === 0) return `No data center sites on record ${where}`
  const dated = res.dated ?? 0
  const listed = (res.undated ?? 0) - (res.unplaced ?? 0)
  const parts = [`${fmt(dated)} with a known start date`]
  if (listed > 0) parts.push(`${fmt(listed)} listed by ${res.listed_year ?? res.current_year} with no earlier date on record`)
  if ((res.unplaced ?? 0) > 0) parts.push(`${fmt(res.unplaced ?? 0)} with no date on record`)
  if (dated === total) return `${cap(sites(total))} on record ${where}, all with a known start date`
  return `${cap(sites(total))} on record ${where}: ${parts.join(', ')}`
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

/**
 * The frame's caption for sites with no start date: "plus 1,651 sites with no start date on record (listed by 2026; they
 * may be older)" once they are on the map, and before then a line saying when they join, so no frame implies they didn't exist.
 */
export function undatedCaption(res: SitesTimelineResponse | null | undefined, year: number): string | null {
  const n = res?.undated ?? 0
  if (!n) return null
  const row = yearRow(res, year)
  const inFrame = row?.undated ?? 0
  const listedYear = res?.listed_year ?? res?.current_year
  if (inFrame > 0) {
    const s = inFrame === 1 ? 'site' : 'sites'
    return `Plus ${fmt(inFrame)} ${s} with no start date on record (squares): listed by ${listedYear}, ${inFrame === 1 ? 'it' : 'they'} may be older.`
  }
  return `${fmt(n)} more ${n === 1 ? 'site has' : 'sites have'} no start date on record and ${n === 1 ? 'joins' : 'join'} the map at ${listedYear}, the year ${n === 1 ? 'it was' : 'they were'} first listed; ${n === 1 ? 'it' : 'they'} may be older.`
}

/** "Announced in 2024" / "Work first on record in 2023 (Epoch AI)" / "Start date not on record; listed by Jul 16, 2026". */
export function appearText(site: TimelineSite): string {
  if (site.appear_basis === 'announced') return `Announced in ${site.appear_year}`
  if (site.appear_basis === 'epoch_first_report') return `Work first on record in ${site.appear_year} (Epoch AI)`
  if (site.appear_basis === 'listed_by') {
    const d = site.listed_on ? new Date(`${site.listed_on}T00:00:00Z`) : null
    const when = d && !Number.isNaN(d.getTime()) ? d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }) : site.appear_year
    return `Start date not on record; listed by ${when}`
  }
  return 'No date on record'
}

/** The capacity the source publishes, labelled, or null. */
export function capacityText(site: TimelineSite): string | null {
  const mw = (n: number) => `${n.toLocaleString('en-US', { maximumFractionDigits: 1 })} MW`
  const parts: string[] = []
  if (site.capacity_mw_operational != null) parts.push(`${mw(site.capacity_mw_operational)} operating`)
  if (site.capacity_mw_planned != null) parts.push(`${mw(site.capacity_mw_planned)} planned`)
  if (site.it_power_mw != null) parts.push(`${mw(site.it_power_mw)} IT power`)
  return parts.length ? parts.join(' · ') : null
}

/** The operating year, when Epoch dates one: "Operating since 2022" or "Expected operating 2028". */
export function operatingText(site: TimelineSite): string | null {
  if (!site.operating_year) return null
  return site.operating_is_expected ? `Expected operating ${site.operating_year} (Epoch AI projection)` : `Operating since ${site.operating_year}`
}
