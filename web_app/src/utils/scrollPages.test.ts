import { describe, expect, it } from 'vitest'
import { scrollLeftForPage, scrollPages } from './scrollPages'

describe('scrollPages', () => {
  it('is one page when the content fits', () => {
    expect(scrollPages(0, 1000, 1000)).toEqual({ pages: 1, current: 0, atStart: true, atEnd: true })
    expect(scrollPages(0, 1000, 800)).toEqual({ pages: 1, current: 0, atStart: true, atEnd: true })
  })

  it('treats a zero-width scroller as one page', () => {
    expect(scrollPages(0, 0, 500)).toEqual({ pages: 1, current: 0, atStart: true, atEnd: true })
  })

  it('counts pages and the start', () => {
    expect(scrollPages(0, 1000, 2100)).toEqual({ pages: 3, current: 0, atStart: true, atEnd: false })
  })

  it('rounds to the nearest page in the middle', () => {
    expect(scrollPages(1000, 1000, 2100).current).toBe(1)
    expect(scrollPages(400, 1000, 2100).current).toBe(0)
    expect(scrollPages(600, 1000, 2100).current).toBe(1)
  })

  it('puts the end on the last page, even a partial one', () => {
    expect(scrollPages(1100, 1000, 2100)).toEqual({ pages: 3, current: 2, atStart: false, atEnd: true })
    expect(scrollPages(1099.4, 1000, 2100).atEnd).toBe(true)
  })

  it('ignores a one-pixel overflow from rounding', () => {
    expect(scrollPages(0, 1000, 1001).pages).toBe(1)
    expect(scrollPages(0, 1000, 2001).pages).toBe(2)
  })

  it('clamps overscroll', () => {
    expect(scrollPages(-30, 1000, 2100).atStart).toBe(true)
    expect(scrollPages(5000, 1000, 2100).current).toBe(2)
  })
})

describe('scrollLeftForPage', () => {
  it('maps a page to its offset, clamped to the range', () => {
    expect(scrollLeftForPage(0, 1000, 2100)).toBe(0)
    expect(scrollLeftForPage(1, 1000, 2100)).toBe(1000)
    expect(scrollLeftForPage(2, 1000, 2100)).toBe(1100)
    expect(scrollLeftForPage(-1, 1000, 2100)).toBe(0)
  })
})
