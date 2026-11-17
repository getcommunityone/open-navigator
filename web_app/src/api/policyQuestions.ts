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
  // Linked local decisions that adopted or recommended a moratorium (#483).
  moratorium_count: number
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
  // Verbatim transcript passage with the alias words wrapped in <mark> (ts_headline,
  // built in dbt question_transcript_link, #499). Render with highlightSnippet.
  evidence: string | null
  start_seconds: number | null
  // The recording at start_seconds; null when the transcript is untimed.
  jump_url: string | null
}

// The rollup's outcome families (dbt macro question_outcome_family).
export type OutcomeFamily = 'approved' | 'denied' | 'moratorium' | 'deferred' | 'other'
export const OUTCOME_FAMILIES: OutcomeFamily[] = ['approved', 'denied', 'moratorium', 'deferred', 'other']

// The place scope every figure of a detail response is counted over (#499).
export interface QuestionScope {
  level: 'national' | 'state' | 'city'
  state_code: string | null
  city: string | null
}

// A linked decision whose net_dollar_impact adds up to money_total.
export interface QuestionMoneySource {
  event_decision_id: string
  title: string | null
  jurisdiction_name: string | null
  state_code: string | null
  outcome_family: OutcomeFamily | null
  occurred_at: string | null
  net_dollar_impact: number
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
  // Date range of the counted instances (#508 summary: "since May 2026").
  first_occurred_at?: string | null
  last_occurred_at?: string | null
  decisions_total: number
  bills_total: number
  jurisdictions_total: number
  jurisdictions_approved: number
  states_total: number
  approved_count: number
  denied_count: number
  deferred_count: number
  moratorium_count: number
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
  outcome_family?: OutcomeFamily | null
  occurred_at: string | null
  assign_score: number | null
  // #508: what was decided, where and who (built in dbt; null/empty for a bill).
  event_decision_id?: string | null
  headline?: string | null
  // Street-level address that agrees with the decision's own government; null when none.
  place_label?: string | null
  // Companies the decision's own headline/statement names, with the matched text.
  company_names?: string[]
  company_evidence?: string | null
  company_mentions?: QuestionCompanyMention[]
  // Tracked Epoch AI sites near the decision's government — NOT its subject.
  nearby_sites?: QuestionNearbySite[]
}

// A company named in a decision's own text: the exact words matched, and a verbatim
// excerpt with them in <mark> (render with highlightSnippet).
export interface QuestionCompanyMention {
  operator_name: string
  matched_text: string
  evidence: string | null
}

export interface QuestionNearbySite {
  data_center_site_id: string
  site_name: string | null
  owner: string | null
}

export interface QuestionRelation {
  relation_type: string
  direction: string
  evidence: string | null
  question_id: string
  canonical_text: string | null
  scope: string | null
}

export interface PolicyQuestionDetail extends Omit<PolicyQuestionSummary, 'scope'> {
  first_seen: string | null
  // The question's level (local | state | both).
  question_scope: string | null
  // The place scope of every count / money / meeting figure below (#499).
  scope: QuestionScope
  rollup: QuestionRollup
  // The decisions whose net_dollar_impact sums to money_total.
  money_sources: QuestionMoneySource[]
  // Browse Topics topic named like one of the question's aliases, if any.
  topic_id: number | null
  topic_name: string | null
  arguments: CanonicalArgument[]
  sample_instances: QuestionInstance[]
  relations: QuestionRelation[]
  // Per quarter, counted over the same scope (and outcome) as the rollup.
  trend: QuestionTrendPoint[]
  // With an outcome: the counts for that family only (the dashboard summary).
  outcome?: OutcomeFamily | null
  outcome_rollup?: QuestionRollup | null
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

export interface QuestionPlaceScope {
  state?: string
  city?: string
}

const scopeParams = (scope?: QuestionPlaceScope) => {
  const q = new URLSearchParams()
  if (scope?.state) q.set('state', scope.state)
  if (scope?.city) q.set('city', scope.city)
  return q
}

// One question; with a state/city every count and the money figure are for that scope.
// With an outcome, outcome_rollup / trend / sample_instances are for that family too.
export async function fetchPolicyQuestion(
  id: string,
  scope?: QuestionPlaceScope & { outcome?: OutcomeFamily },
): Promise<PolicyQuestionDetail> {
  const q = scopeParams(scope)
  if (scope?.outcome) q.set('outcome', scope.outcome)
  const qs = q.toString()
  const res = await api.get(`/policy-question/${id}${qs ? `?${qs}` : ''}`)
  return res.data
}

export async function fetchQuestionInstances(
  id: string,
  params: QuestionPlaceScope & {
    outcome?: OutcomeFamily
    order?: 'relevance' | 'recent'
    limit?: number
    offset?: number
  } = {},
): Promise<QuestionInstance[]> {
  const q = scopeParams(params)
  if (params.outcome) q.set('outcome', params.outcome)
  if (params.order) q.set('order', params.order)
  q.set('limit', String(params.limit ?? 50))
  q.set('offset', String(params.offset ?? 0))
  const res = await api.get(`/policy-question/${id}/instances?${q.toString()}`)
  return res.data
}

// Real meetings whose transcript discusses the question's alias keyword(s), newest
// first, scoped to the state/city. The scoped total is the detail's
// discussion_meeting_count.
export async function fetchQuestionMeetings(
  id: string,
  params: QuestionPlaceScope & { limit?: number; offset?: number } = {},
): Promise<QuestionMeeting[]> {
  const q = scopeParams(params)
  q.set('limit', String(params.limit ?? 50))
  q.set('offset', String(params.offset ?? 0))
  const res = await api.get(`/policy-question/${id}/meetings?${q.toString()}`)
  return res.data
}
