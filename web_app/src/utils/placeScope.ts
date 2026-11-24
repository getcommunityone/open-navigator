// Map a resolved place (the home page's geocoder result, as a LocationData) to the
// grain Data Stories can show: a 2-letter state and, when the geocoder named one, a
// city. The URL `?state=&city=` is the authority on those pages; this never reads or
// writes the site-wide saved location.
import { STATE_CODE_TO_NAME } from './stateMapping'

export interface ResolvedPlace {
  state?: string
  city?: string
  county?: string
}

export interface PlaceScope {
  stateCode: string
  /** The geocoder's own name for the city, so matching against meeting records needs no exact typing. */
  city: string | null
  /** True when the pick was a county (no city grain): the state is applied, and the dialog says so. */
  countyOnly: boolean
  county: string | null
}

/** Null when the place has no US state we can name. */
export function placeToScope(loc: ResolvedPlace | null | undefined): PlaceScope | null {
  const stateCode = (loc?.state ?? '').trim().toUpperCase()
  if (!stateCode || !STATE_CODE_TO_NAME[stateCode]) return null
  const city = (loc?.city ?? '').trim()
  const county = (loc?.county ?? '').trim()
  if (city) return { stateCode, city, countyOnly: false, county: county || null }
  return { stateCode, city: null, countyOnly: true, county: county || null }
}

/** The sentence shown after a county pick, since stories are told by city or state. */
export function countyNotice(scope: PlaceScope): string | null {
  if (!scope.countyOnly) return null
  const state = STATE_CODE_TO_NAME[scope.stateCode] ?? scope.stateCode
  const county = scope.county ? (/county$/i.test(scope.county) ? scope.county : `${scope.county} County`) : 'That county'
  return `${county} has no city of its own here. Stories are told by city or state; showing all of ${state}.`
}
