import { describe, expect, it } from 'vitest'
import { MIN_SCOPE_MEETINGS, resolveStoryScope, scopeForLevel } from './resolveStoryScope'

// Test-only places and counts: nothing here is served by the app.
const base = { topic: 'data centers', stateCode: 'AL', stateName: 'Alabama' }

describe('resolveStoryScope', () => {
  it('needs 5 meetings for a place of its own', () => {
    expect(MIN_SCOPE_MEETINGS).toBe(5)
  })
  it('national stays national', () => {
    const r = resolveStoryScope({ topic: 'data centers' })
    expect(r).toMatchObject({ asked: 'national', level: 'national', reason: null })
  })
  it('a city with enough meetings speaks for itself', () => {
    const r = resolveStoryScope({ ...base, city: 'Testville', cityMeetings: 5, stateMeetings: 70 })
    expect(r).toMatchObject({ asked: 'city', level: 'city', city: 'Testville', meetings: 5, reason: null })
  })
  it('keeps the city while its count is unknown', () => {
    expect(resolveStoryScope({ ...base, city: 'Testville', cityMeetings: null }).level).toBe('city')
  })
  it('city → county when the county has enough', () => {
    const r = resolveStoryScope({ ...base, city: 'Testville', cityMeetings: 2, county: { name: 'Test County', meetings: 7 }, stateMeetings: 70 })
    expect(r).toMatchObject({ level: 'county', county: 'Test County', meetings: 7, city: null, stateCode: 'AL' })
    expect(r.reason).toBe('Testville has only 2 meetings on data centers, too few to call, so this shows Test County (7 meetings).')
  })
  it('city → state when the county is short too', () => {
    const r = resolveStoryScope({ ...base, city: 'Testville', cityMeetings: 1, county: { name: 'Test County', meetings: 3 }, stateMeetings: 70 })
    expect(r).toMatchObject({ level: 'state', stateCode: 'AL', meetings: 70 })
    expect(r.reason).toBe(
      'Testville has only 1 meeting on data centers, too few to call (Test County has 3 meetings), so this shows Alabama (70 meetings).',
    )
  })
  it('city → state, saying so, when the topic has no county grain', () => {
    const r = resolveStoryScope({ ...base, city: 'Testville', cityMeetings: 2, county: 'unavailable', stateMeetings: 70 })
    expect(r.level).toBe('state')
    expect(r.reason).toBe(
      "Testville has only 2 meetings on data centers, too few to call. County counts aren't on record for this topic, so this shows Alabama (70 meetings).",
    )
  })
  it('city → national when the state is short too', () => {
    const r = resolveStoryScope({ ...base, city: 'Testville', cityMeetings: 0, county: 'unavailable', stateMeetings: 3 })
    expect(r).toMatchObject({ level: 'national', stateCode: null })
    expect(r.reason).toContain('Testville has no meetings on data centers')
    expect(r.reason).toContain('Alabama has only 3 meetings, so this shows the whole country.')
  })
  it('state → national when the state is short', () => {
    const r = resolveStoryScope({ ...base, stateMeetings: 4 })
    expect(r).toMatchObject({ asked: 'state', level: 'national' })
    expect(r.reason).toBe('Alabama has only 4 meetings on data centers, too few to call, so this shows the whole country.')
  })
  it('a state with enough stays', () => {
    expect(resolveStoryScope({ ...base, stateMeetings: 5 })).toMatchObject({ level: 'state', reason: null })
  })
  it('scopeForLevel gives the queries their scope', () => {
    expect(scopeForLevel(resolveStoryScope({ ...base, city: 'Testville', cityMeetings: 9 }))).toEqual({ stateCode: 'AL', stateName: 'Alabama', city: 'Testville' })
    expect(scopeForLevel(resolveStoryScope({ ...base, city: 'Testville', cityMeetings: 1, stateMeetings: 70 }))).toEqual({ stateCode: 'AL', stateName: 'Alabama', city: null })
    expect(scopeForLevel(resolveStoryScope({ ...base, stateMeetings: 1 }))).toEqual({ stateCode: undefined, stateName: null, city: null })
  })
})
