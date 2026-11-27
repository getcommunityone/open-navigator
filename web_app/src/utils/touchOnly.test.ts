import { afterEach, describe, expect, it, vi } from 'vitest'
import { isTouchOnly, prefersStillMedia } from './touchOnly'

describe('isTouchOnly', () => {
  afterEach(() => vi.unstubAllGlobals())
  it('follows the (hover: none) / (pointer: coarse) media query (#1277)', () => {
    vi.stubGlobal('window', { matchMedia: (q: string) => ({ matches: q === '(hover: none), (pointer: coarse)' }) })
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

describe('prefersStillMedia (#1277)', () => {
  afterEach(() => vi.unstubAllGlobals())
  it('is true for reduced motion, reduced data or Save-Data', () => {
    vi.stubGlobal('window', { matchMedia: (q: string) => ({ matches: q === '(prefers-reduced-motion: reduce)' }) })
    expect(prefersStillMedia()).toBe(true)
    vi.stubGlobal('window', { matchMedia: (q: string) => ({ matches: q === '(prefers-reduced-data: reduce)' }) })
    expect(prefersStillMedia()).toBe(true)
    vi.stubGlobal('window', { matchMedia: () => ({ matches: false }) })
    vi.stubGlobal('navigator', { connection: { saveData: true } })
    expect(prefersStillMedia()).toBe(true)
  })
  it('is false otherwise', () => {
    vi.stubGlobal('window', { matchMedia: () => ({ matches: false }) })
    vi.stubGlobal('navigator', {})
    expect(prefersStillMedia()).toBe(false)
  })
})
