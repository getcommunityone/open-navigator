import type { LocationData } from '../contexts/LocationContext'
import { STATE_CODE_TO_NAME } from './stateMapping'

/** One-line label for headers and success copy (city, county, or whole state). */
export function formatCommunityPlaceLine(loc: LocationData): string {
  if (loc.granularity === 'state') {
    return `${STATE_CODE_TO_NAME[loc.state] ?? loc.state} (statewide)`
  }
  if (loc.granularity === 'county' && loc.county) {
    return `${loc.county.replace(/\s+County$/i, '').trim()}, ${loc.state}`
  }
  return `${loc.city}, ${loc.state}`
}
