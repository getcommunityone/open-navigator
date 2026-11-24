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
