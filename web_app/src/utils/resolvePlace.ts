// Shared ZIP → real place resolution, used by the home money banner AND the
// MoneyGameModal's "where's home?" gate. Every place is resolved from a real
// /api/geocode lookup — we NEVER fabricate a location (CLAUDE.md: No Fabricated
// Data). A ZIP can span cities and inside-vs-outside city limits, and city tax
// rates STACK on the county's, so a single ZIP can yield several real choices.
import api from '../lib/api'
import type { LocationData } from '../contexts/LocationContext'
import { nominatimUsStateCode } from './stateMapping'

// Build a real LocationData from a Nominatim geocode result (same parsing as
// AddressLookup.processResult). Returns null when no US state resolves.
export function locationFromGeocode(result: any): LocationData | null {
  if (!result) return null
  const addr = result.address || {}
  const stateCode = nominatimUsStateCode(addr) || ''
  if (!stateCode) return null
  const county = (addr.county as string) || ''
  const city =
    (addr.city as string) ||
    (addr.town as string) ||
    (addr.village as string) ||
    (addr.municipality as string) ||
    (addr.hamlet as string) ||
    (addr.suburb as string) ||
    ''
  if (!city && !county) return null
  return {
    address: result.display_name,
    state: stateCode,
    county,
    city,
    granularity: !city ? 'county' : undefined,
    latitude: parseFloat(result.lat),
    longitude: parseFloat(result.lon),
  }
}

// Distinct real choices for a ZIP: one chip per city ("inside {city}") plus an
// "outside city limits" (county-only) option per distinct county. Real geography
// only — no invented ZIP table.
export function buildZipChoices(results: any[]): { label: string; loc: LocationData }[] {
  const locs = (Array.isArray(results) ? results : [results])
    .map(locationFromGeocode)
    .filter(Boolean) as LocationData[]
  const cities = new Map<string, LocationData>()
  const counties = new Map<string, LocationData>()
  for (const l of locs) {
    if (l.city) {
      const k = `${l.city}|${l.county}`
      if (!cities.has(k)) cities.set(k, l)
    }
    if (l.county) {
      if (!counties.has(l.county)) counties.set(l.county, { ...l, city: '', granularity: 'county' })
    }
  }
  const multiCounty = counties.size > 1
  const choices: { label: string; loc: LocationData }[] = []
  for (const l of cities.values()) choices.push({ label: `📍 ${l.city}`, loc: l })
  for (const l of counties.values()) {
    choices.push({
      label: multiCounty ? `🌾 Outside city limits (${l.county})` : '🌾 Outside city limits',
      loc: l,
    })
  }
  return choices
}

// Resolve a 5-digit ZIP to its distinct real place choices. Nominatim's forward
// ZIP lookup often omits the city, but reverse-geocoding the centroid recovers
// it — so we merge both, then dedupe in buildZipChoices.
export async function resolveZipToChoices(zip: string): Promise<{ label: string; loc: LocationData }[]> {
  const fwd = await api.get(`/geocode/search`, { params: { q: zip, limit: 10 } })
  const fwdResults = Array.isArray(fwd.data) ? fwd.data : [fwd.data]
  let revResults: any[] = []
  const first = fwdResults.find((r) => r?.lat && r?.lon)
  if (first) {
    try {
      const rev = await api.get(`/geocode/reverse`, { params: { lat: first.lat, lon: first.lon } })
      revResults = Array.isArray(rev.data) ? rev.data : [rev.data]
    } catch {
      /* reverse is best-effort */
    }
  }
  return buildZipChoices([...revResults, ...fwdResults])
}
