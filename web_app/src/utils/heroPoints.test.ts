import { describe, expect, it } from 'vitest'
import { heroPoints, plural } from './heroPoints'

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
    expect(p[0]!.line).toBe(
      'The public leaned against data centers in 1,234 meetings across 17 states (AI reading of meetings). Of 2,015 speakers counted, 1,900 spoke against.',
    )
    expect(p[1]!.line).toBe('42 meetings tabled, denied or paused a data center (AI reading).')
    expect(p[2]!.line).toBe('Officials sided against the public in 9 meetings across 4 states (AI reading).')
  })

  it('uses singular forms for 1', () => {
    const p = heroPoints(
      { public_against_meetings: 1, public_against_states: 1, stopped_meetings: 1, disagreement_meetings: 1, disagreement_states: 1 },
      { speakers_against: 1 },
    )
    expect(p[0]!.line).toBe('The public leaned against data centers in 1 meeting across 1 state (AI reading of meetings). Of 1 speaker counted, 1 spoke against.')
    expect(p[1]!.line).toBe('1 meeting tabled, denied or paused a data center (AI reading).')
    expect(p[2]!.line).toBe('Officials sided against the public in 1 meeting across 1 state (AI reading).')
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

  it('keeps only the speaker sentence when the AI readings are missing', () => {
    const p = heroPoints(null, speakers)
    expect(p).toHaveLength(1)
    expect(p[0]!.line).toBe('Of 2,015 speakers counted, 1,900 spoke against.')
  })

  it('keeps only the lean sentence when no speakers are counted', () => {
    const p = heroPoints(lean, null)
    expect(p[0]!.line).toBe('The public leaned against data centers in 1,234 meetings across 17 states (AI reading of meetings).')
  })
})

describe('plural', () => {
  it('formats counts', () => {
    expect(plural(0, 'meeting')).toBe('0 meetings')
    expect(plural(1, 'state')).toBe('1 state')
    expect(plural(12345, 'speaker')).toBe('12,345 speakers')
  })
})
