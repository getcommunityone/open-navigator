// The Data Center Story's "Over time" screen (#1348): pure helpers over GET /api/data-centers/sites-timeline. A site
// appears in the year of its earliest real date on record; sites with no date are a footnote, never placed at a guess.
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

/** The site's phase in `year`, or null before it appears. */
export function phaseInYear(site: TimelineSite, year: number): Phase | null {
  const appear = num(site.appear_year)
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
}

/** The sites on record by `year`, with their phase then. */
export function sitesInYear(sites: TimelineSite[], year: number): SiteInYear[] {
  const out: SiteInYear[] = []
  for (const site of sites) {
    const phase = phaseInYear(site, year)
    if (phase) out.push({ site, phase, isNew: num(site.appear_year) === year })
  }
  return out
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

/** The display the shared rule picks (#1289): 1–5 dated sites are a list, not an animation. */
export function timelineDisplay(res: SitesTimelineResponse | null | undefined): DisplayKind {
  // The categories are the phases in the latest year: one status only and under 20 sites is a list too (the shared rule).
  const last = res?.years?.[res.years.length - 1]
  const categories = last ? PHASES.map((p) => (last[p] as number | undefined) ?? 0) : []
  const d = pickDisplay({ items: res?.dated ?? 0, categories })
  return d.kind === 'empty' || d.kind === 'list' ? d.kind : 'units'
}

/** The screen's headline: the real totals at the first year, this year and, where Epoch projects one, the last year. */
export function timelineHeadline(res: SitesTimelineResponse | null | undefined, label: string): string {
  const where = label === 'National' ? 'across the country' : `in ${label}`
  const years = res?.years ?? []
  if (!res?.available) return 'Data center sites over time'
  if (years.length === 0) return `No dated data center sites on record ${where}`
  const first = years[0]!
  const now = yearRow(res, num(res.current_year) ?? 0) ?? years[years.length - 1]!
  const last = years[years.length - 1]!
  const grew = first.year === now.year ? `${cap(sites(now.total ?? 0))} on record ${where} by ${now.year}` : `From ${sites(first.total ?? 0)} on record ${where} in ${first.year} to ${fmt(now.total ?? 0)} by ${now.year}`
  const ahead = last.is_future && (last.operating ?? 0) > (now.operating ?? 0) ? `, ${fmt(last.operating ?? 0)} expected operating by ${last.year}` : ''
  return `${grew}${ahead}`
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

/** "60 sites have no date on record (47 operating, 6 proposed, …), so they aren't placed on the timeline." */
export function undatedNote(res: SitesTimelineResponse | null | undefined): string | null {
  const n = res?.undated ?? 0
  if (!n) return null
  const by = Object.entries(res?.undated_by_status ?? {})
    .filter(([, c]) => c > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([s, c]) => `${fmt(c)} ${(PHASE_LABEL[s as Phase] ?? s).toLowerCase()}`)
  return `${fmt(n)} ${n === 1 ? 'site has' : 'sites have'} no date on record${by.length > 1 ? ` (${by.join(', ')})` : ''}, so ${n === 1 ? "it isn't" : "they aren't"} placed on the timeline.`
}

/** "Announced in 2024" / "Work first on record in 2023 (Epoch AI)": how the site's year is known. */
export function appearText(site: TimelineSite): string {
  return site.appear_basis === 'announced' ? `Announced in ${site.appear_year}` : `Work first on record in ${site.appear_year} (Epoch AI)`
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
