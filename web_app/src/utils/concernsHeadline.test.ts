// #1139: the Concerns screen names each concern once, handles one concern and real ties, prints no zero clause, and compares
// the area with the national ranking from the real national rows.
import { describe, expect, it } from 'vitest'
import { DATA_CENTER_STORY, STORY_CHARTS, nationalConcernNote, screenText, type StoryData, type StoryScope, type StoryStatus } from './dataStory'
import { chartSpec, type DotsSpec } from './stanceGame'
import { concernColor } from './houseTheme'

const ready: StoryStatus = Object.fromEntries(STORY_CHARTS.map((k) => [k, 'ready'])) as StoryStatus
const concernsScreen = DATA_CENTER_STORY.find((s) => s.id === 'concerns')!
const nat: StoryScope = { stateName: null, city: null }
const tx: StoryScope = { stateCode: 'TX', stateName: 'Texas', city: null }
const denison: StoryScope = { stateCode: 'TX', stateName: 'Texas', city: 'Denison' }

type Row = [concern: string, mentions: number, towns?: string[]]
const rows = (xs: Row[]) => xs.map(([concern, mention_count, jurisdictions = []]) => ({ concern, mention_count, objection_count: 10, jurisdictions }))
const NATIONAL = rows([
  ['traffic', 406],
  ['water', 376],
  ['land', 253],
  ['noise', 140],
  ['pollution', 72],
  ['taxes', 69],
  ['electricity', 17],
])
const data = (items: Row[], national = NATIONAL): StoryData => ({ concerns: { items: rows(items), national } as never }) as StoryData
const text = (d: StoryData, scope: StoryScope) => screenText(concernsScreen, d, ready, scope)
const ZERO = /\b0 (mention|of)|with 0\b/

describe('concerns headline', () => {
  it('one concern in a state names its towns, once', () => {
    const t = text(data([['water', 2, ['Denison', 'Odessa']]]), tx)
    expect(t.headline).toBe('Water was the only concern raised in Texas meeting records: 2 mentions, in Denison and Odessa.')
  })

  it('merges rows for the same concern instead of calling it a tie with itself', () => {
    const t = text(data([['water', 1, ['Denison']], ['water', 1, ['Odessa']]]), tx)
    expect(t.headline).toBe('Water was the only concern raised in Texas meeting records: 2 mentions, in Denison and Odessa.')
    expect(t.headline).not.toMatch(/water and water/i)
  })

  it('does not repeat the city as the town list under a city scope', () => {
    const t = text(data([['water', 1, ['Denison']]]), denison)
    expect(t.headline).toBe('Water was the only concern raised in meeting records in Denison, Texas: 1 mention.')
  })

  it('a real tie between different concerns lists each once', () => {
    const t = text(data([['water', 3], ['noise', 3], ['traffic', 1]]), tx)
    expect(t.headline).toBe('Noise and water are tied as the most raised concerns in Texas meeting records: 3 mentions each, of 7.')
  })

  it('a clear leader names the runner-up and never a zero clause', () => {
    const t = text(data([['traffic', 6], ['water', 2], ['noise', 0]]), tx)
    expect(t.headline).toBe('Traffic is raised most in Texas meeting records: 6 of 8 mentions (75%), ahead of water with 2.')
    expect(t.headline).not.toMatch(ZERO)
    expect(t.headline).not.toMatch(/noise/)
  })

  it('compares a state with the national ranking from the national rows', () => {
    const t = text(data([['water', 2, ['Denison', 'Odessa']]]), tx)
    expect(t.context).toContain('Nationally, traffic leads, then water, then land and property.')
  })

  it('does not add a national comparison to the national screen itself', () => {
    const t = text(data([], NATIONAL), nat)
    expect(t.headline).toBe('Traffic is raised most in meeting records nationally: 406 of 1,333 mentions (30%), ahead of water with 376.')
    expect(t.context).not.toContain('Nationally,')
  })

  it('nationalConcernNote handles ties, a single row and no rows', () => {
    expect(nationalConcernNote({ items: [], national: rows([['water', 5], ['noise', 5], ['land', 1]]) } as never)).toBe('Nationally, noise and water lead, then land and property.')
    expect(nationalConcernNote({ items: [], national: rows([['water', 5]]) } as never)).toBe('Nationally, water leads.')
    expect(nationalConcernNote({ items: [], national: [] } as never)).toBeNull()
  })

  it('an empty area is not filled with national figures', () => {
    const t = text(data([]), tx)
    expect(t.headline).not.toMatch(/traffic/i)
  })
})

describe('concerns chart legend', () => {
  it('one group per concern, no empty groups, and a colour fixed by the concern', () => {
    const d = { items: rows([['water', 1, ['Denison']], ['water', 1, ['Odessa']], ['noise', 0]]), national: NATIONAL } as never
    const spec = chartSpec('concerns', d, 'Texas') as DotsSpec
    expect(spec.groups.map((g) => g.key)).toEqual(['water'])
    expect(spec.groups[0]!.total).toBe(2)
    expect(spec.groups[0]!.color).toBe(concernColor('water'))
    const nationalSpec = chartSpec('concerns', d) as DotsSpec
    expect(nationalSpec.groups.find((g) => g.key === 'water')!.color).toBe(concernColor('water'))
    expect(new Set(nationalSpec.groups.map((g) => g.color)).size).toBe(7)
  })
})
