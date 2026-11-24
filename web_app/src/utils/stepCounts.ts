/** True when a Load step has skipped or failed items worth opening (#823). */
export function hasProblems(counts?: Record<string, number> | null): boolean {
  if (!counts) return false
  return (counts.skipped ?? 0) + (counts.errors ?? 0) + (counts.error ?? 0) > 0
}
