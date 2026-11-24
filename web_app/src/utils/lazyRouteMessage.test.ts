import { describe, expect, it } from 'vitest'
import { lazyRouteFailureMessage } from './lazyRouteMessage'

describe('lazyRouteFailureMessage (#856)', () => {
  it('names the page, keeps the error text as given, and says what to do', () => {
    const m = lazyRouteFailureMessage('Matrix map', new Error('Failed to fetch dynamically imported module: /src/pages/X.tsx'))
    expect(m.title).toBe('Matrix map could not be loaded')
    expect(m.detail).toBe('Failed to fetch dynamically imported module: /src/pages/X.tsx')
    expect(m.hint).toContain('npm install')
    expect(m.hint).toContain('rest of the site still works')
  })

  it('says so when the error carries no detail, instead of inventing one', () => {
    expect(lazyRouteFailureMessage('Matrix map', undefined).detail).toBe(
      'The page failed to load. No further detail was reported.',
    )
    expect(lazyRouteFailureMessage('Matrix map', new Error('   ')).detail).toContain('No further detail')
    expect(lazyRouteFailureMessage('Matrix map', 'plain text').detail).toBe('plain text')
  })
})
