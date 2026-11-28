import { describe, expect, it } from 'vitest'
import { boxUnit, columnBoxes, peakStatement, MAX_BOX_ROWS } from './storyTimeline'
import type { TimelineYear } from '../api/topicTimeline'

describe('boxUnit', () => {
  it('is 1 while the tallest column fits', () => {
    expect(boxUnit(12)).toBe(1)
    expect(boxUnit(0)).toBe(1)
  })
  it('grows in 1-2-5 steps and never exceeds the row cap', () => {
    for (const max of [13, 40, 976, 1500, 12345, 6]) {
      const u = boxUnit(max)
      expect(Math.ceil(max / u)).toBeLessThanOrEqual(MAX_BOX_ROWS)
    }
    expect(boxUnit(976)).toBe(100)
  })
})

describe('columnBoxes', () => {
  it('is deterministic and the fills add up to the value', () => {
    for (const [v, u] of [[976, 100], [7, 1], [13, 2], [5.8, 1]] as const) {
      const a = columnBoxes(v, u)
      expect(a).toEqual(columnBoxes(v, u))
      expect(a.reduce((s, b) => s + b.fill, 0) * u).toBeCloseTo(v, 6)
    }
  })
  it('counts whole records exactly when unit is 1', () => {
    expect(columnBoxes(9, 1)).toHaveLength(9)
  })
  it('has no boxes for zero', () => {
    expect(columnBoxes(0, 1)).toEqual([])
  })
})

describe('peakStatement', () => {
  const y = (year: string, meetings: number) => ({ year, meetings }) as TimelineYear
  it('states the real peak from full counts', () => {
    const s = peakStatement([y('2024', 24), y('2025', 100), y('2026', 976)], 'data centers')
    expect(s).toContain('2026 has the most: 976 meetings')
    expect(s).toContain('88.7%')
  })
  it('is null on a tie or a single year', () => {
    expect(peakStatement([y('2025', 5), y('2026', 5)], 'x')).toBeNull()
    expect(peakStatement([y('2026', 5)], 'x')).toBeNull()
  })
})
