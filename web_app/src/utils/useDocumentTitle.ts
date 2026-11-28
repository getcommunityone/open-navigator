// Per-page document titles (#1191, #1430): "<page> | CommunityOne", so tabs, history, bookmarks and search results tell
// pages apart. The suffix is the brand (the Organization in the JSON-LD), from web_app/src/data/seo/routes.json.
import { useEffect } from 'react'
import routesData from '../data/seo/routes.json'

export const SITE_NAME = routesData.site.titleSuffix
/** The title the site ships with (index.html), used on home and whenever a page names nothing. */
export const DEFAULT_DOCUMENT_TITLE = routesData.site.defaultTitle

/** `"<page> | CommunityOne"`; the default title when `page` is empty. */
export function documentTitle(page?: string | null): string {
  const p = (page ?? '').replace(/\s+/g, ' ').trim()
  return p ? `${p} | ${SITE_NAME}` : DEFAULT_DOCUMENT_TITLE
}

// Pages that name their own title (with data the route table doesn't have, e.g. a search query) claim it, so the
// route-level title (`RouteMetaSync`) leaves it alone. On a navigation the old page's cleanup (claim released) runs
// before any new effect, and the new page's own title effect wins whichever order the two effects run in.
let titleClaims = 0

/** True while a mounted page sets its own title with `useDocumentTitle`. */
export function pageClaimsTitle(): boolean {
  return titleClaims > 0
}

/** Sets `document.title` for this page while it is mounted; the default comes back when it unmounts. */
export function useDocumentTitle(page?: string | null): void {
  const title = documentTitle(page)
  useEffect(() => {
    titleClaims += 1
    return () => {
      titleClaims -= 1
    }
  }, [])
  useEffect(() => {
    document.title = title
  }, [title])
  useEffect(
    () => () => {
      document.title = DEFAULT_DOCUMENT_TITLE
    },
    [],
  )
}
