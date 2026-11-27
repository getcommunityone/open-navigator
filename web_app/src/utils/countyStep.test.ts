import { describe, expect, it } from 'vitest'
import type { Feat } from '../lib/dotMatrix'
import { countyLabel, countyMeetings, countyOfPlace } from './countyStep'

// #1321: test-only shapes (two square "counties" in map units) and places; nothing here is served by the app.
const sq = (id: string, name: string, x0: number, y0: number, s = 10): Feat => ({
  id,
  name,
  polys: [[[[x0, y0], [x0 + s, y0], [x0 + s, y0 + s], [x0, y0 + s], [x0, y0]]]],
  bbox: [x0, y0, x0 + s, y0 + s],
})
const walton = sq('12131', 'Walton', 0, 0)
const okaloosa = sq('12091', 'Okaloosa', 10, 0)
const feats = [walton, okaloosa]
// Places in map units, placed by a stand-in for the projection.
const at = (x: number, y: number) => ({ x, y })
const byPlace = [
  { jurisdiction_id: 'c1', jurisdiction_name: 'Walton County', jurisdiction_type: 'county', geoid: '12131', meetings: 3, ...at(5, 5) },
  { jurisdiction_id: 'p1', jurisdiction_name: 'DeFuniak Springs city', jurisdiction_type: 'municipality', meetings: 2, ...at(2, 2) },
  { jurisdiction_id: 'p2', jurisdiction_name: 'Destin city', jurisdiction_type: 'municipality', meetings: 4, ...at(15, 5) },
]
const project = (p: { x?: number; y?: number }) => (p.x != null && p.y != null ? ([p.x, p.y] as [number, number]) : null)

describe('countyOfPlace', () => {
  it("finds the county holding the city's coordinates", () => {
    expect(countyOfPlace({ city: 'DeFuniak Springs', savedCounty: null, byPlace, feats, project })?.id).toBe('12131')
  })
  it('a city with no meetings (no coordinates) uses the saved county', () => {
    expect(countyOfPlace({ city: 'Miramar Beach', savedCounty: 'Walton County', byPlace, feats, project })?.id).toBe('12131')
    expect(countyOfPlace({ city: 'Miramar Beach', savedCounty: 'Okaloosa', byPlace, feats, project })?.id).toBe('12091')
  })
  it('no coordinates and no saved county: unknown', () => {
    expect(countyOfPlace({ city: 'Miramar Beach', savedCounty: null, byPlace, feats, project })).toBeNull()
  })
})

describe('countyMeetings', () => {
  it('the county government plus every place inside the county', () => {
    expect(countyMeetings(walton, byPlace, feats, project)).toEqual({ name: 'Walton County', meetings: 5 })
    expect(countyMeetings(okaloosa, byPlace, feats, project)).toEqual({ name: 'Okaloosa County', meetings: 4 })
  })
  it('names counties as people say them, parishes in Louisiana', () => {
    expect(countyLabel('Walton', '12')).toBe('Walton County')
    expect(countyLabel('Orleans', '22')).toBe('Orleans Parish')
    expect(countyLabel('Juneau City and Borough', '02')).toBe('Juneau City and Borough')
  })
})
