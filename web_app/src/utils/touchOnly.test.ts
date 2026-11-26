import { afterEach, describe, expect, it, vi } from 'vitest'
import { isTouchOnly } from './touchOnly'

describe('isTouchOnly', () => {
  afterEach(() => vi.unstubAllGlobals())
  it('follows the (hover: none) media query', () => {
    vi.stubGlobal('window', { matchMedia: (q: string) => ({ matches: q === '(hover: none)' }) })
    expect(isTouchOnly()).toBe(true)
    vi.stubGlobal('window', { matchMedia: () => ({ matches: false }) })
    expect(isTouchOnly()).toBe(false)
  })
  it('is false without matchMedia or a window', () => {
    vi.stubGlobal('window', {})
    expect(isTouchOnly()).toBe(false)
    vi.stubGlobal('window', undefined)
    expect(isTouchOnly()).toBe(false)
  })
})
