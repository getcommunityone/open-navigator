// Trending terms and hot words in meeting speech (#1399): GET /api/trends/terms and /api/trends/terms/{id}/evidence.
// Backs the "Trending in meetings" chip row on /browse-topics/all.
import api from '../lib/api'

export type TrendSort = 'rising' | 'hot' | 'volume'

export interface TrendScope {
  level: 'national' | 'state'
  state_code: string | null
  state: string | null
  /** A city in the request: terms are counted per state, so the state was answered. */
  requested_city: string | null
}

export interface TrendTerm {
  term_id: string
  term: string
  rank: number
  meetings_a: number
  meetings_b: number
  recorded_a: number
  recorded_b: number
  share_a: number | null
  share_b: number | null
  /** share_b / share_a; null when the term wasn't said in year_a. */
  rise: number | null
  n_meetings: number
  n_jurisdictions: number
  hot_score: number | null
  /** Sensitive term (health, religion, immigration…): counts only, never tied to a speaker. */
  is_sensitive: boolean
  latest_meeting_date: string | null
}

export interface TrendTermsResponse {
  scope: TrendScope
  sort: TrendSort
  year_a: string | null
  year_b: string | null
  terms: TrendTerm[]
}

export interface TrendEvidence {
  video_id: string
  meeting_date: string
  jurisdiction_name: string | null
  state_code: string | null
  video_url: string | null
  /** Verbatim excerpt with the term in <mark>…</mark>; render with highlightSnippet. */
  excerpt: string
  excerpt_source: 'public_comment' | 'transcript' | string
  start_seconds: number | null
  /** "First L.", or null when not identified. */
  speaker_display_name: string | null
}

export interface TrendEvidenceResponse {
  term_id: string
  term: string
  scope: TrendScope
  is_sensitive: boolean
  /** Null when the term isn't published for this scope. */
  total_meetings: number | null
  total: number
  limit: number
  offset: number
  items: TrendEvidence[]
}

export async function fetchTrendingTerms(
  state: string | undefined,
  sort: TrendSort,
  limit = 20,
  city?: string,
): Promise<TrendTermsResponse> {
  const params: Record<string, string | number> = { sort, limit }
  if (state) params.state = state
  if (state && city) params.city = city
  const { data } = await api.get<TrendTermsResponse>('/trends/terms', { params })
  return data
}

export async function fetchTrendEvidence(
  termId: string,
  state: string | undefined,
  offset = 0,
  limit = 5,
): Promise<TrendEvidenceResponse> {
  const params: Record<string, string | number> = { limit, offset }
  if (state) params.state = state
  const { data } = await api.get<TrendEvidenceResponse>(`/trends/terms/${encodeURIComponent(termId)}/evidence`, { params })
  return data
}
