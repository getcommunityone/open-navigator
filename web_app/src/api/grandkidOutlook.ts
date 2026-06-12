// API client for the "Grandkid outlook" intergenerational-mobility slopegraph —
// real Opportunity Atlas data (Chetty, Hendren, Jones & Porter, 2018). Filtered
// by parent income, child race, and child gender, mirroring the Opportunity
// Insights "Race and Class Trends" tool. NO fabricated numbers (CLAUDE.md):
// `local` is null when no commuting zone matched, and `local.available === false`
// when a CZ matched but the race×gender cell has too little data there.
import api from '../lib/api'

/** A single mobility outcome cell (parent → child income rank/percentile). */
export interface GrandkidOutcome {
  /** True when the warehouse has enough data for this scope×group cell. */
  available: boolean
  /** Mean child income rank (0..1) for kids of parents at parent_percentile. */
  child_income_rank?: number | null
  /** Same as a 0..100 percentile (child_income_rank * 100). */
  child_percentile?: number | null
  /** Sample size for the local (commuting-zone) cell. */
  n?: number | null
  /** Sample size for the national cell. */
  total_n?: number | null
}

export interface GrandkidOutlook {
  race: string
  gender: string
  parent_income_level: string
  /** Parent income percentile (e.g. 25 for "low"). */
  parent_percentile: number
  /** True when the place resolved to a commuting zone. */
  resolved: boolean
  /** Commuting-zone name, or null when nothing matched. */
  cz_name: string | null
  /** Human scope label, e.g. "the Tuscaloosa commuting zone". */
  scope_label: string
  /** Local commuting-zone outcome, or null when no CZ matched. */
  local: GrandkidOutcome | null
  /** National outcome — essentially always present. */
  national: GrandkidOutcome | null
  /** Honest one-line caveat to display verbatim near the chart. */
  note: string
  /** Attribution string. */
  source: string
  /** Attribution link. */
  source_url: string
}

export interface GrandkidOutlookParams {
  /** 2-letter state code. */
  state?: string
  city?: string
  /** Child race: pooled | white | black | hisp | asian | natam | other. */
  race?: string
  /** Child gender: pooled | male | female. */
  gender?: string
  /** Parent income level: low | middle | high. */
  parent_income?: string
}

export async function fetchGrandkidOutlook(
  params?: GrandkidOutlookParams,
): Promise<GrandkidOutlook> {
  const q = new URLSearchParams()
  if (params?.state) q.set('state', params.state)
  if (params?.city) q.set('city', params.city)
  if (params?.race) q.set('race', params.race)
  if (params?.gender) q.set('gender', params.gender)
  if (params?.parent_income) q.set('parent_income', params.parent_income)
  const qs = q.toString()
  const res = await api.get<GrandkidOutlook>(`/grandkid-outlook${qs ? `?${qs}` : ''}`)
  return res.data
}
