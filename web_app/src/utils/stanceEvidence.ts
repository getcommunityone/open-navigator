// The recorded evidence behind a stance headline (#1289): hand-counted public speakers and recorded votes, beside the AI
// meeting reading the caption picker starts from. A stance headline ("Alabama mostly opposes data centers.") must agree with
// the recorded votes, and below a minimum of recorded activity it is replaced by "Not enough recorded activity to say."
// Decision record: web_docs/docs/development/story-captions.md ("Stance headlines and the recorded votes").
import type { TopicCaptionFacts } from '../api/topics'
import type { Caption } from './storyCaption'

/** Decisions with a recorded vote a stance headline needs, unless it has enough speakers. */
export const STANCE_MIN_DECISIONS = 3
/** Hand-counted public speakers a stance headline needs, unless it has enough decisions. */
export const STANCE_MIN_SPEAKERS = 5

export interface RecordedEvidence {
  /** Hand-counted public speakers in scope; null when not on record (no meeting reviewed, or the topic has no counts). */
  speakers: number | null
  /** Meetings reviewed by hand; null when not on record. */
  meetingsReviewed: number | null
  /** Decisions with a recorded vote; null when not on record. */
  decisions: number | null
  votesFor: number
  votesAgainst: number
  /** The server sends the #1289 `votes` field (null or not): a null then means nothing reviewed, not an older server. */
  reported: boolean
  /** #1290: decisions whose vote went for / against the topic (dbt `vote_side`); null when the server can't say. */
  decisionsFor: number | null
  decisionsAgainst: number | null
  /** #1290: public comments from our captions in scope (side not classified yet); null when not available. */
  captionComments: number | null
}

/** The scope's recorded evidence from its caption facts. Nothing is filled in: a missing count stays null. */
export function recordedEvidence(f: TopicCaptionFacts | null | undefined): RecordedEvidence {
  const sp = f?.speakers
  const v = f?.votes
  return {
    speakers: sp ? sp.for + sp.against + sp.question + sp.neutral : null,
    meetingsReviewed: sp?.meetings_reviewed ?? null,
    decisions: v ? v.decisions : null,
    votesFor: v?.for ?? 0,
    votesAgainst: v?.against ?? 0,
    reported: Boolean(f && 'votes' in f),
    decisionsFor: v?.decisions_for ?? null,
    decisionsAgainst: v?.decisions_against ?? null,
    captionComments: f?.caption_comments?.comments ?? null,
  }
}

/** Topics whose speakers are hand-counted and whose votes are recorded (`data_center_meeting_position`). */
export const RECORDED_TOPICS: ReadonlySet<string> = new Set(['data-centers'])

/**
 * Below the minimum: fewer than 3 decisions with a recorded vote and fewer than 5 speakers. Only a topic that keeps these
 * records is held to it; for such a topic a scope with nothing reviewed yet (both null) counts as none recorded, so it is
 * below the minimum too. A topic that keeps neither is not held to it.
 */
export function belowStanceMinimum(e: RecordedEvidence, topicKey?: string): boolean {
  // An older server (no `votes` field) can't tell "nothing reviewed" from "not sent": only real counts gate it.
  const keeps = topicKey && e.reported ? RECORDED_TOPICS.has(topicKey) : e.speakers != null || e.decisions != null
  if (!keeps) return false
  return (e.decisions ?? 0) < STANCE_MIN_DECISIONS && (e.speakers ?? 0) < STANCE_MIN_SPEAKERS
}

/** The share of tallied decisions one side needs before the votes lean that way (#1290). */
export const VOTE_LEAN_SHARE = 2 / 3

/**
 * Which way the recorded votes went. #1290: by decision, from which way each vote went for the topic (dbt `vote_side`: a
 * passed moratorium is against, a passed approval or delay is for), leaning a way only with two thirds of the decisions;
 * mixed votes lean neither way. A "yes" is not "for": summed yes votes counted a 23–0 moratorium as support. Only an older
 * server without the sides falls back to the summed yes and no votes. Null with no votes, a tie or mixed votes.
 */
