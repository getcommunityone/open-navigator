// API client for the policy-question registry (cross-jurisdiction policy
// questions + canonical arguments + comparative rollups).
import api from '../lib/api'

export interface PolicyQuestionSummary {
  question_id: string
  canonical_text: string | null
  topic_code: string | null
  primary_theme: string | null
  cofog_code: string | null
  scope: string | null
  status: string | null
  instances_total: number
  jurisdictions_total: number
  jurisdictions_approved: number
  // Curated "featured" questions (homepage "big questions"). `display_order`
  // controls their sequence; both may be absent on older API responses.
  is_featured?: boolean
  display_order?: number | null
  // Real money & talk (dbt policy_question mart). money_total = dollars moved by
  // this question's local decisions; *_share = its slice of ALL civic decisions.
  money_total?: number
  money_share?: number
  talk_share?: number
  // Real meetings whose transcript discusses this question's alias keyword(s)
  // (dbt question_transcript_link). A high-recall keyword signal — distinct from
  // the structured decision instances — that powers the "discussed in N meetings"
  // fallback for questions with no mapped decisions.
  discussion_meeting_count?: number
}

// A real meeting whose transcript discusses the question's alias keyword(s).
export interface QuestionMeeting {
  video_id: string
  event_title: string | null
  event_date: string | null
  state_code: string | null
  state: string | null
  city: string | null
  jurisdiction_name: string | null
  video_url: string | null
  n_alias_hits: number
}

// One quarter of a question's history (real). instances = how often it came up;
// money = net_dollar_impact of that quarter's linked local decisions.
export interface QuestionTrendPoint {
  quarter_start: string
  instances: number
  money: number
}

export interface CanonicalArgument {
  argument_id: string
  stance: string | null
  label: string | null
  summary: string | null
  source_role: string | null
  frame_id: string | null
  frame_label: string | null
  member_count: number
}

export interface QuestionRollup {
  instances_total: number
  decisions_total: number
  bills_total: number
  jurisdictions_total: number
  jurisdictions_approved: number
  states_total: number
  approved_count: number
  denied_count: number
  deferred_count: number
  other_count: number
}

export interface QuestionInstance {
  instance_id: string
  source_type: string
  source_id: string
  state_code: string | null
  jurisdiction_name: string | null
  city: string | null
  outcome_raw: string | null
  outcome_normalized: string | null
  occurred_at: string | null
  assign_score: number | null
}

export interface QuestionRelation {
  relation_type: string
  direction: string
  evidence: string | null
  question_id: string
  canonical_text: string | null
  scope: string | null
}

export interface PolicyQuestionDetail extends PolicyQuestionSummary {
  first_seen: string | null
  rollup: QuestionRollup
  arguments: CanonicalArgument[]
  sample_instances: QuestionInstance[]
  relations: QuestionRelation[]
  trend: QuestionTrendPoint[]
}

export async function fetchPolicyQuestions(params?: {
  theme?: string
  scope?: string
  limit?: number
  // When true, request only the curated/featured questions (homepage
  // "big questions" rail), ordered by display_order server-side.
  featured?: boolean
}): Promise<PolicyQuestionSummary[]> {
  const q = new URLSearchParams()
  if (params?.theme) q.set('theme', params.theme)
  if (params?.scope) q.set('scope', params.scope)
  if (params?.limit) q.set('limit', String(params.limit))
  if (params?.featured) q.set('featured', 'true')
  const res = await api.get(`/policy-question/?${q.toString()}`)
  return res.data
}

export async function fetchPolicyQuestion(id: string): Promise<PolicyQuestionDetail> {
  const res = await api.get(`/policy-question/${id}`)
  return res.data
}

export async function fetchQuestionInstances(
  id: string,
  limit = 50,
  offset = 0,
): Promise<QuestionInstance[]> {
  const res = await api.get(`/policy-question/${id}/instances?limit=${limit}&offset=${offset}`)
  return res.data
}

// Real meetings whose transcript discusses the question's alias keyword(s).
// The "discussed in N meetings" fallback for questions with no mapped decisions.
export async function fetchQuestionMeetings(
  id: string,
  limit = 50,
  offset = 0,
): Promise<QuestionMeeting[]> {
  const res = await api.get(`/policy-question/${id}/meetings?limit=${limit}&offset=${offset}`)
  return res.data
}
