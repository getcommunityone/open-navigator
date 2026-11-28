// Keeps the <head> in step with in-app navigation (#1430). The server sends each page's meta in the first HTML
// (api/seo.py); after that the SPA changes pages without a reload, so this updates the title (unless the page names its
// own with useDocumentTitle), the description, canonical, robots, OpenGraph/Twitter tags and the story breadcrumbs.
import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { routeMeta, type RouteMeta } from '../utils/routeMeta'
import { pageClaimsTitle } from '../utils/useDocumentTitle'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'

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

export default function RouteMetaSync() {
  const { pathname, search } = useLocation()
  useEffect(() => {
    const code = new URLSearchParams(search).get('state')?.toUpperCase() ?? ''
    applyRouteMeta(routeMeta(pathname, search, { stateName: STATE_CODE_TO_NAME[code] ?? null }), !pageClaimsTitle())
  }, [pathname, search])
  return null
}
