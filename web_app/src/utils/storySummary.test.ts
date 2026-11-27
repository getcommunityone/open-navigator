import { describe, expect, it } from 'vitest'
import { summaryFacts } from './storySummary'

const scope = { stateCode: 'AL', stateName: 'Alabama', city: null }
const stats = [{ key: 'meetings', value: 71, label: 'x' }] as never

describe('summaryFacts', () => {
  it('states the meeting count and leaves out what is not loaded', () => {
    expect(summaryFacts(stats, null, scope)).toEqual(['71 meetings in Alabama mentioned data centers'])
  })
  it('adds speakers and votes from the positions table', () => {
    const positions = {
      available: true,
      totals: { speakers_for: 2, speakers_against: 6, speakers_question: 0, speakers_neutral: 0, votes_for: 8, votes_against: 1, decisions_with_tally: 1, meetings_reviewed: 8 },
    } as never
    expect(summaryFacts(stats, positions, scope)).toEqual([
      '71 meetings in Alabama mentioned data centers',
      '8 people spoke on it: 6 against, 2 for',
      'Recorded votes by officials: 8 for, 1 against',
    ])
  })
  it('says nothing for a place with no meetings', () => {
    expect(summaryFacts([], null, scope)).toEqual([])
  })
})
