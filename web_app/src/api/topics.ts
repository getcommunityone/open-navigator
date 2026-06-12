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

/** Fetch the topic catalog. Pass a 2-letter `state` to restrict to topics
 *  actually discussed in that state (used when arriving from a place filter). */
export async function fetchTopics(state?: string): Promise<TopicSummary[]> {
  const res = await api.get<TopicSummary[]>('/topics', {
    params: state ? { state } : undefined,
  })
  return res.data
}
