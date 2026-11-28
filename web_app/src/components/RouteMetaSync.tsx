// Keeps the <head> in step with in-app navigation (#1430). The server sends each page's meta in the first HTML
// (api/seo.py); after that the SPA changes pages without a reload, so this updates the title (unless the page names its
// own with useDocumentTitle), the description, canonical, robots, OpenGraph/Twitter tags and the story breadcrumbs.
import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { routeMeta, type RouteMeta } from '../utils/routeMeta'
import { pageClaimsTitle } from '../utils/useDocumentTitle'

function setMeta(attr: 'name' | 'property', key: string, value: string) {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.setAttribute('content', value)
}

export function applyRouteMeta(meta: RouteMeta, setTitle: boolean): void {
  if (setTitle) document.title = meta.title
  setMeta('name', 'title', meta.title)
  setMeta('property', 'og:type', meta.breadcrumbs.length > 0 ? 'article' : 'website')
  setMeta('name', 'description', meta.description)
  setMeta('name', 'robots', meta.robots)
  setMeta('property', 'og:url', meta.canonical)
  setMeta('property', 'og:title', meta.title)
  setMeta('property', 'og:description', meta.description)
  setMeta('name', 'twitter:url', meta.canonical)
  setMeta('name', 'twitter:title', meta.title)
  setMeta('name', 'twitter:description', meta.description)
  let link = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
  if (!link) {
    link = document.createElement('link')
    link.rel = 'canonical'
    document.head.appendChild(link)
  }
  link.href = meta.canonical
  document.head.querySelector('script[data-seo="breadcrumbs"]')?.remove()
  if (meta.breadcrumbs.length > 0) {
    const s = document.createElement('script')
    s.type = 'application/ld+json'
    s.dataset.seo = 'breadcrumbs'
    s.textContent = JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: meta.breadcrumbs.map((b, i) => ({ '@type': 'ListItem', position: i + 1, name: b.name, item: b.url })),
    })
    document.head.appendChild(s)
  }
}

/** True when the server rendered the head for exactly this page (api/seo.py adds `<meta name="seo-rendered">`). */
export function serverRenderedFor(pathname: string, search: string, rendered: string | null | undefined): boolean {
  if (!rendered) return false
  const [rp, rq = ''] = rendered.split('?')
  const x = new URLSearchParams(rq)
  const y = new URLSearchParams(search.replace(/^\?/, ''))
  x.sort()
  y.sort()
  return rp === pathname && x.toString() === y.toString()
}

export default function RouteMetaSync() {
  const { pathname, search } = useLocation()
  const first = useRef(true)
  useEffect(() => {
    const wasFirst = first.current
    first.current = false
    // On first load the server already wrote this page's tags with data the app may not have yet (the story list,
    // which states have meetings), so keep them rather than downgrade them. Later navigations update everything.
    const rendered = document.head.querySelector<HTMLMetaElement>('meta[name="seo-rendered"]')?.content
    if (wasFirst && serverRenderedFor(pathname, search, rendered)) return
    applyRouteMeta(routeMeta(pathname, search), !pageClaimsTitle())
  }, [pathname, search])
  return null
}
