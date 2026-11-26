// Pure display helpers for the data-center "Jobs promised" panel (#246).
// Kept free of React so they can be unit-tested.
import { expandStateName } from '../utils/formatters'

/**
 * Headcount label for a claim. Unknown is "Not stated" — never 0.
 *   (120, 120) -> "120 jobs"; (100, 150) -> "100–150 jobs"; (null, null) -> "Not stated"
 */
export function formatHeadcount(low: number | null | undefined, high: number | null | undefined): string {
  const fmt = (n: number) => `${n.toLocaleString('en-US')}`
  const lo = low ?? null
  const hi = high ?? null
  if (lo == null && hi == null) return 'Not stated'
  if (lo != null && hi != null && lo !== hi) {
    const [a, b] = lo <= hi ? [lo, hi] : [hi, lo]
    return `${fmt(a)}–${fmt(b)} jobs`
  }
  const word = (n: number) => (n === 1 ? 'job' : 'jobs')
  // One bound only: say which, so "up to 300" never reads as a promise of 300.
  if (lo == null && hi != null) return `Up to ${fmt(hi)} ${word(hi)}`
  if (lo != null && hi == null) return `At least ${fmt(lo)} ${word(lo)}`
  const n = lo as number
  return `${fmt(n)} ${word(n)}`
}

/** Format an ISO date (YYYY-MM-DD…) without timezone shifting. */
export function formatIsoDate(value: string | null | undefined): string | null {
  if (!value) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value.trim())
  if (!m) return value.trim() || null
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' })
}

/** Date range label, or "Dates not stated" when both ends are unknown. */
export function formatDateRange(startsOn: string | null | undefined, endsOn: string | null | undefined): string {
  const s = formatIsoDate(startsOn)
  const e = formatIsoDate(endsOn)
  if (s && e) return s === e ? s : `${s} – ${e}`
  if (s) return `From ${s}`
  if (e) return `Until ${e}`
  return 'Dates not stated'
}

/** YouTube deep link at the claim's moment, or null if either part is missing. */
export function hearItUrl(videoId: string | null | undefined, startSeconds: number | null | undefined): string | null {
  if (!videoId || startSeconds == null || !Number.isFinite(startSeconds) || startSeconds < 0) return null
  return `https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}&t=${Math.floor(startSeconds)}s`
}

/**
 * Which meeting a claim was made at (DC-1.2, #247): the governing body when the
 * record names it, else a plain "Meeting record" — never a guessed body.
 */
export function meetingAttribution(bodyName: string | null | undefined): string {
  const body = bodyName?.trim()
  return body ? `At the ${body} meeting` : 'Meeting record'
}

export type ScopeLevel = 'national' | 'state' | 'city'

export interface PlaceScope {
  level: ScopeLevel
  /** Human label for the applied filter: "National", "Alabama", "Tuscaloosa". */
  label: string
}

/**
 * Scope from the applied URL filter. City wins over state; a city without a
 * state is still a city filter (the API receives it as-is).
 */
export function placeScope(state: string | undefined, city: string | undefined): PlaceScope {
  if (city) return { level: 'city', label: city }
  if (state) return { level: 'state', label: expandStateName(state) || state }
  return { level: 'national', label: 'National' }
}

/** Title with scope qualifier, e.g. "Data centers · Tuscaloosa". */
export function dataCentersTitle(scope: PlaceScope): string {
  return `Data centers · ${scope.label}`
}

/**
 * When an application link was last confirmed working (DC-1.3, #248).
 * Fresh: "Verified Nov 15, 2026". Stale: says so, with the last date when there is one.
 */
export function verifiedLabel(lastVerifiedAt: string | null | undefined, isStale: boolean): string {
  const when = formatIsoDate(lastVerifiedAt)
  if (!isStale && when) return `Verified ${when}`
  if (when) return `Not verified in the last 30 days (last verified ${when})`
  return 'Not verified yet'
}

/**
 * Plain words for a site's status (DC-4.1, #249). A site the source stopped listing
 * keeps its last known status and last-seen date rather than disappearing.
 */
