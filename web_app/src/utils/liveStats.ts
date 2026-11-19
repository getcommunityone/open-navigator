// Live headline counts for cards and chips. A figure shown to a visitor is either read from the national
// GET /api/stats rollup or not shown at all (CLAUDE.md, "No Fabricated Data"): nothing here has a typed-in fallback.

/** Fields of the national /api/stats rollup that the cards can show. */
export type NationalStatKey = 'events' | 'bills' | 'nonprofits' | 'leaders'

export interface NationalStats extends Partial<Record<NationalStatKey, number | null>> {
  /** Local governments in the catalog; null when the serving table has no such figure. */
  governments?: number | null
}

/** Which rollup field a card chip reads, and the noun that follows the count ("13,456 bills"). */
export interface LiveStatSpec {
  key: NationalStatKey
  noun: string
}

/**
 * "12,345 bills" for a spec, or null when the count is missing, zero or not a number: the caller then shows no chip
 * rather than a stand-in figure.
 */
export function formatLiveStat(spec: LiveStatSpec, stats: NationalStats | null | undefined): string | null {
  const value = stats?.[spec.key]
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return null
  return `${value.toLocaleString('en-US')} ${spec.noun}`
}
