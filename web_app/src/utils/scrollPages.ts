/** Where a horizontal scroller is, in pages of its visible width (#1101). */
export interface ScrollPages {
  /** How many pages of visible width the content spans (at least 1). */
  pages: number
  /** The zero-based page the scroll position is on. */
  current: number
  atStart: boolean
  atEnd: boolean
}

/** Sub-pixel slack: browsers report fractional scroll positions, so "at the end" allows a pixel or two. */
const EPS = 2

/** Pages, the current page and the end states from a scroller's `scrollLeft`, `clientWidth` and `scrollWidth`. */
export function scrollPages(scrollLeft: number, clientWidth: number, scrollWidth: number): ScrollPages {
  if (!(clientWidth > 0) || !(scrollWidth > clientWidth + EPS)) {
    return { pages: 1, current: 0, atStart: true, atEnd: true }
  }
  const max = scrollWidth - clientWidth
  const left = Math.min(Math.max(scrollLeft, 0), max)
  const pages = Math.ceil((scrollWidth - EPS) / clientWidth)
  const atStart = left <= EPS
  const atEnd = left >= max - EPS
  // The last page is reached at the end of the scroll even when it is a partial page.
  const current = atEnd ? pages - 1 : Math.min(pages - 1, Math.round(left / clientWidth))
  return { pages, current, atStart, atEnd }
}

/** The `scrollLeft` that shows page `index` (clamped to the scrollable range). */
export function scrollLeftForPage(index: number, clientWidth: number, scrollWidth: number): number {
  const max = Math.max(0, scrollWidth - clientWidth)
  return Math.min(Math.max(index * clientWidth, 0), max)
}
