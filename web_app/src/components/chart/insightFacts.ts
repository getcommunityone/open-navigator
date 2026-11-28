import type { InsightInput } from '../../utils/chartInsight'
import type { TopicHeatByYear, TopicTopConcern } from '../../api/topics'

/** The picker's `heatByYear` from the API rows; undefined when there are none (a thin year is already omitted server-side). */
export function toHeatByYear(d: TopicHeatByYear | undefined): InsightInput['heatByYear'] {
  const rows = d?.years ?? []
  return rows.length > 0 ? rows.map((y) => ({ year: y.year, mean: y.mean, rated: y.speakers_rated })) : undefined
}

/** The picker's `concern` from the API row; undefined unless a label, counts and basis are all on record. */
export function toConcern(d: TopicTopConcern | undefined): InsightInput['concern'] {
  if (!d || !d.label || d.count == null || d.of == null || d.of <= 0 || !d.basis) return undefined
  return { label: d.label.toLowerCase(), count: d.count, of: d.of, basis: d.basis }
}
