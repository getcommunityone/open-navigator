import { describe, expect, it } from 'vitest'
import { filterOptions, groupOptions, moveActive, pickRandom, typeAhead, type PickerOption } from './sentenceHeading'

const opts: PickerOption[] = [
  { value: 'pop', label: 'Population', group: 'People', hint: '5.1M median' },
  { value: 'age', label: 'Median age', group: 'People', hint: '38.6 yrs median' },
  { value: 'inc', label: 'Median household income', group: 'Money', hint: '$72.1K median' },
]

describe('filterOptions', () => {
  it('keeps everything for an empty query', () => {
    expect(filterOptions(opts, '  ')).toEqual(opts)
  })
  it('matches every word in label, group or hint, ignoring case', () => {
    expect(filterOptions(opts, 'MEDIAN').map((o) => o.value)).toEqual(['pop', 'age', 'inc'])
    expect(filterOptions(opts, 'median money').map((o) => o.value)).toEqual(['inc'])
    expect(filterOptions(opts, '$72').map((o) => o.value)).toEqual(['inc'])
    expect(filterOptions(opts, 'zzz')).toEqual([])
  })
})

describe('groupOptions', () => {
  it('groups in first-seen order and keeps a flat list as one unnamed group', () => {
    expect(groupOptions(opts).map((g) => [g.group, g.items.length])).toEqual([['People', 2], ['Money', 1]])
    expect(groupOptions(opts.map(({ group: _g, ...o }) => o))).toHaveLength(1)
    expect(groupOptions([])).toEqual([])
  })
})

describe('moveActive', () => {
  it('moves, stops at the ends and jumps', () => {
    expect(moveActive(0, 1, 3)).toBe(1)
    expect(moveActive(2, 1, 3)).toBe(2)
    expect(moveActive(0, -1, 3)).toBe(0)
    expect(moveActive(-1, 1, 3)).toBe(0)
    expect(moveActive(-1, -1, 3)).toBe(2)
    expect(moveActive(1, 'first', 3)).toBe(0)
    expect(moveActive(1, 'last', 3)).toBe(2)
    expect(moveActive(0, 1, 0)).toBe(-1)
  })
})

describe('typeAhead', () => {
  it('finds the next label that starts with the typed text, wrapping', () => {
    expect(typeAhead(opts, 'me', 0)).toBe(1)
    expect(typeAhead(opts, 'me', 2)).toBe(2)
    expect(typeAhead(opts, 'po', 1)).toBe(0)
    expect(typeAhead(opts, 'x', 0)).toBe(-1)
    expect(typeAhead(opts, '', 0)).toBe(-1)
  })
})

describe('pickRandom', () => {
  const c = [{ value: 'a' }, { value: 'b' }, { value: 'c' }]
  it('never returns the current choice', () => {
    expect(pickRandom(c, 'a', () => 0)?.value).toBe('b')
    expect(pickRandom(c, 'a', () => 0.99)?.value).toBe('c')
    for (let i = 0; i < 20; i++) expect(pickRandom(c, 'b')?.value).not.toBe('b')
  })
  it('is null when there is nothing else', () => {
    expect(pickRandom([{ value: 'a' }], 'a')).toBeNull()
    expect(pickRandom([], 'a')).toBeNull()
  })
})
