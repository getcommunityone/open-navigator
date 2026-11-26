// Headline clauses without zeros (#1134): a title never says "0 asked a question". Clauses with a count of 0 are dropped
// and the rest are joined the way a person writes them ("2 spoke for it and 1 against").

/** "a", "a and b", "a, b and c"; "" for none. */
export function joinClauses(parts: string[]): string {
  const p = parts.filter(Boolean)
  if (p.length <= 1) return p[0] ?? ''
  return `${p.slice(0, -1).join(', ')} and ${p[p.length - 1]}`
}

export interface CountClause {
  n: number | null | undefined
  /** The clause for this count, e.g. (n) => `${n} spoke for it`. */
  text: (n: number) => string
}

/** The clauses whose count is above 0, larger counts first when `leadLarger` (stable for ties), joined. */
export function countClauses(items: CountClause[], opts: { leadLarger?: boolean } = {}): string {
  const kept = items
    .map((c, i) => ({ n: typeof c.n === 'number' && Number.isFinite(c.n) ? c.n : 0, text: c.text, i }))
    .filter((c) => c.n > 0)
  if (opts.leadLarger) kept.sort((a, b) => b.n - a.n || a.i - b.i)
  return joinClauses(kept.map((c) => c.text(c.n)))
}
