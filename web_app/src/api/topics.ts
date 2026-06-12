// API client for the policy-topic taxonomy (browse of topics + their keyword
// clusters). Backs the Browse Topics page.
import api from '../lib/api'

export interface TopicSummary {
  topic_id: number
  name: string
  query_id: string | null
  keywords: string[]
  /** Transcript snippets tagged with this topic — the API sorts by this desc. */
  transcript_occurrences: number
}

/** Fetch the topic catalog. Pass a 2-letter `state` and/or a `city` name to
 *  restrict to topics actually discussed in that place (used when arriving from
 *  a place filter); when scoped, `transcript_occurrences` is the place-scoped
 *  count rather than the national one. */
export async function fetchTopics(state?: string, city?: string): Promise<TopicSummary[]> {
  const params: Record<string, string> = {}
  if (state) params.state = state
  if (city) params.city = city
  const res = await api.get<TopicSummary[]>('/topics', {
    params: Object.keys(params).length ? params : undefined,
  })
  return res.data
}
