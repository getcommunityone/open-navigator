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

/**
 * Routes that read `?state=&city=` for their data (#1205). On these the header names the page's actual scope, so a page
 * showing national data never sits under a town label (CLAUDE.md, scope label rule).
 */
export const SCOPED_ROUTE_PREFIXES = [
  '/stories',
  '/search',
  '/jurisdictions',
  '/browse-topics',
  '/browse-causes',
  '/decisions-map',
  '/policy-questions',
  '/data-centers',
  '/advocacy-topics',
] as const

/** True when `pathname` is one of `SCOPED_ROUTE_PREFIXES` or below it (`/stories/guns`), not a lookalike (`/stories-old`). */
export function isScopeAwarePath(pathname: string): boolean {
  const path = pathname.replace(/\/+$/, '') || '/'
  return SCOPED_ROUTE_PREFIXES.some((p) => path === p || path.startsWith(`${p}/`))
}

export type HeaderPlaceState =
  /** The page is scoped to this place (it is in the URL): "📍 Tuscaloosa, AL ▾". */
  | { kind: 'scoped'; place: HeaderPlace }
  /** The page shows national data and a town is saved: "📍 National · Use Tuscaloosa, AL". */
  | { kind: 'national-saved'; saved: HeaderPlace }
  /** The page shows national data and no town is saved: "📍 National · Find your town". */
  | { kind: 'national' }
  /** Home (its own level picker) or a page that isn't scope-aware: the reader's town, or none. */
  | { kind: 'town'; place: HeaderPlace | null }

/** What the header's place control shows on `pathname` (#1205). */
export function headerPlaceState(
  pathname: string,
  search: URLSearchParams,
  saved: { state?: string | null; city?: string | null } | null | undefined,
): HeaderPlaceState {
  // Home with National chosen (#1285, `?scope=national`): the header says National and offers the place back in one click.
  if (isHomePath(pathname) && search.get('scope') === 'national') {
    const back = headerPlace(search, saved)
    return back ? { kind: 'national-saved', saved: back } : { kind: 'national' }
  }
  if (!isScopeAwarePath(pathname)) return { kind: 'town', place: headerPlace(search, saved) }
  const fromUrl = headerPlace(search, null)
  if (fromUrl) return { kind: 'scoped', place: fromUrl }
  const savedPlace = headerPlace(new URLSearchParams(), saved)
  return savedPlace ? { kind: 'national-saved', saved: savedPlace } : { kind: 'national' }
}

const isHomePath = (pathname: string) => (pathname.replace(/\/+$/, '') || '/') === '/'

/**
 * The query string for the header's one-click National (#1285). On home the place stays (it's the reader's town) and
 * `scope=national` is added; on a scoped page the place is dropped, so the label, the URL and the data go national together.
 * Null when there is nothing to reset.
 */
export function searchForNational(pathname: string, search: URLSearchParams, hasTown: boolean): URLSearchParams | null {
  const next = new URLSearchParams(search)
  next.delete('page')
  if (isHomePath(pathname)) {
    if (!hasTown || next.get('scope') === 'national') return null
    next.set('scope', 'national')
    return next
  }
  if (!next.has('state') && !next.has('city')) return null
  next.delete('state')
  next.delete('city')
  return next
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
  next.delete('scope')
  const st = (loc.state ?? '').trim().toUpperCase()
  if (pathname !== '/' && STATE_CODES.includes(st)) {
    next.set('state', st)
    const c = (loc.city ?? '').trim()
    if (c) next.set('city', c)
  }
  next.delete('page')
  return next
}
