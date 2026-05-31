/**
 * The 50 US states + DC, as 2-letter USPS codes (no territories).
 *
 * This is an explicit canonical list on purpose: the older
 * `STATE_NAME_TO_CODE` map in {@link ../utils/stateMapping} is dirty (duplicate
 * and invalid entries like `VR`, `Oregon`), so it is NOT safe to derive launch
 * targets from it. The batch-jobs dashboard sends these codes straight to the
 * scraper, which validates each against `^[A-Z]{2}$`.
 */
export const STATE_CODES: string[] = [
  'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL',
  'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME',
  'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH',
  'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI',
  'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI',
  'WY',
]
