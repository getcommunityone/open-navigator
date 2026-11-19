/** Label for a live advocacy-topic meeting total. Null when unavailable (no fabricated stand-in). */
export function advocacyMeetingCountLabel(n: number | null | undefined): string | null {
  if (typeof n !== 'number' || !Number.isFinite(n) || n <= 0) return null
  return `${n.toLocaleString('en-US')} related meeting${n === 1 ? '' : 's'}`
}
