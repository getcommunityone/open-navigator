import { describe, expect, it } from 'vitest'
import {
  ADMIN_GUIDE_BY_PATH,
  DOCS_INTRO,
  adminGuideHref,
  docsUrl,
} from './docsLinks'

describe('docsUrl', () => {
  it('joins the docs base with a rooted path', () => {
    const url = docsUrl('/development/ai-policy-analysis')
    expect(url.endsWith('/docs/development/ai-policy-analysis')).toBe(true)
    expect(url.includes('//docs/')).toBe(false)
  })

  it('normalizes a path missing the leading slash', () => {
    expect(docsUrl('intro')).toBe(docsUrl('/intro'))
  })
})

describe('DOCS_INTRO', () => {
  it('points at the docs intro page', () => {
    expect(DOCS_INTRO).toBe(docsUrl('/intro'))
  })
})

describe('ADMIN_GUIDE_BY_PATH / adminGuideHref', () => {
  it('maps the three admin screens from the contract', () => {
    expect(ADMIN_GUIDE_BY_PATH['/admin/batch-jobs']).toBe(
      '/development/ai-policy-analysis',
    )
    expect(ADMIN_GUIDE_BY_PATH['/admin/meeting-kinds']).toBe(
      '/development/jev-meeting-kind-gate',
    )
    expect(ADMIN_GUIDE_BY_PATH['/admin/application-links']).toBe(
      '/development/data-center-application-links',
    )
    expect(ADMIN_GUIDE_BY_PATH['/admin/lighthouse-report']).toBeUndefined()
  })

  it('resolves exact and nested admin paths to absolute guide URLs', () => {
    expect(adminGuideHref('/admin/batch-jobs')).toBe(
      docsUrl('/development/ai-policy-analysis'),
    )
    expect(adminGuideHref('/admin/batch-jobs/run/abc')).toBe(
      docsUrl('/development/ai-policy-analysis'),
    )
    expect(adminGuideHref('/admin/lighthouse-report')).toBeNull()
    expect(adminGuideHref('/settings')).toBeNull()
  })
})