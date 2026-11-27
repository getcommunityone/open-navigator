import { describe, expect, it } from 'vitest'
import { layoutHoverBadge } from './mapHoverBadge'

const US_VB: [number, number, number, number] = [-4, -4, 983, 618]

describe('layoutHoverBadge (#1360)', () => {
  it('places the pill centered above an interior state like Texas', () => {
    const tx: [number, number, number, number] = [340, 350, 520, 560]
    const b = layoutHoverBadge(tx, US_VB, 'Texas · Click to drill down →', 12)
    expect(b.placed).toBe('above')
    expect(b.y + b.height).toBeLessThan(tx[1])
    expect(Math.abs(b.textX - 430)).toBeLessThan(1)
  })

  it('flips below for a northern border state near the top edge', () => {
    const wa: [number, number, number, number] = [80, 10, 180, 95]
    const b = layoutHoverBadge(wa, US_VB, 'Washington · Click to drill down →', 12)
    expect(b.placed).toBe('below')
    expect(b.y).toBeGreaterThan(wa[3])
  })

  it('clamps horizontally inside the viewBox for right-edge states like Maine', () => {
    const me: [number, number, number, number] = [890, 60, 965, 160]
    const b = layoutHoverBadge(me, US_VB, 'Maine · Click to drill down →', 12)
    expect(b.x + b.width).toBeLessThanOrEqual(US_VB[0] + US_VB[2] - 4)
    expect(b.x).toBeGreaterThanOrEqual(US_VB[0] + 4)
  })

  it('clamps horizontally inside the viewBox for left-edge states like Alaska', () => {
    const ak: [number, number, number, number] = [10, 440, 140, 595]
    const b = layoutHoverBadge(ak, US_VB, 'Alaska · Click to drill down →', 12)
    expect(b.x).toBeGreaterThanOrEqual(US_VB[0] + 4)
    expect(b.y).toBeGreaterThanOrEqual(US_VB[1] + 4)
    expect(b.y + b.height).toBeLessThanOrEqual(US_VB[1] + US_VB[3] - 4)
  })
})
