/**
 * Readable label for a coarse `primary_theme` code (#499):
 * "economic_development" / "ECONOMIC_DEVELOPMENT" → "Economic development".
 * Returns null for empty or the "__unthemed__" sentinel so callers can hide it.
 */
export function themeLabel(code: string | null | undefined): string | null {
  const raw = (code ?? '').trim()
  if (!raw || raw === '__unthemed__') return null
  const words = raw.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase()
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : null
}
