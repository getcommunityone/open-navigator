// The county map fits the screen (#1309): its height is capped by the visible screen (CSS, from `--map-ar`), and its labels
// stay readable however small that makes it. Pure, so it is tested. Decision: web_docs/docs/development/story-drill-box-transition.md.

/** Smallest on-screen size of a town label, in CSS pixels. */
export const MAP_MIN_LABEL_PX = 12
/** Smallest on-screen size of a county name ("CHILTON COUNTY"), in CSS pixels. */
export const MAP_MIN_COUNTY_PX = 10.5

/**
 * A label's size in viewBox units: the map-scaled `base`, raised so it renders at least `minPx` when `vbWidth` units are
 * drawn `renderedPx` wide. An unmeasured map (0) keeps `base`.
 */
export function labelUnits(base: number, vbWidth: number, renderedPx: number, minPx: number): number {
  if (!(renderedPx > 0) || !(vbWidth > 0)) return base
  return Math.max(base, (minPx * vbWidth) / renderedPx)
}

/** The map's width over its height, for `--map-ar` (1 for a degenerate box). */
export function mapAspect(vbWidth: number, vbHeight: number): number {
  return vbWidth > 0 && vbHeight > 0 ? vbWidth / vbHeight : 1
}
