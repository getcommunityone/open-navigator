import { describe, expect, it } from 'vitest'
import { closeDestination, previousEntry, recordLocation, showsPageClose } from './pageClose'

const cur = (search = '', pathname = '/browse-topics/all') => ({ pathname, search })

describe('closeDestination', () => {
  it('goes home keeping the city scope and topic when there is no history', () => {
    expect(closeDestination(cur('?state=AL&city=Tuscaloosa&topic=fluoride&x=1'), null)).toEqual({
      kind: 'to',
      to: '/?state=AL&city=Tuscaloosa&topic=fluoride',
      label: 'home',
    })
  })
  it('keeps the national scope', () => {
    expect(closeDestination(cur('?scope=national'), null)).toMatchObject({ to: '/?scope=national' })
  })
  it('goes home bare when there is no scope', () => {
    expect(closeDestination(cur(''), null)).toMatchObject({ to: '/' })
  })
  it('goes back when the previous entry is ours and the scope matches', () => {
    expect(closeDestination(cur('?state=AL'), { pathname: '/search', search: '?state=AL&q=x' })).toEqual({
      kind: 'back',
      label: 'search results',
    })
  })
  it('goes back when this page carries no scope', () => {
    expect(closeDestination(cur(''), { pathname: '/', search: '?state=AL' }).kind).toBe('back')
  })
  it('applies the current scope when the place changed on this page', () => {
    expect(closeDestination(cur('?state=GA&city=Atlanta'), { pathname: '/search', search: '?state=AL&city=Tuscaloosa&q=x' })).toMatchObject({
      kind: 'to',
      to: '/search?q=x&state=GA&city=Atlanta',
    })
  })
  it('does not go back to the same page', () => {
    expect(closeDestination(cur('?state=AL'), { pathname: '/browse-topics/all', search: '' })).toMatchObject({ to: '/?state=AL' })
  })
})

describe('trail', () => {
  it('knows the entry before an index and nothing before the first', () => {
    recordLocation({ pathname: '/a', search: '?s=1' }, 4)
    expect(previousEntry(5)).toEqual({ pathname: '/a', search: '?s=1' })
    expect(previousEntry(0)).toBeNull()
    expect(previousEntry(9)).toBeNull()
  })
})

describe('showsPageClose', () => {
  it('skips stories and home', () => {
    expect(showsPageClose('/stories/data-centers')).toBe(false)
    expect(showsPageClose('/')).toBe(false)
    expect(showsPageClose('/settings')).toBe(false)
    expect(showsPageClose('/stories')).toBe(true)
    expect(showsPageClose('/decisions/12')).toBe(true)
  })
})
