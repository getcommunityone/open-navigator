// Which header link is lit (#1191). Pure, so the rule is tested without rendering the header.
// On home the links name page sections, so the one in view is lit (scroll-spy); elsewhere the route decides.

export type NavKey = 'stories' | 'places' | 'search' | 'how'

/** Home section ids the header's scroll-spy watches, and the link each lights. */
export const HOME_SECTION_NAV: Record<string, NavKey> = {
  'data-stories': 'stories',
  search: 'search',
  'how-it-works': 'how',
}

/**
 * The lit header link for `pathname`. `homeSection` is the home section in view (empty off home or between sections).
 * `/stories*` and `/challenge*` → Data Stories; `/jurisdictions*` and `/jurisdiction/*` → Places; `/search` → Search.
 */
export function activeNavKey(pathname: string, homeSection = ''): NavKey | null {
  const path = pathname.replace(/\/+$/, '') || '/'
  if (path === '/') return HOME_SECTION_NAV[homeSection] ?? null
  if (path === '/stories' || path.startsWith('/stories/') || path === '/challenge' || path.startsWith('/challenge/')) return 'stories'
  if (path === '/jurisdictions' || path.startsWith('/jurisdictions/') || path.startsWith('/jurisdiction/')) return 'places'
  if (path === '/search') return 'search'
  return null
}
