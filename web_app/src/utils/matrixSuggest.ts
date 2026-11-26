/**
 * The "Try" row under the page question (issue #883): one-click suggestions that set the metric blank.
 * Pure so the order is testable: the bundle's own metrics in their published order, without the one in view, only those that
 * have a value for at least one geography (a suggestion never leads to an empty page), capped.
 */
export interface SuggestMetric {
  slug: string
  label: string
}

export const TRY_LIMIT = 8

export function trySuggestions(metrics: SuggestMetric[], currentSlug: string, hasData: (slug: string) => boolean, limit: number = TRY_LIMIT): SuggestMetric[] {
  const seen = new Set<string>([currentSlug])
  const out: SuggestMetric[] = []
  for (const m of metrics) {
    if (seen.has(m.slug) || !m.label.trim() || !hasData(m.slug)) continue
    seen.add(m.slug)
    out.push(m)
    if (out.length >= limit) break
  }
  return out
}

/** Other years in the bundle, newest first, without the one in view. Empty with one vintage. */
export function tryYears(vintages: string[], current: string, limit = 4): string[] {
  return [...vintages].filter((v) => v !== current).sort().reverse().slice(0, limit)
}

/** The visible name of the page's tab. It never says "Matrix map". */
export const MATRIX_TAB_LABEL = 'Analysis'
