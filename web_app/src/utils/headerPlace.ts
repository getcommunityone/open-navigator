// The header's place control (#1191): which place it names, and the address a pick writes. Pure, so it is tested.
// The place in the address (?state=&city=) wins over the saved location, as on the home page (CLAUDE.md: scope via URL).
import { STATE_CODES } from '../lib/usStates'

export interface HeaderPlace {
  stateCode: string
  city: string | null
}

/** The place the header names: the URL's ?state=&city= when it carries a valid state, else the saved location. */
export function headerPlace(
  search: URLSearchParams,
  saved: { state?: string | null; city?: string | null } | null | undefined,
): HeaderPlace | null {
  const urlState = (search.get('state') ?? '').trim().toUpperCase()
  if (STATE_CODES.includes(urlState)) return { stateCode: urlState, city: (search.get('city') ?? '').trim() || null }
  const st = (saved?.state ?? '').trim().toUpperCase()
  if (!STATE_CODES.includes(st)) return null
  return { stateCode: st, city: (saved?.city ?? '').trim() || null }
}

/** "Tuscaloosa, AL", or "AL" for a state-only place. */
export function headerPlaceLabel(p: HeaderPlace | null): string | null {
  return p ? [p.city, p.stateCode].filter(Boolean).join(', ') : null
}

/**
 * The query string after a pick. On home the saved location is the scope, so a carried place is cleared (what the home
 * picker always did); elsewhere the pick becomes the page's ?state=&city=, so the page's label and data follow it.
 */
export function searchAfterPick(pathname: string, search: URLSearchParams, loc: { state?: string; city?: string }): URLSearchParams {
  const next = new URLSearchParams(search)
  next.delete('state')
  next.delete('city')
  const st = (loc.state ?? '').trim().toUpperCase()
  if (pathname !== '/' && STATE_CODES.includes(st)) {
    next.set('state', st)
    const c = (loc.city ?? '').trim()
    if (c) next.set('city', c)
  }
  next.delete('page')
  return next
}
