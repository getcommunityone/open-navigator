/** True when a Load step has skipped or failed items worth opening (#823). */
export function hasProblems(counts?: Record<string, number> | null): boolean {
  if (!counts) return false
  return (counts.skipped ?? 0) + (counts.errors ?? 0) + (counts.error ?? 0) > 0
}

/**
 * dbt model counts added up over every dbt step of a run (#843: a Load run has two). `null` when no step
 * recorded any, so the header never shows a zero it did not measure.
 */
export function sumDbtCounts(
  steps: Array<{ counts?: Record<string, number> | null }>,
): { models: number; success: number; error: number } | null {
  const dbt = steps.map((s) => s.counts).filter((c) => !!c && typeof c.models === 'number') as Record<string, number>[]
  if (dbt.length === 0) return null
  const total = (key: string) => dbt.reduce((n, c) => n + (c[key] ?? 0), 0)
  return { models: total('models'), success: total('success'), error: total('error') }
}
