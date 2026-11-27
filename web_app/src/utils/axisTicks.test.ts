import { describe, expect, it } from 'vitest'
import { labelWidth, pickAxisTicks, pickYearTicks, AXIS_LABEL_GAP } from './axisTicks'
import { timelinePads } from './storyTimeline'

const range = (a: number, b: number) => Array.from({ length: b - a + 1 }, (_, i) => a + i)
/** The Meetings-over-time plot width at a chart width, with the milestone lanes on the right. */
const plotAt = (w: number) => {
  const { padL, padR } = timelinePads(w, true)
  return w - padL - padR
}
/** No two printed labels closer than a label plus the gap. */
function assertApart(years: number[], picked: number[], plot: number) {
  const slot = plot / years.length
  for (let i = 1; i < picked.length; i++) {
    expect((picked[i]! - picked[i - 1]!) * slot).toBeGreaterThanOrEqual(labelWidth(4) + AXIS_LABEL_GAP)
  }
}

describe('pickYearTicks', () => {
  const eleven = range(2016, 2026)

  it('labels every other year of 2016–2026 on a 320px phone, first and last kept', () => {
    const t = pickYearTicks(eleven, plotAt(320))
    expect(t).toEqual([2016, 2018, 2020, 2022, 2024, 2026])
    assertApart(eleven, t, plotAt(320))
  })

  it('labels every other year on a 412px phone (the owner’s Pixel)', () => {
    const t = pickYearTicks(eleven, plotAt(412))
    expect(t[0]).toBe(2016)
    expect(t[t.length - 1]).toBe(2026)
    expect(t.length).toBeLessThan(eleven.length)
    assertApart(eleven, t, plotAt(412))
  })

  it('labels every year at 768px, where there is room', () => {
    expect(pickYearTicks(eleven, plotAt(768))).toEqual(eleven)
  })

  it('steps by five over twenty years on a phone, and drops a stepped label that would crowd the last', () => {
    const twenty = range(2007, 2026)
    const t = pickYearTicks(twenty, plotAt(412))
    expect(t).toEqual([2007, 2012, 2017, 2022, 2026])
    assertApart(twenty, t, plotAt(412))
  })

  it('keeps both years of a two-year axis', () => {
    expect(pickYearTicks([2025, 2026], plotAt(320))).toEqual([2025, 2026])
  })

  it('never overlaps at any phone-to-desktop width', () => {
    for (const n of [2, 5, 11, 20, 30]) {
      const ys = range(2026 - n + 1, 2026)
      for (let w = 280; w <= 1200; w += 7) {
        const t = pickYearTicks(ys, plotAt(w))
        expect(t[t.length - 1]).toBe(2026)
        assertApart(ys, t, plotAt(w))
      }
    }
  })
})

describe('pickAxisTicks', () => {
  it('keeps all five % labels when there is room, every other one when tight', () => {
    expect(pickAxisTicks(5, 80, 4)).toEqual([0, 1, 2, 3, 4])
    expect(pickAxisTicks(5, 25, 4)).toEqual([0, 2, 4])
  })
  it('prints only the last label when even the ends collide', () => {
    expect(pickAxisTicks(3, 5, 4)).toEqual([2])
  })
})
