/** Shared by every Leaflet map popup in the app, so the padding is defined once. */

/** Pan the map so a popup has room on every side, with extra space at the top for the
 *  page header, so anything inside it (a button, a link) can always be clicked. */
export const MAP_POPUP_OPTIONS = {
  autoPan: true,
  keepInView: true,
  autoPanPaddingTopLeft: [40, 90] as [number, number],
  autoPanPaddingBottomRight: [40, 40] as [number, number],
}

/** For popup content built as an HTML string (`bindPopup`). */
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
