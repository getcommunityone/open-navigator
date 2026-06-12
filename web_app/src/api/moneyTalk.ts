// API client for the "Money & Talk" explorer — compares each government
// function's share of spending ("money") vs share of meeting discussion
// ("talk"). Money = net impact of money-flagged decisions, NOT a budget.
import api from '../lib/api'

export interface MoneyTalkMonthly {
  month: string // "YYYY-MM"
  decision_count: number
  spend_amount: number
}

export interface MoneyTalkTheme {
  theme: string
  cofog_code: string | null
  decision_count: number // "talk"
  spend_amount: number // "money" (can be 0)
  spend_count: number
  talk_share: number // percent 0..100
  spend_share: number // percent 0..100
  monthly: MoneyTalkMonthly[] // sparse, may be short/empty
}

export interface MoneyTalkTotals {
  decision_count: number
  spend_amount: number
  spend_count: number
}

export interface MoneyTalk {
  as_of: string // "YYYY-MM-DD"
  note: string // honest caveat to display near the title
  totals: MoneyTalkTotals
  themes: MoneyTalkTheme[]
}

export async function fetchMoneyAndTalk(params?: {
  jurisdiction_id?: number | string
  state_code?: string
}): Promise<MoneyTalk> {
  const q = new URLSearchParams()
  if (params?.jurisdiction_id !== undefined && params.jurisdiction_id !== null && params.jurisdiction_id !== '') {
    q.set('jurisdiction_id', String(params.jurisdiction_id))
  }
  if (params?.state_code) q.set('state_code', params.state_code)
  const qs = q.toString()
  const res = await api.get<MoneyTalk>(`/money-and-talk${qs ? `?${qs}` : ''}`)
  return res.data
}
