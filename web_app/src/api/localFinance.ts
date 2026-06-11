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
  level: 'city' | 'county' | 'state'
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
}

export async function fetchLocalFinance(params: LocalFinanceParams): Promise<LocalFinance> {
  const q: Record<string, string> = { state: params.state }
  if (params.city) q.city = params.city
  if (params.county) q.county = params.county
  const res = await api.get<LocalFinance>('/local-finance', { params: q })
  return res.data
}
