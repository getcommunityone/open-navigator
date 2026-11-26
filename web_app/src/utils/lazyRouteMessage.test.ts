import { describe, expect, it } from 'vitest'
import { lazyRouteFailureMessage } from './lazyRouteMessage'

describe('lazyRouteFailureMessage (#856, #936)', () => {
  it('in development, names the page, keeps the error text as given, and says to run npm install', () => {
    const m = lazyRouteFailureMessage('Matrix map', new Error('Failed to fetch dynamically imported module: /src/pages/X.tsx'), { dev: true })
    expect(m.title).toBe('Matrix map could not be loaded')
    expect(m.detail).toBe('Failed to fetch dynamically imported module: /src/pages/X.tsx')
    expect(m.hint).toContain('npm install')
    expect(m.hint).toContain('rest of the site still works')
  })

  it('on the public site, a missing chunk after a deploy says the site was updated, not npm install', () => {
    const m = lazyRouteFailureMessage(
      'Data story',
      new Error('Unable to preload CSS for https://www.communityone.com/assets/ScrollCue-C-uJ7YO1.css'),
      { dev: false, online: true },
    )
    expect(m.title).toBe('Data story could not be loaded')
    expect(m.detail).toBe('Unable to preload CSS for https://www.communityone.com/assets/ScrollCue-C-uJ7YO1.css')
    expect(m.hint).toContain('site was updated')
    expect(m.hint).not.toContain('npm install')
  })

  it('offline, a failed fetch is not blamed on a deploy', () => {
    const m = lazyRouteFailureMessage('Data story', new Error('Failed to fetch dynamically imported module: https://x/a.js'), { dev: false, online: false })
    expect(m.hint).toContain('offline')
    expect(m.hint).not.toContain('site was updated')
  })

  it('on the public site, any other failure just offers a reload', () => {
    const m = lazyRouteFailureMessage('Data story', new Error('x is not a function'), { dev: false, online: true })
    expect(m.hint).toBe('The rest of the site still works. Reload to try again.')
  })

  it('says so when the error carries no detail, instead of inventing one', () => {
    expect(lazyRouteFailureMessage('Matrix map', undefined).detail).toBe(
      'The page failed to load. No further detail was reported.',
    )
    expect(lazyRouteFailureMessage('Matrix map', new Error('   ')).detail).toContain('No further detail')
    expect(lazyRouteFailureMessage('Matrix map', 'plain text').detail).toBe('plain text')
  })
})
