// Per-page document titles (#1191): "<page> | Open Navigator", so tabs, history and bookmarks tell pages apart.
import { useEffect } from 'react'

export const SITE_NAME = 'Open Navigator'
/** The title the site ships with (index.html), used on home and whenever a page names nothing. */
export const DEFAULT_DOCUMENT_TITLE = 'CommunityOne — Open Navigator | Civic data & policy tracking'

/** `"<page> | Open Navigator"`; the default title when `page` is empty. */
export function documentTitle(page?: string | null): string {
  const p = (page ?? '').replace(/\s+/g, ' ').trim()
  return p ? `${p} | ${SITE_NAME}` : DEFAULT_DOCUMENT_TITLE
}

/** Sets `document.title` for this page while it is mounted; the default comes back when it unmounts. */
export function useDocumentTitle(page?: string | null): void {
  const title = documentTitle(page)
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
