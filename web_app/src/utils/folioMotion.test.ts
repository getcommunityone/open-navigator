import { describe, expect, it } from 'vitest'
import { countUpValue, easeOutCubic, rowDelayMs, staggerDelayMs } from './folioMotion'

describe('staggerDelayMs', () => {
  it('is 0 at the origin and the full span at the far corner', () => {
    expect(staggerDelayMs(0, 0, 10)).toBe(0)
    expect(staggerDelayMs(5, 5, 10)).toBe(900)
    expect(staggerDelayMs(2, 3, 10, 1000)).toBe(500)
  })
  it('is 0 when there is no diagonal, and clamps to the span', () => {
    expect(staggerDelayMs(3, 3, 0)).toBe(0)
    expect(staggerDelayMs(3, 3, -2)).toBe(0)
    expect(staggerDelayMs(20, 20, 10)).toBe(900)
    expect(staggerDelayMs(-4, 0, 10)).toBe(0)
  })
})

describe('rowDelayMs', () => {
  it('uses the per-row step for short lists and squeezes long ones into the budget', () => {
    expect(rowDelayMs(0, 10)).toBe(0)
    expect(rowDelayMs(4, 10, 50)).toBe(200)
    expect(rowDelayMs(51, 52, 50, 600)).toBeLessThanOrEqual(600)
    expect(rowDelayMs(0, 1)).toBe(0)
  })
})

describe('easeOutCubic', () => {
  it('runs 0 to 1, fast at first, and clamps', () => {
    expect(easeOutCubic(0)).toBe(0)
    expect(easeOutCubic(1)).toBe(1)
    expect(easeOutCubic(0.5)).toBeCloseTo(0.875)
    expect(easeOutCubic(2)).toBe(1)
    expect(easeOutCubic(-1)).toBe(0)
  })
})

describe('countUpValue', () => {
  it('equals the target exactly at t >= 1', () => {
    expect(countUpValue(1234.5678, 1)).toBe(1234.5678)
    expect(countUpValue(-0.37, 3)).toBe(-0.37)
  })
  it('starts at 0 and moves toward the target, for negative and fractional targets', () => {
    expect(countUpValue(100, 0)).toBe(0)
    expect(countUpValue(100, 0.5)).toBeCloseTo(87.5)
    expect(countUpValue(-40, 0.5)).toBeCloseTo(-35)
    expect(countUpValue(0.25, 0.5)).toBeCloseTo(0.21875)
  })
})
