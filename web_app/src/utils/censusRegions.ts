/** Census Bureau region codes used for scorecard benchmarks. */
export type CensusRegionId = 'NE' | 'MW' | 'S' | 'W'

export const CENSUS_REGION_LABEL: Record<CensusRegionId, string> = {
  NE: 'Northeast',
  MW: 'Midwest',
  S: 'South',
  W: 'West',
}

/** Two-digit state FIPS → census region (50 states + DC; PR mapped to South). */
export const STATE_FIPS_TO_CENSUS_REGION: Record<string, CensusRegionId> = {
  '01': 'S',
  '02': 'W',
  '04': 'W',
  '05': 'S',
  '06': 'W',
  '08': 'W',
  '09': 'NE',
  '10': 'S',
  '11': 'S',
  '12': 'S',
  '13': 'S',
  '15': 'W',
  '16': 'W',
  '17': 'MW',
  '18': 'MW',
  '19': 'MW',
  '20': 'MW',
  '21': 'S',
  '22': 'S',
  '23': 'NE',
  '24': 'S',
  '25': 'NE',
  '26': 'MW',
  '27': 'MW',
  '28': 'S',
  '29': 'MW',
  '30': 'W',
  '31': 'MW',
  '32': 'W',
  '33': 'NE',
  '34': 'NE',
  '35': 'W',
  '36': 'NE',
  '37': 'S',
  '38': 'MW',
  '39': 'MW',
  '40': 'S',
  '41': 'W',
  '42': 'NE',
  '44': 'NE',
  '45': 'S',
  '46': 'MW',
  '47': 'S',
  '48': 'S',
  '49': 'W',
  '50': 'NE',
  '51': 'S',
  '53': 'W',
  '54': 'S',
  '55': 'MW',
  '56': 'W',
  '60': 'W',
  '66': 'W',
  '69': 'W',
  '72': 'S',
  '78': 'S',
}

export function censusRegionForStateFips(fips: string | null | undefined): CensusRegionId | null {
  if (!fips) return null
  const k = fips.length === 1 ? `0${fips}` : fips.slice(0, 2)
  return STATE_FIPS_TO_CENSUS_REGION[k] ?? null
}
