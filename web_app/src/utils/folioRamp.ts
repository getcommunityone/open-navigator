/** Sequential ramp for the Matrix map: reference violet tint -> violet -> violet-ink (six steps, like the shade bins). */
export const FOLIO_RAMP = ['#E4DFFC', '#C9BEFB', '#A797FC', '#7C63FF', '#5A3BE6', '#3A22A8'] as const
export const FOLIO_INK = '#121116'
export const FOLIO_NEUTRAL = '#CFCBD9'
export const FOLIO_VERMILION = '#E2492C'
/** Mid-point of each of the six shade bins (BIN_EDGES 0.1/0.25/0.45/0.65/0.8 on the page). */
const STEP_MID_T = [0.05, 0.175, 0.35, 0.55, 0.725, 0.9] as const
export { STEP_MID_T }

const lin = (c: number) => {
  const s = c / 255
  return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
}
export function luminance(hex: string): number {
  const n = parseInt(hex.replace('#', ''), 16)
  return 0.2126 * lin((n >> 16) & 255) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255)
}
export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (hi + 0.05) / (lo + 0.05)
}
/**
 * Whichever candidate has the highest contrast on `bg` (decided by luminance, not by guesswork). Defaults to the default
 * theme's ink; themed charts pass their own ink as well. White and black are always candidates, and one of the two always
 * reaches 4.5:1 on any colour, so a label is never below AA.
 */
export function labelOn(bg: string, extra: readonly string[] = [FOLIO_INK]): string {
  const best = (cands: readonly string[]) => cands.reduce((b, c) => (contrastRatio(bg, c) > contrastRatio(bg, b) ? c : b), cands[0]!)
  const pick = best([...extra, '#FFFFFF'])
  return contrastRatio(bg, pick) >= 4.5 ? pick : best([pick, '#000000'])
}
