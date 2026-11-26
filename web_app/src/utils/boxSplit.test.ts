import { describe, expect, it } from 'vitest'
import { bandSides, speakersOf, splitBoxes } from './boxSplit'

const s = (f: number, a: number, q: number, n: number) => ({ speakers_for: f, speakers_against: a, speakers_question: q, speakers_neutral: n })

describe('splitBoxes', () => {
  it('sums to the box total and follows the real proportions', () => {
    const out = splitBoxes(s(0, 11, 1, 0), 120)
    expect(out.against + out.for + out.question + out.neutral).toBe(120)
    expect(out.against).toBe(110)
    expect(out.question).toBe(10)
    expect(out.for).toBe(0)
    expect(out.neutral).toBe(0)
  })

  it('gives every side with a speaker at least one box when there are enough boxes', () => {
    const out = splitBoxes(s(1, 200, 0, 0), 20)
    expect(out.for).toBe(1)
    expect(out.against).toBe(19)
  })

  it('splits evenly with largest remainder', () => {
    const out = splitBoxes(s(1, 1, 0, 1), 10)
    expect(out.for + out.against + out.neutral).toBe(10)
    expect(Math.max(out.for, out.against, out.neutral) - Math.min(out.for, out.against, out.neutral)).toBeLessThanOrEqual(1)
  })

  it('never splits without speakers or boxes', () => {
    expect(splitBoxes(s(0, 0, 0, 0), 30)).toEqual({ against: 0, for: 0, question: 0, neutral: 0 })
    expect(splitBoxes(null, 30)).toEqual({ against: 0, for: 0, question: 0, neutral: 0 })
    expect(splitBoxes(s(1, 1, 0, 0), 0)).toEqual({ against: 0, for: 0, question: 0, neutral: 0 })
  })

  it('a single box goes to the larger side', () => {
    const out = splitBoxes(s(1, 3, 0, 0), 1)
    expect(out).toEqual({ against: 1, for: 0, question: 0, neutral: 0 })
  })
})

describe('bandSides', () => {
  it('fills contiguous bands in drawing order', () => {
    expect(bandSides(s(2, 1, 0, 3), 6)).toEqual(['against', 'for', 'for', 'neutral', 'neutral', 'neutral'])
  })
  it('is all null without speakers', () => {
    expect(bandSides(undefined, 3)).toEqual([null, null, null])
  })
})

describe('speakersOf', () => {
  it('adds the four sides', () => {
    expect(speakersOf(s(2, 1, 0, 3))).toBe(6)
    expect(speakersOf(null)).toBe(0)
  })
})
