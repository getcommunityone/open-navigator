// API client for the policy-topic taxonomy (browse of topics + their keyword
// clusters). Backs the Browse Topics page.
import api from '../lib/api'

export interface TopicSummary {
  topic_id: number
  name: string
  query_id: string | null
  keywords: string[]
  /** Transcript snippets tagged with this topic — the API sorts by this desc.
   *  0 for curated topics (CivicSearch never tagged them). */
  transcript_occurrences: number
  /** 'civicsearch' (CivicSearch taxonomy) or 'curated' (hand-authored, e.g.
   *  "Data centers"). Older API builds omit it. */
  source?: 'civicsearch' | 'curated' | string
  /** Meetings whose transcript matched the topic, in the requested scope
   *  (national, or the `state` passed) for every topic. State grain is the
   *  finest there is: no city-level topic counts exist. null/undefined = no
   *  count available. */
  meeting_count?: number | null
}

/** Fetch the topic catalog. Pass a 2-letter `state` to restrict to topics
 *  actually discussed in that state (used when arriving from a place filter). */
export async function fetchTopics(state?: string): Promise<TopicSummary[]> {
  const res = await api.get<TopicSummary[]>('/topics', {
    params: state ? { state } : undefined,
  })
  return res.data
}

/** A meeting whose transcript matched a curated topic's keywords. */
export interface TopicMeeting {
  video_id: string
  title: string | null
  /** ISO yyyy-mm-dd or null. */
  date: string | null
  state_code: string | null
  state: string | null
  city: string | null
  jurisdiction_name: string | null
  video_url: string | null
  /** Verbatim transcript passage with the matched words in <mark>…</mark>.
   *  Render with highlightSnippet (React-escaped), never as raw HTML. */
  excerpt: string | null
  n_keyword_hits: number
}

export interface TopicMeetingList {
  topic_id: number
  total: number
  items: TopicMeeting[]
}

export async function fetchTopicMeetings(
  topicId: number,
  params: { state?: string; city?: string; limit?: number; offset?: number } = {},
): Promise<TopicMeetingList> {
  const res = await api.get<TopicMeetingList>(`/topics/${topicId}/meetings`, { params })
  return res.data
}
