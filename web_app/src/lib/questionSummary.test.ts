import { describe, expect, it } from 'vitest'
import { monthYear, questionSummary, type SummaryRollup } from './questionSummary'

const national: SummaryRollup = {
  instances_total: 25,
  bills_total: 0,
  jurisdictions_total: 15,
  states_total: 4,
  approved_count: 5,
  denied_count: 1,
  moratorium_count: 4,
  deferred_count: 5,
  other_count: 10,
  first_occurred_at: '2026-05-28T13:00:00Z',
}

describe('questionSummary', () => {
  it('states the real counts, places, start month and breakdown', () => {
    expect(questionSummary(national, { meetings: 1270 })).toBe(
      '25 decisions in 15 governments across 4 states since May 2026: 5 approved, 1 denied, 4 moratoriums, 5 deferred, 10 other. Discussed in 1,270 meetings.',
    )
  })

  it('drops the state count inside one state and leaves zero families out', () => {
    const ga = { ...national, instances_total: 3, jurisdictions_total: 1, states_total: 1, approved_count: 0, denied_count: 0, moratorium_count: 1, deferred_count: 0, other_count: 2 }
    expect(questionSummary(ga)).toBe('3 decisions in 1 government since May 2026: 1 moratorium, 2 other.')
  })

  it('names the outcome family when one is selected', () => {
    const approved = { ...national, instances_total: 5, jurisdictions_total: 3, states_total: 2 }
    expect(questionSummary(approved, { outcome: 'approved', meetings: 104 })).toBe(
      '5 approved decisions in 3 governments across 2 states since May 2026. The question was discussed in 104 meetings.',
    )
    expect(questionSummary({ ...approved, instances_total: 1 }, { outcome: 'moratorium' })).toMatch(/^1 moratorium in/)
  })

  it('says so when the scope has nothing, without inventing numbers', () => {
    expect(questionSummary({ ...national, instances_total: 0 }, { meetings: 3 })).toBe(
      'No decisions recorded yet in this scope. Discussed in 3 meetings.',
    )
    expect(questionSummary(undefined, { outcome: 'moratorium' })).toBe('No moratoriums recorded yet in this scope.')
  })

  it('formats month-year in UTC and tolerates bad dates', () => {
    expect(monthYear('2026-06-01')).toBe('Jun 2026')
    expect(monthYear('nope')).toBeNull()
    expect(monthYear(null)).toBeNull()
  })
})
