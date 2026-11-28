import { describe, expect, it } from 'vitest'
import { headerPlace, headerPlaceLabel, headerPlaceState, isScopeAwarePath, searchAfterPick, searchForNational, searchForScope } from './headerPlace'

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

describe('headerPlaceState (#1205)', () => {
  const saved = { state: 'AL', city: 'Tuscaloosa' }
  it('names the URL place on a scope-aware page', () => {
    expect(headerPlaceState('/stories/guns', sp('state=AL&city=Tuscaloosa'), { state: 'MA', city: 'Boston' })).toEqual({
      kind: 'scoped',
      place: { stateCode: 'AL', city: 'Tuscaloosa' },
    })
  })
  it('says National and offers the saved town when the page has no place', () => {
    expect(headerPlaceState('/stories/guns', sp(''), saved)).toEqual({ kind: 'national-saved', saved: { stateCode: 'AL', city: 'Tuscaloosa' } })
    expect(headerPlaceState('/search', sp('q=fluoride'), saved).kind).toBe('national-saved')
  })
  it('says National with no saved town', () => {
    expect(headerPlaceState('/jurisdictions', sp(''), null)).toEqual({ kind: 'national' })
  })
  it('keeps the town label on home and on pages that are not scope-aware', () => {
    expect(headerPlaceState('/', sp(''), saved)).toEqual({ kind: 'town', place: { stateCode: 'AL', city: 'Tuscaloosa' } })
    expect(headerPlaceState('/settings', sp(''), null)).toEqual({ kind: 'town', place: null })
    expect(headerPlaceState('/jurisdiction/0177256/meetings', sp(''), saved).kind).toBe('town')
  })
  it('matches scope-aware routes exactly', () => {
    expect(isScopeAwarePath('/stories')).toBe(true)
    expect(isScopeAwarePath('/stories/')).toBe(true)
    expect(isScopeAwarePath('/stories-old')).toBe(false)
    expect(isScopeAwarePath('/browse-topics')).toBe(true)
    expect(isScopeAwarePath('/profile')).toBe(false)
  })
})

describe('National in one click (#1285)', () => {
  it('home adds scope=national and keeps the place; the header then says National with the place offered back', async () => {
    const { searchForNational } = await import('./headerPlace')
    expect(searchForNational('/', sp('state=AL&city=Tuscaloosa'), true)?.toString()).toBe('state=AL&city=Tuscaloosa&scope=national')
    expect(searchForNational('/', sp(''), false)).toBeNull()
    expect(headerPlaceState('/', sp('scope=national'), { state: 'AL', city: 'Tuscaloosa' })).toEqual({
      kind: 'national-saved',
      saved: { stateCode: 'AL', city: 'Tuscaloosa' },
    })
  })
  it('a scoped page drops the place', async () => {
    const { searchForNational } = await import('./headerPlace')
    expect(searchForNational('/stories/data-centers', sp('state=AL&city=Tuscaloosa&screen=overview'), true)?.toString()).toBe('screen=overview')
    expect(searchForNational('/stories/data-centers', sp('screen=overview'), true)).toBeNull()
  })
  it('a pick clears scope=national', () => {
    expect(searchAfterPick('/', sp('scope=national'), { state: 'AL', city: 'Tuscaloosa' }).toString()).toBe('')
  })
})

describe('a place change on a story starts it over (#1463)', () => {
  it('sets ?screen=overview on National, a pick and the scope toggle', () => {
    expect(searchForNational('/stories/data-centers', sp('state=AL&screen=sites'), true)?.toString()).toBe('screen=overview')
    expect(searchAfterPick('/stories/data-centers', sp('state=AL&screen=sites'), { state: 'MA', city: 'Boston' }).toString()).toBe('screen=overview&state=MA&city=Boston')
    expect(searchForScope('/stories/data-centers', sp('state=AL&screen=sites'), 'national', null).toString()).toBe('screen=overview')
  })
  it('keeps ?screen= elsewhere', () => {
    expect(searchForNational('/search', sp('state=AL&screen=x'), true)?.toString()).toBe('screen=x')
  })
})
