/** Popup content and options for the Places map (`PlaceClusterMap`). Kept out of the
 *  component so the label, the links and the escaping are unit-tested. Counts are real
 *  (from the warehouse); nothing here invents a figure. */

export interface PlacePopupPin {
  geoid: string
  name: string
  state_code: string | null
  place_count: number
  transcript_count: number
}

/** Leaflet popup options: pan the map so the popup has room on every side, with extra
 *  space at the top for the page header, so the button can always be clicked. */
export const PLACE_POPUP_OPTIONS = {
  autoPan: true,
  keepInView: true,
  autoPanPaddingTopLeft: [40, 90] as [number, number],
  autoPanPaddingBottomRight: [40, 40] as [number, number],
  minWidth: 180,
  maxWidth: 260,
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/** State pins open the places list filtered to that state; every other place opens its
 *  meetings page. */
export function placePopupHtml(pin: PlacePopupPin, level: string): string {
  const name = escapeHtml(pin.name)
  const isState = level === 'state'
  const href = isState
    ? `/jurisdictions?state=${encodeURIComponent(pin.state_code ?? '')}`
    : `/jurisdiction/${encodeURIComponent(pin.geoid)}/meetings`
  const label = isState ? `Browse places in ${name} →` : 'Open meetings →'
  const transcripts = `${pin.transcript_count.toLocaleString()} transcript${pin.transcript_count === 1 ? '' : 's'}`
  const places = isState
    ? `<div style="color:#6b7280;font-size:12px;margin-top:2px">${pin.place_count.toLocaleString()} indexed place${pin.place_count === 1 ? '' : 's'}</div>`
    : ''
  return (
    `<div style="min-width:160px">` +
    `<div style="font-weight:700;color:#111827;font-size:14px">${name}</div>` +
    `<div style="color:#6b7280;font-size:12px;margin-top:2px">${transcripts}</div>` +
    places +
    `<a href="${href}" style="display:block;margin-top:10px;padding:8px 12px;border-radius:6px;background:#0d9488;color:#fff;font-weight:600;font-size:13px;text-align:center;text-decoration:none">${label}</a>` +
    `</div>`
  )
}
