import { describe, expect, it } from 'vitest'
import { headerPlace, headerPlaceLabel, searchAfterPick } from './headerPlace'

const sp = (s: string) => new URLSearchParams(s)

describe('headerPlace', () => {
  it('prefers the place in the URL', () => {
    expect(headerPlace(sp('state=al&city=Tuscaloosa'), { state: 'MA', city: 'Boston' })).toEqual({ stateCode: 'AL', city: 'Tuscaloosa' })
  })
  it('falls back to the saved location, and to none', () => {
    expect(headerPlace(sp('q=x'), { state: 'MA', city: 'Boston' })).toEqual({ stateCode: 'MA', city: 'Boston' })
    expect(headerPlace(sp('state=ZZ'), null)).toBeNull()
    expect(headerPlace(sp(''), { state: '', city: '' })).toBeNull()
  })
  it('labels city and state, or the state alone', () => {
    expect(headerPlaceLabel({ stateCode: 'AL', city: 'Tuscaloosa' })).toBe('Tuscaloosa, AL')
    expect(headerPlaceLabel({ stateCode: 'AL', city: null })).toBe('AL')
    expect(headerPlaceLabel(null)).toBeNull()
  })
})

describe('searchAfterPick', () => {
  it('writes the pick into the URL off home, keeping other params and resetting the page', () => {
    expect(searchAfterPick('/search', sp('q=fluoride&page=3&state=MA'), { state: 'AL', city: 'Tuscaloosa' }).toString()).toBe(
      'q=fluoride&state=AL&city=Tuscaloosa',
    )
    expect(searchAfterPick('/search', sp('city=Boston'), { state: 'AL', city: '' }).toString()).toBe('state=AL')
  })
  it('clears the carried place on home', () => {
    expect(searchAfterPick('/', sp('state=MA&city=Boston'), { state: 'AL', city: 'Tuscaloosa' }).toString()).toBe('')
  })
})
