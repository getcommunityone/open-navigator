import { describe, expect, it } from 'vitest'
import { activeSortKey, largestRemainder, medianOf, olsFit, shadeT } from './matrixMapMath'

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
