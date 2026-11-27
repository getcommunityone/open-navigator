import { describe, expect, it } from 'vitest'
import { handCountLine, heroPoints, plural } from './heroPoints'

// Test-only counts: nothing here is served by the app.
const lean = {
  public_against_meetings: 1234,
  public_against_states: 17,
  stopped_meetings: 42,
  disagreement_meetings: 9,
  disagreement_states: 4,
}
const speakers = { speakers_for: 100, speakers_against: 1900, speakers_question: 10, speakers_neutral: 5 }

describe('heroPoints', () => {
  it('builds three numbered points with thousands separators', () => {
    const p = heroPoints(lean, speakers)
    expect(p.map((x) => [x.n, x.icon, x.title])).toEqual([
      [1, 'quote', 'Communities are saying no.'],
      [2, 'stop', 'Projects are being stopped.'],
      [3, 'scale', "Officials don't always listen."],
    ])
    // Short, so it never repeats the title's basis line word for word (#1134).
    expect(p[0]!.line).toBe('1,234 meetings across 17 states where the public mostly opposed data centers.')
    expect(p[1]!.line).toBe('42 meetings tabled, denied or paused a data center.')
    expect(p[2]!.line).toBe('Officials sided against the public in 9 meetings across 4 states.')
  })

  it('uses singular forms for 1', () => {
    const p = heroPoints(
      { public_against_meetings: 1, public_against_states: 1, stopped_meetings: 1, disagreement_meetings: 1, disagreement_states: 1 },
      { speakers_against: 1 },
    )
    expect(p[0]!.line).toBe('1 meeting across 1 state where the public mostly opposed data centers.')
    expect(p[1]!.line).toBe('1 meeting tabled, denied or paused a data center.')
    expect(p[2]!.line).toBe('Officials sided against the public in 1 meeting across 1 state.')
  })

  it('leaves out points without data and renumbers', () => {
    const p = heroPoints({ ...lean, stopped_meetings: 0 }, speakers)
    expect(p.map((x) => [x.n, x.icon])).toEqual([
      [1, 'quote'],
      [2, 'scale'],
    ])
  })

  it('returns nothing when lean totals are null and no speakers are counted', () => {
    expect(heroPoints(null, null)).toEqual([])
    expect(heroPoints(null, { speakers_for: 0, speakers_against: 0 })).toEqual([])
  })

  it('uses the hand count, with its states, when the AI readings are missing', () => {
    const p = heroPoints(null, speakers, { speakerStates: 4 })
    expect(p).toHaveLength(1)
    expect(p[0]!.line).toBe('2,015 speakers counted by hand in 4 states: 1,900 against and 100 for.')
  })

  // #1134: a place's own figure where it has one, otherwise the national one marked "Nationally:".
  it("uses the place's own figures and marks national ones", () => {
    const p = heroPoints(lean, speakers, {
      place: { label: 'Arizona', lean: { public_against_meetings: 14, stopped_meetings: 0, disagreement_meetings: 1 }, speakers: null },
    })
    expect(p.map((x) => x.line)).toEqual([
      '14 meetings in Arizona where the public mostly opposed data centers.',
      'Nationally: 42 meetings tabled, denied or paused a data center.',
      'Officials sided against the public in 1 meeting in Arizona.',
    ])
  })
  it("falls back to the place's hand count, then to the national reading", () => {
    const p = heroPoints(lean, speakers, { place: { label: 'Texas', lean: null, speakers: { speakers_for: 2, speakers_against: 1, speakers_neutral: 3 } } })
    expect(p[0]!.line).toBe('6 speakers counted by hand in Texas: 2 for and 1 against.')
    const q = heroPoints(lean, speakers, { place: { label: 'Tuscaloosa, Alabama', lean: { public_against_meetings: 0 }, speakers: null } })
    expect(q.every((x) => x.line.startsWith('Nationally: '))).toBe(true)
  })
})

describe('handCountLine never states a zero side (#1134)', () => {
  it('drops zero for, zero against, and leads with the larger side', () => {
    expect(handCountLine({ speakers_for: 0, speakers_against: 11, speakers_question: 1 }, ' in Arizona')).toBe(
      '12 speakers counted by hand in Arizona: 11 against.',
    )
    expect(handCountLine({ speakers_for: 4, speakers_against: 0 }, '')).toBe('4 speakers counted by hand: 4 for.')
    expect(handCountLine({ speakers_for: 2, speakers_against: 1, speakers_question: 0 }, '')).toBe('3 speakers counted by hand: 2 for and 1 against.')
  })
  it('says only the count when no one took a side, and nothing when all are zero', () => {
    expect(handCountLine({ speakers_question: 2, speakers_neutral: 1 }, '')).toBe('3 speakers counted by hand.')
    expect(handCountLine({ speakers_for: 0, speakers_against: 0, speakers_question: 0, speakers_neutral: 0 }, '')).toBeNull()
  })
})

describe('plural', () => {
  it('formats counts', () => {
    expect(plural(0, 'meeting')).toBe('0 meetings')
    expect(plural(1, 'state')).toBe('1 state')
    expect(plural(12345, 'speaker')).toBe('12,345 speakers')
  })
})
