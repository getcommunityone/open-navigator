// API client for /api/local-finance — REAL government-finance figures (Census
// Annual Survey of State & Local Government Finances, per the API's `source`).
// Every field is honest: whole-dollar amounts, `null` for genuinely-missing
// values (render as "—"/omit, NEVER 0). `fiscal_year` is already a string.
// Mirrors moneyTalk.ts's style: `import api from '../lib/api'`, typed interface,
// a single fetchLocalFinance(params) helper.
import api from '../lib/api'

export interface LocalFinanceCategory {
  category: string
  amount: number
  /** Share of direct_expenditure, percent 0..100. Can be null. */
  share_pct: number | null
}

export interface LocalFinance {
  level: 'city' | 'county' | 'state' | 'school_district'
  /** false = requested city/county fell back to statewide figures. */
  matched: boolean
  jurisdiction_name: string
  gov_type: string
  state_code: string
  /** full state name. */
  state: string
  /** already serialized as a string, e.g. "2021". */
  fiscal_year: string
  population: number | null
  total_taxes: number | null
  property_tax: number | null
  sales_tax: number | null
  other_taxes: number | null
  taxes_per_capita: number | null
  total_expenditure: number | null
  /** the pie denominator. */
  direct_expenditure: number | null
  /** sorted by amount desc, sums to ~100% of direct_expenditure. */
  categories: LocalFinanceCategory[]
  source: string
  note: string
}

export interface LocalFinanceParams {
  /** 2-letter state code — REQUIRED. */
  state: string
  city?: string
  county?: string
  /** Drill into a single government level instead of the combined view.
   *  Omit for the location's default (best-matching) level. A level with no
   *  data for the location returns 404 — surface it as an explicit empty state. */
  level?: 'city' | 'county' | 'state' | 'school_district'
}

export async function fetchLocalFinance(params: LocalFinanceParams): Promise<LocalFinance> {
  const q: Record<string, string> = { state: params.state }
  if (params.city) q.city = params.city
  if (params.county) q.county = params.county
  if (params.level) q.level = params.level
  const res = await api.get<LocalFinance>('/local-finance', { params: q })
  return res.data
}

// REAL effective property-tax rate (ACS B25103 ÷ B25077) for the best-matching
// place/county. A location with no place/county match is a 404 — the caller
// hides the estimate rather than invent a rate.
export interface PropertyTaxRate {
  level: 'place' | 'county'
  matched: boolean
  jurisdiction_name: string
  state_code: string
  state: string
  acs_vintage_year: number | null
  /** Fraction (0.004746 = 0.47%); multiply by home value for the annual bill. */
  effective_property_tax_rate: number | null
  /** ACS median home value — a sensible default for the slider. */
  median_home_value: number | null
  median_real_estate_taxes_paid: number | null
  source: string
  note: string
}

export async function fetchPropertyTaxRate(
  params: LocalFinanceParams,
): Promise<PropertyTaxRate> {
  const q: Record<string, string> = { state: params.state }
  if (params.city) q.city = params.city
  if (params.county) q.county = params.county
  const res = await api.get<PropertyTaxRate>('/local-finance/property-tax-rate', {
    params: q,
  })
  return res.data
}

// REAL combined state + average-local sales-tax rate (Tax Foundation), per state.
export interface SalesTaxRate {
  state_code: string
  state: string
  /** Percentages as published (9.46 = 9.46%). */
  state_sales_tax_rate_pct: number | null
  avg_local_sales_tax_rate_pct: number | null
  combined_sales_tax_rate_pct: number | null
  as_of_date: string | null
  source: string
}

export async function fetchSalesTaxRate(state: string): Promise<SalesTaxRate> {
  const res = await api.get<SalesTaxRate>('/local-finance/sales-tax-rate', {
    params: { state },
  })
  return res.data
}

// REAL combined local government — city + county + the resident's school
// district, summed (so K-12 spending shows up). Shares are recomputed against
// the combined total.
export interface CombinedGovernment {
  level: 'city' | 'county' | 'school_district'
  jurisdiction_name: string
  direct_expenditure: number | null
}

export interface CombinedFinance {
  jurisdiction_name: string
  state_code: string
  state: string
  fiscal_year: string
  direct_expenditure: number | null
  categories: LocalFinanceCategory[]
  /** What was stacked, for the "city + county + schools" callout. */
  governments: CombinedGovernment[]
  source: string
  note: string
}

export async function fetchCombinedFinance(params: LocalFinanceParams): Promise<CombinedFinance> {
  const q: Record<string, string> = { state: params.state }
  if (params.city) q.city = params.city
  if (params.county) q.county = params.county
  const res = await api.get<CombinedFinance>('/local-finance/combined', { params: q })
  return res.data
}
