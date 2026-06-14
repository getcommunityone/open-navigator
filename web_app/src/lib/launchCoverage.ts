// ── Launch coverage ──
// The single source of truth for which places have civic data loaded today.
// One launch city per state (ordered by city population, largest first); each
// state has exactly one launch city, so a state-scoped search (`/search?state=XX`)
// is an effective per-city view. Keep in sync with the serving-layer filter.
//
// Used both by the home page's coverage note and by the location picker, which
// warns when a user picks a place we haven't loaded yet (see isLocationCovered).

export interface LaunchCity {
  city: string
  state: string
}

export const LAUNCH_CITIES: ReadonlyArray<LaunchCity> = [
  { city: 'Seattle', state: 'WA' },       // ~737k
  { city: 'Boston', state: 'MA' },        // ~666k
  { city: 'Atlanta', state: 'GA' },       // ~495k
  { city: 'Tuscaloosa', state: 'AL' },    // ~106k
]

const norm = (s?: string) => (s || '').trim().toLowerCase()

// A picked location is "covered" only when its city + state match a launch city.
// Each launch state has just one loaded city, so a different city in a launch
// state (e.g. St. Paul, MN) is NOT covered — we surface that honestly rather than
// pretending data exists. Match is case-insensitive and tolerant of a trailing
// " city"/" town" the geocoder sometimes appends.
export function isLocationCovered(loc: { city?: string; state?: string } | null | undefined): boolean {
  if (!loc?.state) return false
  const state = norm(loc.state)
  const city = norm(loc.city).replace(/\s+(city|town)$/, '')
  return LAUNCH_CITIES.some((c) => norm(c.state) === state && norm(c.city) === city)
}
