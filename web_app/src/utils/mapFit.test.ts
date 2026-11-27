import { describe, expect, it } from 'vitest'
import { MAP_MIN_COUNTY_PX, MAP_MIN_LABEL_PX, labelUnits, mapAspect } from './mapFit'

// #1309: the county map fits the screen; its labels stay readable however small the map is drawn.
describe('labelUnits', () => {
  const vbW = 600 // viewBox width in map units
  it('keeps the map-scaled size when the map is drawn large (a wide laptop column)', () => {
    // 600 units drawn at 900px: 15 units = 22.5px, above the minimum.
    expect(labelUnits(15, vbW, 900, MAP_MIN_LABEL_PX)).toBe(15)
  })
  it('raises the size so a label is at least 12px on screen when the map is drawn small (a phone)', () => {
    // 600 units drawn at 300px: 15 units would be 7.5px; 24 units = 12px.
    const u = labelUnits(15, vbW, 300, MAP_MIN_LABEL_PX)
    expect(u).toBe(24)
    expect((u * 300) / vbW).toBeCloseTo(12)
  })
  it('county names keep their own, smaller minimum', () => {
    expect((labelUnits(10, vbW, 300, MAP_MIN_COUNTY_PX) * 300) / vbW).toBeCloseTo(10.5)
  })
  it('an unmeasured map (first render, no layout) keeps the map-scaled size', () => {
    expect(labelUnits(15, vbW, 0, MAP_MIN_LABEL_PX)).toBe(15)
    expect(labelUnits(15, 0, 300, MAP_MIN_LABEL_PX)).toBe(15)
  })
})

describe('mapAspect', () => {
  it('is width over height, and 1 for a degenerate box', () => {
    expect(mapAspect(320, 500)).toBeCloseTo(0.64)
    expect(mapAspect(0, 0)).toBe(1)
  })
})
