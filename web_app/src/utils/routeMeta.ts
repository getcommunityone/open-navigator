// Per-route <head> meta (#1430): the title, description, canonical and breadcrumbs for a path. The server renders the same
// meta into the first HTML (api/seo.py) from the same data files, so crawlers, link previews and in-app navigation agree.
import routesData from '../data/seo/routes.json'
import storyCopy from '../data/seo/story-copy.json'
import { documentTitle } from './useDocumentTitle'

export interface RouteDef {
  path: string
  title: string
  description: string
  sitemap: boolean
  changefreq?: string
  priority?: string
}

export interface Breadcrumb {
  name: string
  url: string
}

export interface RouteMeta {
  /** The page's name, without the site suffix ("" on home). */
  page: string
  /** The full `<title>`: "<page> | CommunityOne". */
  title: string
  description: string
  canonical: string
  robots: string
  breadcrumbs: Breadcrumb[]
}

/** What the app knows about the live stories when it asks: a topic story's title, and the state's name. */
export interface RouteMetaContext {
  /** The story's display title ("Gun control"), when the topic catalog has loaded. */
  storyTitle?: string | null
  /** The story's lede, when known. */
  storyLede?: string | null
  /** The full state name for `?state=` ("Alabama"). */
  stateName?: string | null
}

export const SITE = routesData.site
export const PUBLIC_ROUTES: RouteDef[] = routesData.routes as RouteDef[]
const PRIVATE: { prefix: string; title: string }[] = routesData.private
const ROUTES_BY_PATH = new Map(PUBLIC_ROUTES.map((r) => [r.path, r]))
const REGISTRY: Record<string, { title: string; topic: string; question: string; lede: string }> = storyCopy.stories
const TOPIC_COPY: Record<string, { title?: string; subject?: string; lede?: string; companiesPath?: string }> = storyCopy.topics
const DATA_EXPLORER_MAP = '/data-explorer/map/us/2024/median_household_income'

const cap = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s)

/** "Gun control in Alabama — Data story" (api/seo.py `story_page_title`). */
export function storyPageTitle(topicTitle: string, stateName?: string | null): string {
  return `${cap(topicTitle)}${stateName ? ` in ${stateName}` : ''} — Data story`
}

/** The story's title from the copy alone: the registry's topic, else a topic's hand-written title. */
export function storyCopyTitle(slug: string): string | null {
  const reg = REGISTRY[slug]
  if (reg) return cap(reg.topic)
  return TOPIC_COPY[slug]?.title ?? null
}

function normPath(pathname: string): string {
  const p = `/${(pathname || '').replace(/^\/+|\/+$/g, '')}`
  return p
}

/** The meta for `pathname` + `search`. Mirrors `route_meta()` in api/seo.py. */
export function routeMeta(pathname: string, search = '', ctx: RouteMetaContext = {}): RouteMeta {
  const base = SITE.baseUrl.replace(/\/$/, '')
  const p = normPath(pathname)
  const make = (page: string, description: string, canonical: string, extra: Partial<RouteMeta> = {}): RouteMeta => ({
    page,
    title: documentTitle(page),
    description: description || SITE.defaultDescription,
    canonical,
    robots: 'index, follow',
    breadcrumbs: [],
    ...extra,
  })

  const priv = PRIVATE.find((r) => p === r.prefix || p.startsWith(`${r.prefix}/`))
  if (priv) return make(priv.title, SITE.defaultDescription, `${base}${p}`, { robots: 'noindex, nofollow' })

  const story = /^\/stories\/([^/]+)$/.exec(p)
  if (story) {
    const slug = decodeURIComponent(story[1]!)
    const topicTitle = ctx.storyTitle ?? storyCopyTitle(slug)
    if (!topicTitle) return make('Data story', SITE.defaultDescription, `${base}${p}`)
    const raw = (new URLSearchParams(search).get('state') ?? '').trim().toUpperCase()
    const stateCode = /^[A-Z]{2}$/.test(raw) ? raw : null
    const label = stateCode ? ctx.stateName || stateCode : null
    const storyUrl = `${base}/stories/${encodeURIComponent(slug)}`
    const canonical = stateCode ? `${storyUrl}?state=${stateCode}` : storyUrl
    const lede =
      ctx.storyLede ?? REGISTRY[slug]?.lede ?? TOPIC_COPY[slug]?.lede ?? `What local governments said about ${topicTitle.toLowerCase()}, in the words said at the meeting.`
    const breadcrumbs: Breadcrumb[] = [
      { name: SITE.name, url: `${base}/` },
      { name: 'Data stories', url: `${base}/stories` },
      { name: cap(topicTitle), url: storyUrl },
      ...(stateCode ? [{ name: label!, url: canonical }] : []),
    ]
    return make(storyPageTitle(topicTitle, label), label ? `${label}: ${lede}` : lede, canonical, { breadcrumbs })
  }

  const route = ROUTES_BY_PATH.get(p) ?? (p.startsWith('/data-explorer/map/') ? ROUTES_BY_PATH.get(DATA_EXPLORER_MAP) : undefined)
  if (route) return make(route.title, route.description, p === '/' ? `${base}/` : `${base}${p}`)

  return { page: '', title: SITE.defaultTitle, description: SITE.defaultDescription, canonical: `${base}${p}`, robots: 'index, follow', breadcrumbs: [] }
}

/** The public routes listed in the sitemap (api/seo.py reads the same flag). */
export function sitemapRoutes(): RouteDef[] {
  return PUBLIC_ROUTES.filter((r) => r.sitemap)
}
