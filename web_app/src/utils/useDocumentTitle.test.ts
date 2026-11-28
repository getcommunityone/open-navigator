import { describe, expect, it, vi } from 'vitest'

// No DOM test environment in this app: run the hook's effects by hand against a stand-in `document`.
const cleanups: Array<() => void> = []
vi.mock('react', () => ({
  useEffect: (fn: () => void | (() => void)) => {
    const c = fn()
    if (typeof c === 'function') cleanups.push(c)
  },
}))

const { DEFAULT_DOCUMENT_TITLE, documentTitle, pageClaimsTitle, useDocumentTitle } = await import('./useDocumentTitle')

describe('documentTitle', () => {
  it('names the page before the site', () => {
    expect(documentTitle('Search: fluoride')).toBe('Search: fluoride | CommunityOne')
    expect(documentTitle('  Guns —  Data story ')).toBe('Guns — Data story | CommunityOne')
  })
  it('falls back to the default title', () => {
    expect(documentTitle()).toBe(DEFAULT_DOCUMENT_TITLE)
    expect(documentTitle(null)).toBe(DEFAULT_DOCUMENT_TITLE)
    expect(documentTitle('   ')).toBe(DEFAULT_DOCUMENT_TITLE)
  })
})

describe('useDocumentTitle', () => {
  it('sets the page title and restores the default on unmount', () => {
    const doc = { title: 'before' }
    vi.stubGlobal('document', doc)
    useDocumentTitle('Places')
    expect(doc.title).toBe('Places | CommunityOne')
    // The page claims the title while mounted, so the route-level title (RouteMetaSync) leaves it alone (#1430).
    expect(pageClaimsTitle()).toBe(true)
    cleanups.splice(0).forEach((c) => c())
    expect(doc.title).toBe(DEFAULT_DOCUMENT_TITLE)
    expect(pageClaimsTitle()).toBe(false)
    vi.unstubAllGlobals()
  })
})
