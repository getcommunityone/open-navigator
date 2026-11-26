import { describe, expect, it } from 'vitest'
import { activeSortKey, largestRemainder, medianOf, niceScale, olsFit, quantileOf, shadeT } from './matrixMapMath'

describe('quantileOf', () => {
  it('interpolates between ranks and ignores missing values', () => {
    expect(quantileOf([1, 2, 3, 4, 5], 0.5)).toBe(3)
    expect(quantileOf([1, 2, 3, 4], 0.25)).toBeCloseTo(1.75)
    expect(quantileOf([null, 10, undefined, 20], 0.5)).toBe(15)
    expect(quantileOf([], 0.5)).toBeNull()
  })
})

describe('niceScale', () => {
  it('covers the data with 1/2/5 steps', () => {
    const s = niceScale(3, 47, 5)
    expect(s.min).toBeLessThanOrEqual(3)
    expect(s.max).toBeGreaterThanOrEqual(47)
    expect(s.ticks).toEqual([0, 10, 20, 30, 40, 50])
  })
  it('can pin zero and survives a flat range', () => {
    expect(niceScale(120, 480, 4, true).min).toBe(0)
    const flat = niceScale(5, 5)
    expect(flat.min).toBeLessThan(5)
    expect(flat.max).toBeGreaterThan(5)
  })
})

describe('shadeT', () => {
  it('places a value in the range and flips for lower-is-better metrics', () => {
    expect(shadeT(75, 50, 100, false)).toBe(0.5)
    expect(shadeT(60, 50, 100, true)).toBeCloseTo(0.8)
  })
  it('is null for missing values and for a flat range', () => {
    expect(shadeT(null, 0, 1, false)).toBeNull()
    expect(shadeT(5, 5, 5, false)).toBeNull()
  })
})

describe('medianOf', () => {
  it('takes the middle value, or the mean of the two middle values', () => {
    expect(medianOf([3, 1, 2])).toBe(2)
    expect(medianOf([4, 1, 3, 2])).toBe(2.5)
  })
  it('ignores missing values and is null when nothing is left', () => {
    expect(medianOf([null, 7, undefined])).toBe(7)
    expect(medianOf([null])).toBeNull()
  })
})

describe('largestRemainder', () => {
  it('always sums to the cell count', () => {
    const cells = largestRemainder([1, 1, 1])
    expect(cells.reduce((a, c) => a + c, 0)).toBe(100)
    expect(cells).toEqual([34, 33, 33])
  })
  it('keeps exact shares and returns nothing for a zero total', () => {
    expect(largestRemainder([50, 30, 20])).toEqual([50, 30, 20])
    expect(largestRemainder([0, 0])).toEqual([])
  })
})

describe('olsFit', () => {
  it('recovers a straight line exactly', () => {
    const fit = olsFit([0, 1, 2, 3].map((x) => ({ x, y: 2 * x + 1 })))
    expect(fit?.slope).toBeCloseTo(2)
    expect(fit?.intercept).toBeCloseTo(1)
    expect(fit?.r2).toBeCloseTo(1)
  })
  it('is null with too few points or no spread in x', () => {
    expect(olsFit([{ x: 1, y: 1 }, { x: 2, y: 2 }])).toBeNull()
    expect(olsFit([{ x: 1, y: 1 }, { x: 1, y: 2 }, { x: 1, y: 3 }])).toBeNull()
  })
})

describe('activeSortKey', () => {
  it('uses the header sort only in the pivot', () => {
    expect(activeSortKey('pivot', 'income', 'poverty', ['pop'])).toBe('poverty')
    expect(activeSortKey('pivot', 'income', '', ['pop'])).toBe('pop')
  })
  it('orders every other layout by the metric on screen', () => {
    for (const layout of ['tiles', 'dumbbell', 'diverging', 'scatter']) {
      expect(activeSortKey(layout, 'income', 'poverty', ['pop'])).toBe('income')
    }
  })
})
