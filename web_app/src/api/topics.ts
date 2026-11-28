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
  /** On `/states` `newest` (#1230) and `/meetings` (#1293): how the public leaned at this meeting in the AI reading
   *  (topic_meeting_lean, same thresholds as the map): 'against' | 'for' | 'split' | 'silent', or null when not read. */
  public_stance?: 'against' | 'for' | 'split' | 'silent' | null
  /** `/meetings` (#1293): the meeting's five-position public reading (water fluoridation), only when on the same side. */
  public_position?: string | null
  /** `/meetings`: what the council or board did on the topic, in the same AI reading. */
  vote?: 'advanced' | 'blocked' | 'tabled_or_deferred' | null
  /** `/meetings`: the card's position chip key and where it comes from; both null = no chip. 'meeting' is the meeting's
   *  overall public position, never the quoted speaker's. */
  position?: string | null
  position_source?: 'speaker' | 'meeting' | 'vote' | null
  /** `/meetings`: named public commenters whose words matched the topic ("First L."), up to 3, and how many in all. */
  commenters?: string[]
  commenter_count?: number
  /** `/meetings`: no person, no public position and no vote on record. */
  in_passing?: boolean
  /** `/meetings`: the meeting's page in the app, or null. */
  meeting_url?: string | null
}

/** `/meetings` (#1293): the scope's meetings by what the record says about people and positions. Never speakers. */
export interface TopicSaidCounts {
  against: number
  for: number
  split: number
  silent: number
  unread: number
  vote_advanced: number
  vote_blocked: number
  vote_tabled: number
  with_person: number
  public_position_meetings: number
  in_passing: number
}

export interface TopicMeetingList {
  topic_id: number
  total: number
  items: TopicMeeting[]
  /** First page only; null on later pages or on a serving copy without the tables. */
  position_counts?: TopicSaidCounts | null
}

export async function fetchTopicMeetings(
  topicId: number,
  params: { state?: string; city?: string; limit?: number; offset?: number; sort?: 'newest' | 'people' } = {},
): Promise<TopicMeetingList> {
  const res = await api.get<TopicMeetingList>(`/topics/${topicId}/meetings`, { params })
  return res.data
}

/** A decision whose record matched the topic (#1293), with its meeting and why it is on the topic or only in passing. */
export interface TopicDecision extends DecisionPeople {
  event_decision_id: string
  title: string
  /** Matched passage, terms in <mark> (render with highlightSnippet). */
  excerpt?: string | null
  outcome?: string | null
  jurisdiction_name?: string | null
  state_code?: string | null
  state?: string | null
  meeting_name?: string | null
  meeting_date?: string | null
  decision_url: string
  meeting_url?: string | null
  video_url?: string | null
  video_id?: string | null
  relevance: 'on_topic' | 'in_passing'
  relevance_basis: string
}

/** One person on a decision's side (#1320): an official by full name and reliable role, anyone else "First L.". */
export interface DecisionPerson {
  name: string
  role?: string | null
  kind: 'official' | 'resident'
}

/** Who was on each side of a decision, and its recorded vote (#1320). All optional: older servers omit them. */
export interface DecisionPeople {
  supported_by?: DecisionPerson[]
  opposed_by?: DecisionPerson[]
  spoke_on_it?: DecisionPerson[]
  supported_view?: string | null
  /** false: no counter view on record; null: the record has no competing views. */
  opposition_recorded?: boolean | null
  vote_yes?: number | null
  vote_no?: number | null
}

export interface TopicDecisionList {
  topic_id: number
  topic_slug?: string | null
  total: number
  on_topic_total: number
  in_passing_total: number
  on_topic: TopicDecision[]
  in_passing: TopicDecision[]
}

