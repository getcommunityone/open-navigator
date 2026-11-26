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
   *  (national, state, or city when both `state` and `city` are passed).
   *  null/undefined = no count available. */
  meeting_count?: number | null
}

/** Fetch the topic catalog. Pass a 2-letter `state` (and optional `city`) to
 *  restrict to topics discussed there and get matching meeting_count grain. */
export async function fetchTopics(state?: string, city?: string): Promise<TopicSummary[]> {
  const params: Record<string, string> = {}
  if (state) params.state = state
  if (state && city) params.city = city
  const res = await api.get<TopicSummary[]>('/topics', {
    params: Object.keys(params).length ? params : undefined,
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

export interface TopicStateCount {
  state_code: string
  state: string | null
  meetings: number
}

export interface TopicStates {
  topic_id: number
  total_meetings: number
  states: TopicStateCount[]
  /** The newest matched meeting per state, with its verbatim passage. */
  newest: TopicMeeting[]
}

/** Meetings per state for a curated topic, and each state's newest passage (#1013). */
export async function fetchTopicStates(topicId: number, params: { state?: string } = {}): Promise<TopicStates> {
  const res = await api.get<TopicStates>(`/topics/${topicId}/states`, { params })
  return res.data
}

/** A company's newest mention: verbatim evidence with the matched words in <mark> (render with highlightSnippet). */
export interface TopicCompanyMention {
  mention_kind: string
  title?: string | null
  /** ISO yyyy-mm-dd or null. */
  date?: string | null
  jurisdiction_name?: string | null
  state_code?: string | null
  url?: string | null
  evidence?: string | null
}

/** One company a topic names (#1052), with its real meeting and decision counts in scope. */
export interface TopicCompany {
  company_key: string
  company_name: string
  aliases: string[]
  website_url?: string | null
  /** The organization page id, when the company is in MDM. */
  master_org_id?: string | null
  meetings: number
  decisions: number
  newest?: TopicCompanyMention | null
}

export interface TopicCompanies {
  topic_query_id: string
  scope: { level: string; state_code?: string | null; city?: string | null }
  companies: TopicCompany[]
}

/** `GET /api/topics/{queryId}/companies?state=&city=`: each company's meetings and decisions in scope, busiest first. */
export async function fetchTopicCompanies(queryId: string, state?: string, city?: string | null): Promise<TopicCompanies> {
  const params: Record<string, string> = {}
  if (state) params.state = state
  if (state && city) params.city = city
  const res = await api.get<TopicCompanies>(`/topics/${encodeURIComponent(queryId)}/companies`, {
    params: Object.keys(params).length ? params : undefined,
  })
  return res.data
}
