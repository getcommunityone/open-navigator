/** Absolute Docusaurus links for the Vite app (prod vs local docs origin). */

const DOCS_ORIGIN = import.meta.env.PROD
  ? 'https://www.communityone.com/docs'
  : 'http://localhost:3000/docs'

/** Build an absolute docs URL. `path` is under the docs root (e.g. `/intro`). */
export function docsUrl(path: string): string {
  const rooted = path.startsWith('/') ? path : `/${path}`
  return `${DOCS_ORIGIN}${rooted}`
}

export const DOCS_INTRO = docsUrl('/intro')

/**
 * Admin app path → docs path (no `/docs` prefix; `docsUrl` adds the origin).
 * Lighthouse intentionally omitted until a dedicated page exists.
 */
export const ADMIN_GUIDE_BY_PATH: Readonly<Record<string, string>> = {
  '/admin/batch-jobs': '/development/ai-policy-analysis',
  '/admin/meeting-kinds': '/development/jev-meeting-kind-gate',
  '/admin/application-links': '/development/data-center-application-links',
}

/** Absolute Guide href for an admin pathname, or null when unmapped. */
export function adminGuideHref(pathname: string): string | null {
  const entry = Object.entries(ADMIN_GUIDE_BY_PATH).find(
    ([appPath]) => pathname === appPath || pathname.startsWith(`${appPath}/`),
  )
  return entry ? docsUrl(entry[1]) : null
}