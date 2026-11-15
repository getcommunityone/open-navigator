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
