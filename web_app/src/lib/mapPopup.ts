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

/** An "Open meetings →" button for a popup written as an HTML string. Only a real
 *  7-digit place GEOID gets one; anything else (a placeholder id, a missing value)
 *  yields no button rather than a link to nothing. */
export function meetingsButtonHtml(geoid: string | null | undefined): string {
  if (!geoid || !/^\d{7}$/.test(geoid)) return ''
  return (
    `<a href="/jurisdiction/${encodeURIComponent(geoid)}/meetings" ` +
    `style="display:block;margin-top:10px;padding:8px 12px;border-radius:6px;background:#0d9488;color:#fff;font-weight:600;font-size:13px;text-align:center;text-decoration:none">Open meetings →</a>`
  )
}
