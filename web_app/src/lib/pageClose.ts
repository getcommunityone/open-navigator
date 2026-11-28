/**
 * Where a page's Close (x) goes (#1405). In-app history first: if the entry before this one is ours, Close goes back to it
 * (`navigate(-1)`). Otherwise it goes home, keeping the scope (`?state=&city=` / `?scope=`) and `?topic=`. The scope is never
 * dropped: when the place was changed on this page, Close goes to the previous page with the page's current scope applied.
 */

export const SCOPE_KEYS = ['state', 'city', 'scope', 'topic'] as const

export interface TrailEntry {
  pathname: string
  search: string
}

export type CloseDestination = { kind: 'back'; label: string } | { kind: 'to'; to: string; label: string }

// The entries of this tab's history, keyed by react-router's history index, so "the previous entry" is exact after Back too.
const trail = new Map<number, TrailEntry>()

/** The history index react-router keeps in `history.state` (0 for the first entry of the tab). */
export function historyIndex(): number {
  const idx = (window.history.state as { idx?: number } | null)?.idx
  return typeof idx === 'number' ? idx : 0
}

export function recordLocation(entry: TrailEntry, idx: number = historyIndex()): void {
  trail.set(idx, { pathname: entry.pathname, search: entry.search })
}

export function previousEntry(idx: number = historyIndex()): TrailEntry | null {
  return idx > 0 ? (trail.get(idx - 1) ?? null) : null
}

export function scopeParams(search: string): URLSearchParams {
  const from = new URLSearchParams(search.replace(/^\?/, ''))
  const out = new URLSearchParams()
  for (const k of SCOPE_KEYS) {
    const v = from.get(k)
    if (v) out.set(k, v)
  }
  return out
}

const LABELS: Record<string, string> = {
  '': 'home',
  search: 'search results',
  'browse-topics': 'browse topics',
  'browse-causes': 'browse causes',
  'data-explorer': 'Data Explorer',
  jurisdictions: 'jurisdictions',
  jurisdiction: 'the jurisdiction',
  decisions: 'the decision',
  meetings: 'the meeting',
  bodies: 'the body',
  stories: 'data stories',
  organizations: 'the organization',
  nonprofits: 'nonprofits',
  settings: 'settings',
}

export function placeLabel(pathname: string): string {
  const seg = pathname.split('/')[1] ?? ''
  return LABELS[seg] ?? 'the previous page'
}

const sameScope = (a: URLSearchParams, b: URLSearchParams) => SCOPE_KEYS.every((k) => (a.get(k) ?? '') === (b.get(k) ?? ''))

export function closeDestination(current: TrailEntry, prev: TrailEntry | null): CloseDestination {
  const scope = scopeParams(current.search)
  if (prev && prev.pathname !== current.pathname) {
    const prevScope = scopeParams(prev.search)
    // The page carries no scope of its own, or the same one: plain Back keeps whatever the previous page had.
    if (scope.size === 0 || sameScope(scope, prevScope)) return { kind: 'back', label: placeLabel(prev.pathname) }
    // The place was changed here: go to the previous page with this page's scope, never the stale one.
    const qs = new URLSearchParams(prev.search.replace(/^\?/, ''))
    for (const k of SCOPE_KEYS) qs.delete(k)
    scope.forEach((v, k) => qs.set(k, v))
    const q = qs.toString()
    return { kind: 'to', to: `${prev.pathname}${q ? `?${q}` : ''}`, label: placeLabel(prev.pathname) }
  }
  const q = scope.toString()
  return { kind: 'to', to: `/${q ? `?${q}` : ''}`, label: 'home' }
}

/** Pages that already carry their own Close (the stories) or are not sub-pages. */
export function showsPageClose(pathname: string): boolean {
  return !/^\/stories\/[^/]+/.test(pathname) && pathname !== '/' && pathname !== '/settings' // Settings is a dialog with its own Close
}