export function voteSide(e: RecordedEvidence): 'for' | 'against' | null {
  if (!e.decisions) return null
  if (e.decisionsFor != null && e.decisionsAgainst != null) {
    const d = e.decisionsFor + e.decisionsAgainst
    if (d <= 0) return null
    if (e.decisionsFor / d >= VOTE_LEAN_SHARE) return 'for'
    if (e.decisionsAgainst / d >= VOTE_LEAN_SHARE) return 'against'
    return null
  }
  if (e.votesFor > e.votesAgainst) return 'for'
  if (e.votesAgainst > e.votesFor) return 'against'
  return null
}

/**
 * The side a caption claims for its own scope, or null when it claims none (a question, a count, "divided", "not enough")
 * or claims it for a broader scope (wider_*: that scope's votes are not this one's).
 */
export function stanceSide(c: Pick<Caption, 'kind' | 'verdict'>): 'for' | 'against' | null {
  if (c.kind === 'sentiment') return 'against'
  if (c.kind === 'position' && (c.verdict === 'for' || c.verdict === 'against')) return c.verdict
  return null
}

const fmt = (n: number) => n.toLocaleString('en-US')

/** "One decision passed 8–1; no public speakers in 24 meetings reviewed.": the recorded facts, with no zero invented. */
export function evidenceFacts(e: RecordedEvidence): string {
  let votes: string
  if (e.decisions == null) votes = 'Recorded votes are not available yet'
  else if (e.decisions === 0) votes = 'No decision with a recorded vote'
  else if (e.decisions === 1) {
    const how = e.votesFor > e.votesAgainst ? 'passed' : e.votesAgainst > e.votesFor ? 'failed' : 'tied'
    votes = `One decision ${how} ${fmt(e.votesFor)}–${fmt(e.votesAgainst)}`
  } else {
    votes = `${fmt(e.decisions)} decisions with recorded votes, ${fmt(e.votesFor)} for and ${fmt(e.votesAgainst)} against in all`
  }
  const r = e.meetingsReviewed
  const comments = e.captionComments ?? 0
  let speakers: string
  if (e.speakers == null) speakers = 'public speakers are not available yet'
  else if (!r) speakers = `${fmt(e.speakers)} public ${e.speakers === 1 ? 'speaker' : 'speakers'} on record`
  else {
    const where = `in ${fmt(r)} ${r === 1 ? 'meeting' : 'meetings'} reviewed`
    // #1290: our captions hold public comments, so people did speak; what's missing is which side they took.
    speakers =
      e.speakers === 0
        ? comments > 0
          ? `no speaker’s side is recorded ${where}, and the ${fmt(comments)} public ${comments === 1 ? 'comment' : 'comments'} in our captions ${comments === 1 ? 'is' : 'are'} not sorted by side yet`
          : `no public speakers ${where}`
        : `${fmt(e.speakers)} public ${e.speakers === 1 ? 'speaker' : 'speakers'} ${where}`
  }
  return `${votes}; ${speakers}.`
}

/** "Recorded votes went the other way: 3 of 3 decisions went for data centers." (#1290), or the summed votes without sides. */
export function voteSideClause(e: RecordedEvidence, topic: string): string {
  const side = voteSide(e)
  if (!side || e.decisionsFor == null || e.decisionsAgainst == null) return voteClause(e)
  const d = e.decisionsFor + e.decisionsAgainst
  const k = side === 'for' ? e.decisionsFor : e.decisionsAgainst
  return `Recorded votes went the other way: ${fmt(k)} of ${fmt(d)} ${d === 1 ? 'decision' : 'decisions'} with a recorded vote went ${side} ${topic}.`
}

/** The label in front of the transcript reading, so it never reads as counted speakers (#1290). */
export const READING_LABEL = 'Read from each meeting’s transcript, not counted by speaker:'

/** "Recorded votes: 79 for and 10 against, in 12 decisions." */
export function voteClause(e: RecordedEvidence): string {
  const d = e.decisions ?? 0
  return `Recorded votes: ${fmt(e.votesFor)} for and ${fmt(e.votesAgainst)} against, in ${fmt(d)} ${d === 1 ? 'decision' : 'decisions'}.`
}