export function siteStatusLabel(
  status: string | null | undefined,
  lastKnownStatus: string | null | undefined,
  lastSeenOn: string | null | undefined,
): string {
  const words: Record<string, string> = {
    planned: 'Planned',
    under_construction: 'Under construction',
    operating: 'Operating',
    cancelled: 'Cancelled (per the source)',
  }
  if (status === 'no_longer_listed') {
    const seen = formatIsoDate(lastSeenOn)
    const last = lastKnownStatus ? words[lastKnownStatus] : null
    return [
      'No longer listed by the source',
      seen ? `last seen ${seen}` : null,
      last ? `last known: ${last.toLowerCase()}` : null,
    ]
      .filter(Boolean)
      .join(' · ')
  }
  return (status && words[status]) || 'Status not published'
}

const CONCERN_WORDS: Record<string, string> = {
  water: 'water',
  electricity: 'electricity costs',
  noise: 'noise',
  land: 'land and property',
  taxes: 'tax breaks',
  traffic: 'traffic',
  pollution: 'pollution',
}

/** Plain words for a concern key (DC-4.3, #251). */
export function concernLabel(concern: string): string {
  return CONCERN_WORDS[concern] ?? concern
}

/**
 * One line on what an area objects to, from real counts:
 * "water in 3 of 4 objections (75%)". Null when there's nothing to say.
 */
export function concernSummary(
  c: { concern: string; mention_count: number; objection_count: number } | null | undefined,
): string | null {
  if (!c || c.objection_count <= 0) return null
  const pct = Math.round((100 * c.mention_count) / c.objection_count)
  return `${concernLabel(c.concern)} in ${c.mention_count} of ${c.objection_count} objections (${pct}%)`
}

// --- company-hosted meetings and project timelines (#532) --------------------------------

const COMMUNITY_EVENT_KIND: Record<string, string> = {
  town_hall: 'Town hall',
  community_meeting: 'Community meeting',
  open_house: 'Open house',
  information_session: 'Information session',
  public_meeting: 'Public meeting',
}

/** "Town hall", "Open house", ... for a community event kind. */
export function communityEventKindLabel(kind: string): string {
  return COMMUNITY_EVENT_KIND[kind] ?? 'Meeting'
}

const TIMELINE_STAGE: Record<string, string> = {
  announced: 'Announced',
  company_meeting: 'Company meeting',
  planning: 'Planning',
  vote: 'Council vote',
  government_meeting: 'Government meeting',
}

export function timelineStageLabel(stage: string): string {
  return TIMELINE_STAGE[stage] ?? stage
}

/** A sourced figure as the reader sees it: "$3.2 billion investment", "210 MW IT load". */
export function figureLabel(metric: string, value: number, unit: string): string {
  if (unit === 'usd') {
    const billions = value / 1e9
    const money = billions >= 1 ? `$${+billions.toFixed(2)} billion` : `$${+(value / 1e6).toFixed(1)} million`
    return `${money} investment`
  }
  const n = value.toLocaleString('en-US')
  switch (metric) {
    case 'it_mw':
      return `${n} MW IT load`
    case 'utility_mw':
      return `${n} MW utility power`
    case 'acres':
      return `${n} acres`
    case 'square_feet':
      return `${n} sq ft`
    case 'jobs':
      return `${n} jobs`
    default:
      return `${n} ${unit}`
  }
}

/** Sites in a scope, every status counted once (#958 adds `cancelled`, which only the registry publishes). */
export function siteTotal(
  k: { planned: number; under_construction: number; operating: number; cancelled?: number; no_longer_listed: number; status_not_published: number } | null | undefined,
): number {
  if (!k) return 0
  return k.planned + k.under_construction + k.operating + (k.cancelled ?? 0) + k.no_longer_listed + k.status_not_published
}

/** The sources the listed sites come from, in words ("Epoch AI and the US Data Center Registry"), from the rows' own
 * `source` values, so a scope (or a warehouse) with only one source never names the other. Null when nothing is listed. */
export function siteSourcesText(items: { source?: string | null }[] | null | undefined, total?: number | null): string | null {
  // A capped list (fewer rows than the scope holds) may leave a source out entirely, so it can't say which sources
  // there are: name both (#985). Only a complete list narrows the credit.
  if (total != null && (items?.length ?? 0) < total) return 'Epoch AI and the US Data Center Registry'
  const have = new Set((items ?? []).map((i) => i.source ?? 'epoch'))
  const names = [have.has('epoch') && 'Epoch AI', have.has('us_data_center_registry') && 'the US Data Center Registry'].filter(
    (n): n is string => Boolean(n),
  )
  return names.length ? names.join(' and ') : null
}
