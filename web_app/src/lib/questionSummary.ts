// The question dashboard's plain-language summary (#508), built only from real counts
// the API returns for the active scope (CLAUDE.md: No Fabricated Data). Nothing here
// invents a figure: a zero count is left out of the breakdown, and an empty scope says so.

export type SummaryOutcome = 'approved' | 'denied' | 'moratorium' | 'deferred' | 'other'

export interface SummaryRollup {
  instances_total: number
  bills_total?: number
  jurisdictions_total: number
  states_total: number
  approved_count: number
  denied_count: number
  moratorium_count: number
  deferred_count: number
  other_count: number
  first_occurred_at?: string | null
}

const ORDER: SummaryOutcome[] = ['approved', 'denied', 'moratorium', 'deferred', 'other']

const count = (r: SummaryRollup, f: SummaryOutcome): number =>
  ({
    approved: r.approved_count,
    denied: r.denied_count,
    moratorium: r.moratorium_count,
    deferred: r.deferred_count,
    other: r.other_count,
  })[f] ?? 0

const plural = (n: number, one: string, many: string) => `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`

// "approved" / "moratoriums" in the breakdown list.
const familyWord = (f: SummaryOutcome, n: number) => (f === 'moratorium' ? (n === 1 ? 'moratorium' : 'moratoriums') : f)

// The noun for n records of one outcome family ("5 approved decisions", "4 moratoriums").
const familyNoun = (f: SummaryOutcome, n: number) =>
  f === 'moratorium' ? plural(n, 'moratorium', 'moratoriums') : plural(n, `${f} decision`, `${f} decisions`)

// "2026-05-28..." -> "May 2026" (UTC, so a midnight date never slips a month).
export const monthYear = (iso: string | null | undefined): string | null => {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' })
}

/**
 * "25 decisions in 15 governments across 4 states since May 2026: 5 approved, 1 denied,
 * 4 moratoriums, 5 deferred, 10 other. Discussed in 1,270 meetings."
 *
 * With an outcome, `rollup` is the counts for that family only:
 * "5 approved decisions in 2 governments since Jun 2026. The question was discussed in
 * 104 meetings." The meetings count is for the place scope (all outcomes).
 */
export function questionSummary(
  rollup: SummaryRollup | null | undefined,
  opts: { outcome?: SummaryOutcome; meetings?: number } = {},
): string {
  const meetings = opts.meetings ?? 0
  const n = rollup?.instances_total ?? 0
  const meetingsSentence =
    meetings > 0
      ? opts.outcome
        ? ` The question was discussed in ${plural(meetings, 'meeting', 'meetings')}.`
        : ` Discussed in ${plural(meetings, 'meeting', 'meetings')}.`
      : ''

  if (!rollup || n === 0) {
    const what = !opts.outcome ? 'decisions' : opts.outcome === 'moratorium' ? 'moratoriums' : `${opts.outcome} decisions`
    return `No ${what} recorded yet in this scope.${meetingsSentence}`
  }

  const what = opts.outcome
    ? familyNoun(opts.outcome, n)
    : (rollup.bills_total ?? 0) > 0
      ? plural(n, 'decision or bill', 'decisions and bills')
      : plural(n, 'decision', 'decisions')
  const where = ` in ${plural(rollup.jurisdictions_total, 'government', 'governments')}`
  const states = rollup.states_total > 1 ? ` across ${rollup.states_total} states` : ''
  const since = monthYear(rollup.first_occurred_at)
  const head = `${what}${where}${states}${since ? ` since ${since}` : ''}`

  if (opts.outcome) return `${head}.${meetingsSentence}`

  const parts = ORDER.filter((f) => count(rollup, f) > 0).map(
    (f) => `${count(rollup, f).toLocaleString('en-US')} ${familyWord(f, count(rollup, f))}`,
  )
  return `${head}${parts.length ? `: ${parts.join(', ')}` : ''}.${meetingsSentence}`
}
