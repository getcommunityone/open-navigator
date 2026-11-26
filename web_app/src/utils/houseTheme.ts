import type { CSSProperties } from 'react'
import { DEFAULT_THEME_ID, themeById } from './folioThemes'

/**
 * The Open Navigator house theme, read from `folioThemes.ts` (the same theme the Matrix map defaults to). The data stories hub,
 * the Data Center Story and the Data Center Challenge apply its custom properties on their `.folio` wrapper, so links, buttons,
 * bars, dots and the reveal bars all take their colours from it and no hex value is copied into the stylesheet.
 */
export const HOUSE_THEME = themeById(DEFAULT_THEME_ID)

/** Inline custom properties for the `.folio` wrapper. */
export const HOUSE_STYLE = HOUSE_THEME.vars as unknown as CSSProperties

/**
 * Dot-chart group colours: the theme's segment colours in order, leaving out the pale tints (they would not stand out from the
 * paper) so every group stays distinguishable. Groups beyond the sixth reuse the list; each group also has its own heading.
 */
export const GROUP_COLORS: readonly string[] = [0, 1, 2, 3, 4, 6].map((i) => HOUSE_THEME.seg[i]!)

/**
 * One colour per concern (#1139), fixed by the concern rather than by its place in the list, so water is the same colour in
 * every state and nationally. The order follows the national ranking; the seventh takes the theme's dark ochre ink (the pale
 * tints would vanish on the paper) so no two concerns share a colour. A concern outside this list falls back to the neutral.
 */
const CONCERN_ORDER = ['traffic', 'water', 'land', 'noise', 'pollution', 'taxes', 'electricity'] as const
const CONCERN_COLORS: readonly string[] = [...GROUP_COLORS, HOUSE_THEME.vars['--vermilion-ink'] ?? HOUSE_THEME.neutral]

/** The fixed colour of a concern key. */
export function concernColor(concern: string): string {
  const i = (CONCERN_ORDER as readonly string[]).indexOf(concern)
  return i >= 0 ? CONCERN_COLORS[i]! : (HOUSE_THEME.seg[8] ?? HOUSE_THEME.neutral)
}
