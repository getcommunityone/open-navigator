// Every major meeting topic, last full year against this year (#1343, #1361): GET /api/topics/yoy?state=&city=&source=.
// Backs /browse-topics/all.
import api from '../lib/api'

export interface YoyScope {
  level: 'national' | 'state' | 'city'
  state_code: string | null
  state: string | null
  city: string | null
}

export interface YoyTopic {
  topic_id: number
  /** civicsearch_topic.query_id; live stories are /stories/<slug>. */
  slug: string
  name: string
  /** 'curated' or 'civicsearch'. */
  source: 'curated' | 'civicsearch' | string
  /** True when this topic already has a live story at /stories/<slug>. */
  has_story: boolean
  year_a: string
  year_b: string
  meetings_a: number
  meetings_b: number
  recorded_a: number
  recorded_b: number
  /** meetings / recorded (0–1); null when the scope recorded no meetings that year. */
  share_a: number | null
  share_b: number | null
  /** False when either year has too few topic meetings (< min_meetings) or recorded meetings (< min_recorded_meetings). */
  comparable: boolean
}

export interface YoyResponse {
  scope: YoyScope
  year_a: string
  year_b: string
  /** ISO date of the latest topic meeting in year_b in the scope (the partial year's label). */
  year_b_through: string | null
  year_b_partial: boolean
  recorded_a: number
  recorded_b: number
  /** A year with thin recording coverage in the scope, if any. */
  thin_year: string | null
  min_meetings: number
  min_recorded_meetings: number
  topics: YoyTopic[]
}

export async function fetchTopicsYoy(
  state?: string,
  city?: string | null,
  source?: 'curated' | 'civicsearch',
): Promise<YoyResponse> {
  const params: Record<string, string> = {}
  if (state) params.state = state
  if (state && city) params.city = city
  if (source) params.source = source
  const res = await api.get<YoyResponse>('/topics/yoy', { params })
  return res.data
}
