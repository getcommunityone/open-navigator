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
  /** Who said the passage, from their self-introduction in the recording (#1231): an official's name, a resident's
   *  "First L.", or null (unknown, or withheld for a student, a minor or a school board resident). /states only. */
  speaker_display_name?: string | null
  /** The official's title, or "Resident" when they said they live here; null otherwise. */
  speaker_role?: string | null
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

/** One state's meetings and the AI reading of them (#1127): distinct meetings, never counted speakers. */
export interface TopicStanceStateCount {
  state_code: string
  state: string | null
  meetings: number
  lean_meetings: number
  public_against_meetings: number
  public_for_meetings: number
  /** Read as split (#1200): the public spoke but was divided, or the reading was unsure (mixed, or a lean under P 0.7). */
  no_side_meetings: number
  /** Read, but the public didn't speak on the topic (#1200): missing, never split. Absent on older servers. */
  silent_meetings?: number
  /** The public mostly opposed while officials mostly supported it. */
  disagreement_meetings: number
}

export interface TopicStanceMap {
  topic_id: number
  /** False until the AI reading (`topic_meeting_lean`, #1126) has this topic: the map shows meetings only. */
  available: boolean
  by_state: TopicStanceStateCount[]
}

/** Meetings per state with the AI reading behind a topic story's four-colour box map (#1127). */
export async function fetchTopicStanceMap(topicId: number, params: { state?: string } = {}): Promise<TopicStanceMap> {
  const res = await api.get<TopicStanceMap>(`/topics/${topicId}/state-map`, { params })
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

/** One state's meetings for a topic, with its population when on record (#1125). */
export interface CaptionStateCount {
  state_code: string
  state: string | null
  meetings: number
  population: number | null
}

/** The real counts behind a topic caption for one scope (#1125). Null means not on record, never zero. */
export interface TopicCaptionFacts {
  topic: string
  topic_id: number
  scope: { level: string; state_code: string | null; state: string | null; city: string | null }
  meetings: number | null
  /** Meetings per state for the whole country, largest first (never narrowed by the scope). */
  states: CaptionStateCount[]
  top_state: string | null
  ratio_to_next: number | null
  /** City scope: the place name the city matched, and meetings per place in the state. */
  place: string | null
  places: { name: string; meetings: number }[] | null
  /** Counted speakers (data centers only); `states` is how many states in scope have any (#1134). */
  speakers: { for: number; against: number; question: number; neutral: number; states?: number } | null
  /** AI readings (Jev) of meeting transcripts: never counted speakers. */
  lean_meetings: number | null
  public_against_meetings: number | null
  /** States with at least one public-against meeting in scope (#1134); absent on older servers. */
  public_against_states?: number | null
  public_for_meetings: number | null
  /** #1200: meetings where the public spoke but was split or the reading unsure; absent on older servers. */
  public_split_meetings?: number | null
  /** #1200: meetings read where the public didn't speak on the topic; absent on older servers. */
  public_silent_meetings?: number | null
  disagreement_meetings: number | null
  disagreement_states: number | null
  /**
   * The broader scopes' AI readings (#1182): for a city `[state, national]`, for a state `[national]`, nationally null.
   * An entry is left out when no reading is loaded for it. Absent on older servers.
   */
  wider?: CaptionWiderLean[] | null
}

/** One broader scope's AI reading (Jev) for the caption's fallback (#1182). */
export interface CaptionWiderLean {
  level: 'state' | 'national'
  state_code: string | null
  state: string | null
  lean_meetings: number
  public_against_meetings: number
  public_against_states: number
  /** #1200: absent on older servers. */
  public_for_meetings?: number
  public_split_meetings?: number
  public_silent_meetings?: number
  disagreement_meetings: number
}

/** `GET /api/topics/{topic}/caption-facts?state=&city=` (#1125). */
export async function fetchTopicCaptionFacts(topic: string, state?: string, city?: string | null): Promise<TopicCaptionFacts> {
  const params: Record<string, string> = {}
  if (state) params.state = state
  if (state && city) params.city = city
  const res = await api.get<TopicCaptionFacts>(`/topics/${encodeURIComponent(topic)}/caption-facts`, { params })
  return res.data
}
