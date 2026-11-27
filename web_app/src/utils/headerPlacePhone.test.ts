import { describe, expect, it } from 'vitest'
import { phonePlaceState, searchForScope } from './headerPlace'

// #1301: the phone header's location selector. Saved places here are test stand-ins, not anyone's data.
const sp = (s: string) => new URLSearchParams(s)
const tus = { state: 'AL', city: 'Tuscaloosa' }

describe('phonePlaceState', () => {
  it('no saved town and no place in the URL: the pin + ZIP field', () => {
    expect(phonePlaceState('/', sp(''), null)).toEqual({ mode: 'zip' })
    expect(phonePlaceState('/stories/data-centers', sp(''), null)).toEqual({ mode: 'zip' })
    expect(phonePlaceState('/how-it-works', sp(''), undefined)).toEqual({ mode: 'zip' })
  })

  it('a scope-aware page: the toggle shows which side the URL is on', () => {
    expect(phonePlaceState('/stories/data-centers', sp('state=AL&city=Tuscaloosa'), tus)).toEqual({
      mode: 'toggle', place: 'Tuscaloosa, AL', active: 'place', canToggle: true,
    })
    expect(phonePlaceState('/stories/data-centers', sp(''), tus)).toEqual({
      mode: 'toggle', place: 'Tuscaloosa, AL', active: 'national', canToggle: true,
    })
    // A deep link to a place with nothing saved still shows that place, and can go national.
    expect(phonePlaceState('/search', sp('state=GA'), null)).toEqual({ mode: 'toggle', place: 'GA', active: 'place', canToggle: true })
  })

  it('home: ?scope=national is the National side; the saved town is kept', () => {
    expect(phonePlaceState('/', sp(''), tus)).toMatchObject({ active: 'place', canToggle: true, place: 'Tuscaloosa, AL' })
    expect(phonePlaceState('/', sp('scope=national'), tus)).toMatchObject({ active: 'national', canToggle: true, place: 'Tuscaloosa, AL' })
  })

  it('a page with no place scope: the town chip only, nothing to toggle', () => {
    expect(phonePlaceState('/how-it-works', sp(''), tus)).toEqual({ mode: 'toggle', place: 'Tuscaloosa, AL', active: 'place', canToggle: false })
  })
})

describe('searchForScope: one tap there and back, no retyping', () => {
  it('scope-aware page: National clears ?state=&city=, the town side writes the saved town back', () => {
    const start = sp('state=AL&city=Tuscaloosa&tab=x&page=3')
    const national = searchForScope('/stories/data-centers', start, 'national', tus)
    expect(national.toString()).toBe('tab=x')
    const back = searchForScope('/stories/data-centers', national, 'place', tus)
    expect(back.get('state')).toBe('AL')
    expect(back.get('city')).toBe('Tuscaloosa')
    expect(back.get('tab')).toBe('x')
    expect(phonePlaceState('/stories/data-centers', back, tus)).toMatchObject({ active: 'place' })
  })

  it('home: National sets ?scope=national and the town side removes it', () => {
    const national = searchForScope('/', sp(''), 'national', tus)
    expect(national.toString()).toBe('scope=national')
    expect(searchForScope('/', national, 'place', tus).toString()).toBe('')
  })

  it('a state-only saved place writes no city', () => {
    expect(searchForScope('/search', sp(''), 'place', { state: 'AL', city: null }).toString()).toBe('state=AL')
  })

  it('a page with no place scope is left alone', () => {
    expect(searchForScope('/how-it-works', sp('a=1'), 'national', tus).toString()).toBe('a=1')
  })
})
