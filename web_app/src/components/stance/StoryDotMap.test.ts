import { describe, expect, it } from 'vitest'
import { meetingColor } from '../../lib/dotMatrix'

const RAMP = ['#1', '#2', '#3', '#4']
const EMPTY = '#e'

describe('meetingColor (#970 Overview dot map)', () => {
  it('leaves a state with no count, or zero, in the empty colour', () => {
    expect(meetingColor(undefined, 122, RAMP, EMPTY)).toBe(EMPTY)
    expect(meetingColor(null, 122, RAMP, EMPTY)).toBe(EMPTY)
    expect(meetingColor(0, 122, RAMP, EMPTY)).toBe(EMPTY)
    expect(meetingColor(5, 0, RAMP, EMPTY)).toBe(EMPTY)
  })

  it('gives the largest count the strongest step and small counts a light one', () => {
    expect(meetingColor(122, 122, RAMP, EMPTY)).toBe('#4')
    expect(meetingColor(1, 122, RAMP, EMPTY)).toBe('#1')
  })

  it('is monotonic: more meetings never get a lighter step', () => {
    const steps = [1, 3, 10, 30, 60, 122].map((n) => RAMP.indexOf(meetingColor(n, 122, RAMP, EMPTY)))
    expect([...steps].sort((a, b) => a - b)).toEqual(steps)
  })

  it('shades a single state with a count fully', () => {
    expect(meetingColor(71, 71, RAMP, EMPTY)).toBe('#4')
    expect(meetingColor(1, 1, RAMP, EMPTY)).toBe('#4')
  })
})
