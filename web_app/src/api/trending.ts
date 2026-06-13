// API client for trending causes (homepage "Browse causes" flyout + cause
// directory). Backs /api/trending, which reads real EveryOrg / NTEE cause
// tables from the warehouse — no fabricated rows.
import api from '../lib/api'

export interface CauseItem {
  /** Stable slug (EveryOrg cause id, e.g. 'education') — passed as ?cause_id=. */
  cause_id?: string | null
  name: string
  icon: string
  category: string
  description?: string | null
  image_url?: string | null
  popularity_rank?: number | null
  /** Real count of analyzed meetings whose transcript matches this cause. */
  meeting_count?: number
}

export interface TrendingResponse {
  causes: CauseItem[]
  total: number
}

export async function fetchTrendingCauses(params?: {
  source?: 'everyorg' | 'ntee' | 'mixed'
  limit?: number
  level?: number
  /** Scope per-cause meeting counts to a state (2-letter code or full name). */
  state?: string
  /** Further scope counts to a city/jurisdiction name. */
  city?: string
}): Promise<TrendingResponse> {
  const q: Record<string, string | number> = {}
  if (params?.source) q.source = params.source
  if (params?.limit != null) q.limit = params.limit
  if (params?.level != null) q.level = params.level
  if (params?.state) q.state = params.state
  if (params?.city) q.city = params.city
  const res = await api.get<TrendingResponse>('/trending', { params: q })
  return res.data
}
