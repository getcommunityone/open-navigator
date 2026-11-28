import { describe, expect, it } from 'vitest'
import { PUBLIC_ROUTES, routeMeta, sitemapRoutes, stateName, storyPageTitle } from './routeMeta'
import { serverRenderedFor } from '../components/RouteMetaSync'
import { documentTitle, DEFAULT_DOCUMENT_TITLE } from './useDocumentTitle'

const BASE = 'https://www.communityone.com'

describe('routeMeta (#1430)', () => {
  it('home keeps the site title and a root canonical', () => {
    const m = routeMeta('/')
    expect(m.title).toBe(DEFAULT_DOCUMENT_TITLE)
    expect(m.canonical).toBe(`${BASE}/`)
    expect(m.robots).toBe('index, follow')
  })

  it('every core page has its own descriptive title', () => {
    const titles = sitemapRoutes().map((r) => routeMeta(r.path).title)
    expect(new Set(titles).size).toBe(titles.length)
    expect(routeMeta('/browse-topics').title).toBe('Browse topics | CommunityOne')
    expect(routeMeta('/browse-topics/all').title).toBe('Browse all topics | CommunityOne')
    expect(routeMeta('/stories').title).toBe('All data stories | CommunityOne')
    for (const r of sitemapRoutes()) expect(routeMeta(r.path).description.length).toBeGreaterThan(40)
  })

  it('names a topic story by its curated title, with its lede', () => {
    const m = routeMeta('/stories/guns')
    expect(m.title).toBe('Gun control — Data story | CommunityOne')
    expect(m.description).toMatch(/^Firearm rules/)
    expect(m.canonical).toBe(`${BASE}/stories/guns`)
    expect(m.breadcrumbs.map((b) => b.name)).toEqual(['CommunityOne', 'Data stories', 'Gun control'])
  })

  it('names the Data Center Story from the registry', () => {
    expect(routeMeta('/stories/data-centers').title).toBe('Data centers — Data story | CommunityOne')
  })

  it('a state-scoped story keeps only ?state in its canonical and names the state', () => {
    const m = routeMeta('/stories/guns', '?state=al&screen=overview')
    expect(m.title).toBe('Gun control in Alabama — Data story | CommunityOne')
    expect(m.canonical).toBe(`${BASE}/stories/guns?state=AL`)
    expect(m.description).toMatch(/^Alabama: /)
    expect(m.breadcrumbs[m.breadcrumbs.length - 1]).toEqual({ name: 'Alabama', url: `${BASE}/stories/guns?state=AL` })
  })

  it('ignores a malformed or unknown state', () => {
    expect(routeMeta('/stories/guns', '?state=Alabama!').canonical).toBe(`${BASE}/stories/guns`)
    const zz = routeMeta('/stories/guns', '?state=ZZ')
    expect(zz.title).toBe('Gun control — Data story | CommunityOne')
    expect(zz.canonical).toBe(`${BASE}/stories/guns`)
  })

  it('a state with no meetings for the story is noindex with the story as canonical', () => {
    const m = routeMeta('/stories/guns', '?state=WY', { storyStates: ['AL'] })
    expect(m.title).toBe('Gun control in Wyoming — Data story | CommunityOne')
    expect(m.robots).toBe('noindex, follow')
    expect(m.canonical).toBe(`${BASE}/stories/guns`)
    expect(routeMeta('/stories/guns', '?state=AL', { storyStates: ['AL'] }).robots).toBe('index, follow')
  })

  it('shares one state-name map with the server', () => {
    expect(stateName('ga')).toBe('Georgia')
    expect(stateName('DC')).toBe('District of Columbia')
    expect(stateName('PR')).toBeNull()
  })

  it('has hand-written titles for every topic with copy, so the client never downgrades the server', () => {
    expect(routeMeta('/stories/short-term-rentals').title).toBe('Short-term rentals — Data story | CommunityOne')
    expect(routeMeta('/stories/license-plate-readers').title).toBe('Flock and license plate readers — Data story | CommunityOne')
    expect(routeMeta('/stories/pickleball').breadcrumbs).toHaveLength(3)
  })

  it('keeps the server-rendered head on first load only for the same page', () => {
    expect(serverRenderedFor('/stories/guns', '?screen=overview&state=AL', '/stories/guns?state=AL&screen=overview')).toBe(true)
    expect(serverRenderedFor('/stories/guns', '', '/stories/pickleball')).toBe(false)
    expect(serverRenderedFor('/stories/guns', '', null)).toBe(false)
  })

  it('uses the catalog title for a topic story with no hand-written copy', () => {
    expect(routeMeta('/stories/water-fluoridation').title).toBe('Data story | CommunityOne')
    expect(routeMeta('/stories/water-fluoridation', '', { storyTitle: 'Water fluoridation' }).title).toBe(
      'Water fluoridation — Data story | CommunityOne',
    )
  })

  it('marks private and account pages noindex', () => {
    for (const p of ['/dashboard', '/profile', '/settings', '/admin/batch-jobs', '/feed-setup']) {
      expect(routeMeta(p).robots).toBe('noindex, nofollow')
    }
  })

  it('keeps private pages and API paths out of the sitemap routes', () => {
    const paths = sitemapRoutes().map((r) => r.path)
    for (const p of ['/dashboard', '/analytics', '/profile', '/settings', '/debate-grader', '/services']) expect(paths).not.toContain(p)
    expect(paths.some((p) => p.startsWith('/api'))).toBe(false)
    expect(paths).toContain('/browse-topics/all')
  })

  it('any Data Explorer map shares the explorer title with its own canonical', () => {
    const m = routeMeta('/data-explorer/map/us/2023/poverty_rate')
    expect(m.title).toBe('Data Explorer | CommunityOne')
    expect(m.canonical).toBe(`${BASE}/data-explorer/map/us/2023/poverty_rate`)
  })

  it('a detail page keeps the site default and stays indexable; an unknown path is noindex', () => {
    expect(routeMeta('/decisions/123').title).toBe(DEFAULT_DOCUMENT_TITLE)
    expect(routeMeta('/decisions/123').robots).toBe('index, follow')
    expect(routeMeta('/no-such-page').robots).toBe('noindex, follow')
  })

  it('decodes the path before the private check', () => {
    expect(routeMeta('/admi%6e').robots).toBe('noindex, nofollow')
  })

  it('story titles match the shared helper', () => {
    expect(documentTitle(storyPageTitle('pickleball'))).toBe('Pickleball — Data story | CommunityOne')
    expect(PUBLIC_ROUTES.every((r) => r.path.startsWith('/'))).toBe(true)
  })
})
