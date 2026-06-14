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
// Note: San Francisco is a consolidated city-county, so its county FIPS (06075)
// covers exactly the city — broadening is a no-op. It's included for
// completeness, but callers should skip the broaden control for it.

export interface LaunchCounty {
  countyName: string
  countyFips: string
}

export const LAUNCH_COUNTIES: Record<string, LaunchCounty> = {
  'san francisco': { countyName: 'San Francisco County', countyFips: '06075' },
  boston: { countyName: 'Suffolk County', countyFips: '25025' },
  atlanta: { countyName: 'Fulton County', countyFips: '13121' },
  minneapolis: { countyName: 'Hennepin County', countyFips: '27053' },
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
