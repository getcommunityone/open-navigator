/**
 * US State name to 2-letter code mapping
 */
export const STATE_NAME_TO_CODE: Record<string, string> = {
  'Alabama': 'AL',
  'Alaska': 'AK',
  'Arizona': 'AZ',
  'Arkansas': 'AR',
  'California': 'CA',
  'Colorado': 'CO',
  'Connecticut': 'CT',
  'Delaware': 'DE',
  'Florida': 'FL',
  'Georgia': 'GA',
  'Hawaii': 'HI',
  'Idaho': 'ID',
  'Illinois': 'IL',
  'Indiana': 'IN',
  'Iowa': 'IA',
  'Kansas': 'KS',
  'Kentucky': 'KY',
  'Louisiana': 'LA',
  'Maine': 'ME',
  'Maryland': 'MD',
  'Massachusetts': 'MA',
  'Michigan': 'MI',
  'Minnesota': 'MN',
  'Mississippi': 'MS',
  'Missouri': 'MO',
  'Montana': 'MT',
  'Nebraska': 'NE',
  'Nevada': 'NV',
  'New Hampshire': 'NH',
  'New Jersey': 'NJ',
  'New Mexico': 'NM',
  'New York': 'NY',
  'North Carolina': 'NC',
  'North Dakota': 'ND',
  'Ohio': 'OH',
  'Oklahoma': 'OK',
  'Oregon': 'OR',
  'Pennsylvania': 'PA',
  'Rhode Island': 'RI',
  'South Carolina': 'SC',
  'South Dakota': 'SD',
  'Tennessee': 'TN',
  'Texas': 'TX',
  'Utah': 'UT',
  'Vermont': 'VT',
  'Virginia': 'VA',
  'Washington': 'WA',
  'West Virginia': 'WV',
  'Wisconsin': 'WI',
  'Wyoming': 'WY',
  'District of Columbia': 'DC',
  'Puerto Rico': 'PR'
}

/**
 * Reverse mapping: 2-letter code to full state name
 */
export const STATE_CODE_TO_NAME: Record<string, string> = Object.fromEntries(
  Object.entries(STATE_NAME_TO_CODE).map(([name, code]) => [code, name])
)

/** Alias used by jurisdiction-quality dashboard components. */
export const US_STATE_NAMES = STATE_CODE_TO_NAME

/**
 * Convert a full state name to its 2-letter code
 * @param stateName - Full state name (e.g., "Massachusetts")
 * @returns 2-letter state code (e.g., "MA") or the original string if not found
 */
export function stateNameToCode(stateName: string): string {
  // If it's already a 2-letter code, return as-is
  if (stateName && stateName.length === 2 && stateName === stateName.toUpperCase()) {
    return stateName
  }
  
  // Try exact match
  if (STATE_NAME_TO_CODE[stateName]) {
    return STATE_NAME_TO_CODE[stateName]
  }
  
  // Try case-insensitive match
  const normalizedName = Object.keys(STATE_NAME_TO_CODE).find(
    key => key.toLowerCase() === stateName.toLowerCase()
  )
  
  if (normalizedName) {
    return STATE_NAME_TO_CODE[normalizedName]
  }
  
  // Return original if not found
  console.warn(`State name "${stateName}" not found in mapping`)
  return stateName
}

function looksLikeUspsCode(s: string): boolean {
  return s.length === 2 && /^[A-Z]{2}$/i.test(s)
}

/**
 * Derive a USPS state code from a Nominatim `address` object (US results).
 * Handles full state names and `ISO3166-2-lvl4` like `US-NE`.
 */
export function nominatimUsStateCode(addr: Record<string, unknown> | null | undefined): string | null {
  if (!addr || typeof addr !== 'object') return null
  const rec = addr as Record<string, string | undefined>
  if (rec.state) {
    const c = stateNameToCode(rec.state)
    if (looksLikeUspsCode(c)) return c.toUpperCase()
  }
  const iso = rec['ISO3166-2-lvl4']
  if (iso && typeof iso === 'string' && iso.toUpperCase().startsWith('US-') && iso.length >= 5) {
    const c = iso.slice(3).toUpperCase()
    if (looksLikeUspsCode(c)) return c
  }
  return null
}
