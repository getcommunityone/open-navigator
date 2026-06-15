// Launch-city → surrounding-county map.
//
// Each launch city the app ships with maps to the county that contains it, so a
// scoped surface (e.g. Search) can offer "Include all of <County>" broadening.
// The search API accepts a 5-digit `county_fips`; when present it supersedes the
// `city` filter and widens results to every city in that county.
//
// Keys are LOWERCASED city names for case-insensitive lookup. `countyName` is the
// full "X County" label used verbatim in the scope label / checkbox.
//
// Keep this aligned with the launch set in `launchCoverage.ts` and the
// serving-layer `launch_county_fips` in publish_public_serving.sql.

export interface LaunchCounty {
  countyName: string
  countyFips: string
}

export const LAUNCH_COUNTIES: Record<string, LaunchCounty> = {
  seattle: { countyName: 'King County', countyFips: '53033' },
  boston: { countyName: 'Suffolk County', countyFips: '25025' },
  atlanta: { countyName: 'Fulton County', countyFips: '13121' },
  tuscaloosa: { countyName: 'Tuscaloosa County', countyFips: '01125' },
}

/**
 * Look up the surrounding county for a launch city (case-insensitive, trimmed).
 * Returns null for an unknown/empty city.
 */
export function getLaunchCounty(city?: string | null): LaunchCounty | null {
  if (!city) return null
  const key = city.trim().toLowerCase()
  if (!key) return null
  return LAUNCH_COUNTIES[key] ?? null
}
