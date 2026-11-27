import { describe, expect, it } from 'vitest'
import { labelWidth, placeValueLabels, wrapLabel } from './dumbbellLabels'

const W = 36 // a "30.5%" label
const overlap = (a: { x: number }, b: { x: number }, wa = W, wb = W) => Math.abs(a.x - b.x) < (wa + wb) / 2

describe('labelWidth', () => {
  it('grows with the text', () => {
    expect(labelWidth('5.0%')).toBeLessThan(labelWidth('30.5%'))
    expect(labelWidth('')).toBe(0)
  })
})

describe('placeValueLabels', () => {
  it('centres each label over its dot when they are far apart', () => {
    const r = placeValueLabels({ x: 100, width: W }, { x: 250, width: W }, 0, 340)
    expect(r.a).toEqual({ x: 100, below: false })
    expect(r.b).toEqual({ x: 250, below: false })
  })

  it('keeps a label inside the row at either edge', () => {
    const r = placeValueLabels({ x: 2, width: W }, { x: 338, width: W }, 0, 340)
    expect(r.a!.x).toBe(W / 2)
    expect(r.b.x).toBe(340 - W / 2)
  })

  it('nudges close dots apart in the dots’ order, symmetric about their midpoint', () => {
    const r = placeValueLabels({ x: 160, width: W }, { x: 170, width: W }, 0, 340, 4)
    expect(r.a!.below).toBe(false)
    expect(r.b.below).toBe(false)
    expect(r.a!.x).toBeLessThan(r.b.x)
    expect(overlap(r.a!, r.b)).toBe(false)
    expect((r.a!.x + r.b.x) / 2).toBeCloseTo(165, 5)
  })

  it('puts the hollow label on the right when the value fell', () => {
    const r = placeValueLabels({ x: 170, width: W }, { x: 160, width: W }, 0, 340)
    expect(r.a!.x).toBeGreaterThan(r.b.x)
    expect(overlap(r.a!, r.b)).toBe(false)
  })

  it('separates labels for equal values', () => {
    const r = placeValueLabels({ x: 120, width: W }, { x: 120, width: W }, 0, 340)
    expect(overlap(r.a!, r.b)).toBe(false)
  })

  it('slides a nudged pair inward at the edge instead of clipping', () => {
    const r = placeValueLabels({ x: 3, width: W }, { x: 8, width: W }, 0, 340)
    expect(Math.min(r.a!.x, r.b.x) - W / 2).toBeGreaterThanOrEqual(0)
    expect(overlap(r.a!, r.b)).toBe(false)
    expect(r.a!.below).toBe(false)
  })

  it('puts the hollow label below when there is no room side by side', () => {
    const r = placeValueLabels({ x: 30, width: W }, { x: 32, width: W }, 0, 60)
    expect(r.a!.below).toBe(true)
    expect(r.b.below).toBe(false)
  })

  it('places a single value alone', () => {
    const r = placeValueLabels(null, { x: 5, width: W }, 0, 340)
    expect(r.a).toBeNull()
    expect(r.b).toEqual({ x: W / 2, below: false })
  })
})

describe('wrapLabel', () => {
  it('keeps a short label on one line', () => {
    expect(wrapLabel('Traffic', 20)).toEqual(['Traffic'])
  })
  it('wraps at spaces onto two lines', () => {
    expect(wrapLabel('Land and property', 10)).toEqual(['Land and', 'property'])
    expect(wrapLabel('Land and property values', 14)).toEqual(['Land and', 'property…'])
  })
  it('never returns more than two lines and marks a cut', () => {
    const lines = wrapLabel('One two three four five six seven eight', 10)
    expect(lines).toHaveLength(2)
    expect(lines[1]!.endsWith('…')).toBe(true)
    lines.forEach((l) => expect(l.length).toBeLessThanOrEqual(10))
  })
})
