// API client for the policy-topic taxonomy (browse of topics + their keyword
// clusters). Backs the Browse Topics page.
import api from '../lib/api'

export interface TopicSummary {
  topic_id: number
  name: string
  query_id: string | null
  keywords: string[]
}

export async function fetchTopics(): Promise<TopicSummary[]> {
  const res = await api.get<TopicSummary[]>('/topics')
  return res.data
}
