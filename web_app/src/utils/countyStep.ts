// The county step of the story scope (#1321): city → county → state. Pure, so it is tested; useStoryScope wires it to the
// data-center place counts (`meeting-mentions counts.by_place`) and the county shapes. No county is guessed: it is the one
// holding the city's coordinates on record, else the saved location's county, else unknown.
import { featAt, type Feat } from '../lib/dotMatrix'

export interface CountyPlace {
  jurisdiction_name?: string | null
  jurisdiction_type?: string | null
  geoid?: string | null
  meetings: number
}

/** Where a place lands on the county shapes (albersPoint of its latitude/longitude), or null with no coordinates. */
export type Project<P> = (p: P) => [number, number] | null

const norm = (s: string | null | undefined) =>
  (s ?? '').trim().toLowerCase().replace(/\s+(city|town|village|borough|cdp)$/, '')
const normCounty = (s: string | null | undefined) =>
  (s ?? '').trim().toLowerCase().replace(/\s+(county|parish|borough|census area|municipality|city and borough)$/, '')

/** "Walton County", "Orleans Parish" (Louisiana, FIPS 22); a name that already says what it is stays as it is. */
export function countyLabel(name: string, stateFips: string): string {
  if (/\b(county|parish|borough|census area|municipality|city)\b/i.test(name)) return name
  return `${name} ${stateFips === '22' ? 'Parish' : 'County'}`
}

/** The county a city is in: from its coordinates on record, else the saved county's name; null when neither is known. */
export function countyOfPlace<P extends CountyPlace>(a: {
  city: string
  savedCounty: string | null | undefined
  byPlace: P[]
  feats: Feat[]
  project: Project<P>
}): Feat | null {
  const row = a.byPlace.find((p) => p.jurisdiction_type !== 'county' && norm(p.jurisdiction_name) === norm(a.city))
  const pt = row ? a.project(row) : null
  if (pt) {
    const hit = featAt(pt[0], pt[1], a.feats)
    if (hit) return hit
  }
  const want = normCounty(a.savedCounty)
  return want ? (a.feats.find((f) => normCounty(f.name) === want) ?? null) : null
}

/** A county's meetings: its own government's plus every place whose coordinates fall inside it. */
export function countyMeetings<P extends CountyPlace>(county: Feat, byPlace: P[], feats: Feat[], project: Project<P>): { name: string; meetings: number } {
  let meetings = 0
  for (const p of byPlace) {
    if (p.jurisdiction_type === 'county') {
      if (p.geoid === county.id) meetings += Math.max(0, p.meetings || 0)
      continue
    }
    const pt = project(p)
    if (pt && featAt(pt[0], pt[1], feats)?.id === county.id) meetings += Math.max(0, p.meetings || 0)
  }
  return { name: countyLabel(county.name, county.id.slice(0, 2)), meetings }
}