/** `GET /api/topics/{id}/decisions`: decisions on the topic and ones that only mention it (#1293). */
export async function fetchTopicDecisions(
  topicId: number,
  params: { state?: string; city?: string; limit?: number } = {},
): Promise<TopicDecisionList> {
  const res = await api.get<TopicDecisionList>(`/topics/${topicId}/decisions`, { params })
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

/** Meetings per state for a curated topic, and each state's newest passage(s) (#1013, #1357). */
export async function fetchTopicStates(
  topicId: number,
  params: { state?: string; quotes_per_state?: number } = {},
): Promise<TopicStates> {
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

/**
 * One government's meetings on a topic in a state (#1349), in the data-center map's `by_place` shape, so StoryCountyMap
 * reads it as it is. `speakers_*` are MEETINGS as the AI read them (public mostly opposed / supported / split), never
 * counted speakers; 0 where the government has no reading.
 */
export interface TopicPlaceCount {
  jurisdiction_id: string
  jurisdiction_name: string | null
  jurisdiction_type: string | null
  geoid: string | null
  latitude: number | null
  longitude: number | null
  meetings: number
  lean_meetings: number
  speakers_against: number
  speakers_for: number
  speakers_neutral: number
  speakers_question: number
  silent_meetings: number
  public_against_meetings: number
  disagreement_meetings: number
}

export interface TopicPlaces {
  topic_id: number
  state_code: string
  /** Distinct meetings on the topic in the state (the same count as /states for it). */
  total_meetings: number
  /** Meetings whose government can't be drawn: total minus the sum of `by_place`. Footnoted, never spread. */
  unplaced_meetings: number
  /** False until `topic_place_meeting` is published: the page keeps the state outline. */
  available: boolean
  by_place: TopicPlaceCount[]
}

/** `GET /api/topics/{id}/places?state=` (#1349): a topic's meetings per government for the state's county map. */
export async function fetchTopicPlaces(topicId: number, state: string): Promise<TopicPlaces> {
  const res = await api.get<TopicPlaces>(`/topics/${topicId}/places`, { params: { state } })
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
  speakers: { for: number; against: number; question: number; neutral: number; states?: number; meetings_reviewed?: number } | null
  /**
   * Recorded votes in scope (data centers only, #1289): decisions with a tally and their summed votes. Null when no meeting
   * in scope was reviewed; absent on older servers.
   */
  votes?: {
    decisions: number
    for: number
    against: number
    /** #1290: decisions whose vote went for / against the data center (dbt vote_side); null when not available. */
    decisions_for?: number | null
    decisions_against?: number | null
  } | null
  /** #1330: officials' position in the meeting reading (P >= 0.7 for a side), and meetings with any position. */
  official_against_meetings?: number | null
  official_for_meetings?: number | null
  official_divided_meetings?: number | null
  /** Meetings with any recorded position, public (against, for or split) or official. */
  position_meetings?: number | null
  /** Meetings where both the public and officials took a position. */
  both_position_meetings?: number | null
  /** #1290: public comments from our own captions in scope (data centers only); their side isn't classified yet. */
  caption_comments?: { comments: number; governments: number } | null
  /**
   * #1391: public speakers in scope whose own words on the topic a classifier read with confidence (low-confidence readings
   * are never served). A separate, labelled source ("speakers' own words, classifier"), never added to `speakers`.
   */
  classifier_speakers?: {
    source: string
    for: number
    against: number
    concerns_only: number
    no_position: number
    meetings: number
  } | null
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

/** `GET /api/topics/{topic}/heat-by-year?state=&city=` (#1418): mean speaker heat per year; thin years are omitted. */
export interface TopicHeatByYear {
  topic: string
  years: { year: string; mean: number; speakers_rated: number; share_heated: number | null }[]
}

export async function fetchTopicHeatByYear(topic: string, state?: string, city?: string | null): Promise<TopicHeatByYear> {
  const params: Record<string, string> = {}
  if (state) params.state = state
  if (state && city) params.city = city
  const res = await api.get<TopicHeatByYear>(`/topics/${encodeURIComponent(topic)}/heat-by-year`, { params })
  return res.data
}

/** `GET /api/topics/{topic}/top-concern?state=&city=` (#1418): the most-cited concern in the opposing or heated turns. */
export interface TopicTopConcern {
  topic: string
  label: string | null
  count: number | null
  of: number | null
  basis: 'opposing' | 'heated' | null
  share: number | null
}

export async function fetchTopicTopConcern(topic: string, state?: string, city?: string | null): Promise<TopicTopConcern> {
  const params: Record<string, string> = {}
  if (state) params.state = state
  if (state && city) params.city = city
  const res = await api.get<TopicTopConcern>(`/topics/${encodeURIComponent(topic)}/top-concern`, { params })
  return res.data
}
