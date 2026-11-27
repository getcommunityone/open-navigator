import { describe, expect, it } from 'vitest'
import { coverageText } from './coverageLine'
import type { RecordedCoverageResponse } from '../api/sitesTimeline'

const cov = (governments: number | null, meetings: number | null, states: number | null = 1, available = true) =>
  ({ scope: { level: 'state' }, available, governments, meetings, states }) as RecordedCoverageResponse

describe('coverageText (#1348)', () => {
  it('states the real counts for a state, with the caveat, and a short phone form', () => {
    expect(coverageText(cov(29, 1035), { stateCode: 'FL', stateName: 'Florida', city: null })).toEqual({
      full: "From recordings of 29 Florida local governments (1,035 meetings). Many Florida governments aren't in our recordings yet.",
      short: "From 29 FL governments' recordings (1,035 meetings); many aren't in yet.",
    })
  })

  it('names the states nationally', () => {
    expect(coverageText(cov(2061, 137661, 45), { stateName: null, city: null })!.full).toBe(
      "From recordings of 2,061 local governments in 45 states (137,661 meetings). Many governments aren't in our recordings yet.",
    )
  })

  it('a city counts the governments named for it, singular when one', () => {
    expect(coverageText(cov(1, 1), { stateCode: 'AL', stateName: 'Alabama', city: 'Tuscaloosa' })).toEqual({
      full: 'From recordings of 1 Tuscaloosa local government (1 meeting).',
      short: 'Recorded: 1 meeting.',
    })
  })

  it('says so when no government is recorded, never a zero count', () => {
    expect(coverageText(cov(0, 0), { stateCode: 'WY', stateName: 'Wyoming', city: null })!.full).toBe(
      'No Wyoming local government is in our meeting recordings yet.',
    )
  })

  it('is null when the counts are unavailable', () => {
    expect(coverageText(cov(null, null, null, false), { stateCode: 'FL', stateName: 'Florida', city: null })).toBeNull()
    expect(coverageText(undefined, { stateName: null, city: null })).toBeNull()
  })
})
