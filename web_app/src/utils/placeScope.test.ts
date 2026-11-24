import { describe, expect, it } from 'vitest'
import { countyNotice, placeToScope } from './placeScope'

describe('placeToScope', () => {
  it('keeps a city with its state', () => {
    expect(placeToScope({ state: 'AL', city: 'Tuscaloosa', county: 'Tuscaloosa County' })).toEqual({
      stateCode: 'AL',
      city: 'Tuscaloosa',
      countyOnly: false,
      county: 'Tuscaloosa County',
    })
  })
  it('falls back to the state for a county pick', () => {
    const s = placeToScope({ state: 'al', city: '', county: 'Jefferson County' })
    expect(s).toMatchObject({ stateCode: 'AL', city: null, countyOnly: true })
    expect(countyNotice(s!)).toBe('Jefferson County has no city of its own here. Stories are told by city or state; showing all of Alabama.')
  })
  it('adds County to a bare county name', () => {
    expect(countyNotice(placeToScope({ state: 'GA', county: 'Fulton' })!)).toMatch(/^Fulton County has/)
  })
  it('returns null without a US state', () => {
    expect(placeToScope({ city: 'Paris' })).toBeNull()
    expect(placeToScope({ state: 'ZZ', city: 'X' })).toBeNull()
    expect(placeToScope(null)).toBeNull()
    expect(countyNotice(placeToScope({ state: 'AL', city: 'Mobile' })!)).toBeNull()
  })
})
