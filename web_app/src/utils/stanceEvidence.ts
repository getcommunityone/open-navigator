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
/**
 * #1330 (owner: "I thought we were counting all speakers and highlighting where they disagree"): meetings with any recorded
 * position, public or official, a stance headline needs, unless it has enough decisions (or hand-counted speakers).
 */
export const STANCE_MIN_POSITION_MEETINGS = 5

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
  /** #1330: meetings with any recorded position (public or official), and with both; null when the reading isn't loaded. */
  positionMeetings: number | null
  bothPositionMeetings: number | null
  /** #1330: the public's position, in meetings read (against, for, split). */
  publicAgainst: number | null
  publicFor: number | null
  publicSplit: number | null
  /** #1330: officials' position, in meetings read (against, for, divided). */
  officialAgainst: number | null
  officialFor: number | null
  officialDivided: number | null
  /** Meetings where officials sided against the public. */
  disagreement: number | null
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
    positionMeetings: f?.position_meetings ?? null,
    bothPositionMeetings: f?.both_position_meetings ?? null,
    publicAgainst: f?.public_split_meetings != null ? (f.public_against_meetings ?? 0) : null,
    publicFor: f?.public_split_meetings != null ? (f.public_for_meetings ?? 0) : null,
    publicSplit: f?.public_split_meetings ?? null,
    officialAgainst: f?.official_against_meetings ?? null,
    officialFor: f?.official_for_meetings ?? null,
    officialDivided: f?.official_divided_meetings ?? null,
    disagreement: f?.disagreement_meetings ?? null,
  }
}

/** Topics whose speakers are hand-counted and whose votes are recorded (`data_center_meeting_position`). */
export const RECORDED_TOPICS: ReadonlySet<string> = new Set(['data-centers'])

/**
 * Below the minimum (#1330): fewer than 3 decisions with a recorded vote, fewer than 5 meetings with any recorded position
 * (public or official), and fewer than 5 hand-counted speakers. Every recorded position counts, officials' included: the
 * owner asked for all speakers, not the public's alone. A scope whose reading is loaded is held to it whatever the topic;
 * a data-center scope with nothing reviewed and no reading counts as none recorded. A topic with no record of any kind
 * isn't held to it.
 */
export function belowStanceMinimum(e: RecordedEvidence, topicKey?: string): boolean {
  const keeps =
    e.positionMeetings != null ||
    (topicKey && e.reported ? RECORDED_TOPICS.has(topicKey) : e.speakers != null || e.decisions != null)
  if (!keeps) return false
  return (
    (e.decisions ?? 0) < STANCE_MIN_DECISIONS &&
    (e.positionMeetings ?? 0) < STANCE_MIN_POSITION_MEETINGS &&
    (e.speakers ?? 0) < STANCE_MIN_SPEAKERS
  )
}

const fmtN = (n: number) => n.toLocaleString('en-US')
const meetings = (n: number) => `${fmtN(n)} ${n === 1 ? 'meeting' : 'meetings'}`

/**
 * "In Georgia, officials sided against the public in 11 of 27 meetings where both took a side." (#1330), or null when they
 * never did or the reading isn't loaded. `where` is "In Georgia" / "Across America".
 */
export function disagreementLine(e: RecordedEvidence, where: string): string | null {
  const p = disagreementParts(e, where)
  return p ? `${p.before}${p.count}${p.after}` : null
}

/** The same line in three parts, so the count alone can be the tap target (never a search for the number in the text). */
export function disagreementParts(e: RecordedEvidence, where: string): { before: string; count: string; after: string } | null {
  if (!e.disagreement || e.disagreement <= 0) return null
  const both = e.bothPositionMeetings
  const of = both != null && both >= e.disagreement ? ` of ${fmtN(both)}` : ''
  const noun = (of ? both! : e.disagreement) === 1 ? 'meeting' : 'meetings'
  return {
    before: `${where}, officials sided against the public in `,
    count: fmtN(e.disagreement),
    after: `${of} ${noun}${of ? ` where both took a side` : ''}.`,
  }
}

/** "Public: 6 against · 2 split (8 meetings)" (#1330): the public's positions read, no zero side; null with none read. */
export function publicPositionsLine(e: RecordedEvidence): string | null {
  if (e.publicSplit == null) return null
  const parts = [
    [e.publicAgainst ?? 0, 'against'],
    [e.publicFor ?? 0, 'for'],
    [e.publicSplit, 'both sides spoke'],
  ].filter(([n]) => (n as number) > 0) as [number, string][]
  const total = parts.reduce((a, [n]) => a + n, 0)
  if (total === 0) return 'Public: took no side in the meetings read'
  return `Public: ${parts.map(([n, w]) => `${fmtN(n)} ${w}`).join(' · ')} (${meetings(total)})`
}

/**
 * "Officials: 7 against · 8 for · 13 divided (28 meetings); recorded votes: 1 decision for, 0 against" (#1330): officials' positions read and
 * the recorded votes by which way they went; null with neither.
 */
export function officialPositionsLine(e: RecordedEvidence): string | null {
  const parts = (
    [
      [e.officialAgainst ?? 0, 'against'],
      [e.officialFor ?? 0, 'for'],
      [e.officialDivided ?? 0, 'divided'],
    ] as [number, string][]
  ).filter(([n]) => n > 0)
  const total = parts.reduce((a, [n]) => a + n, 0)
  const read = e.officialDivided != null ? (total > 0 ? `${parts.map(([n, w]) => `${fmtN(n)} ${w}`).join(' · ')} (${meetings(total)})` : 'took no side in the meetings read') : null
  let votes: string | null = null
  if (e.decisions) {
    votes =
      e.decisionsFor != null && e.decisionsAgainst != null
        ? `recorded votes: ${fmtN(e.decisionsFor)} ${e.decisionsFor === 1 ? 'decision' : 'decisions'} for, ${fmtN(e.decisionsAgainst)} against`
        : `recorded votes: ${fmtN(e.votesFor)} yes, ${fmtN(e.votesAgainst)} no`
  }
  if (!read && !votes) return null
  return `Officials: ${[read, votes].filter(Boolean).join('; ')}`
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
    // #1290: "for / against" only by which way each decision went; summed votes are yes and no (a yes can be a moratorium).
    votes =
      e.decisionsFor != null && e.decisionsAgainst != null
        ? `${fmt(e.decisions)} decisions with recorded votes, ${fmt(e.decisionsFor)} for and ${fmt(e.decisionsAgainst)} against`
        : `${fmt(e.decisions)} decisions with recorded votes, ${fmt(e.votesFor)} yes and ${fmt(e.votesAgainst)} no votes in all`
  }
  const r = e.meetingsReviewed
  const comments = e.captionComments ?? 0
  let speakers: string
  if (e.speakers == null) speakers = 'public speakers are not available yet'
  else if (!r) speakers = `${fmt(e.speakers)} public ${e.speakers === 1 ? 'speaker' : 'speakers'} on record`
  else {
    const where = `in ${fmt(r)} ${r === 1 ? 'meeting' : 'meetings'} reviewed by hand`
    // #1290: our captions hold public comments, so people did speak; what's missing is which side they took.
    speakers =
      e.speakers === 0
        ? comments > 0
          ? `no speaker’s side is recorded ${where}, and the ${fmt(comments)} public ${comments === 1 ? 'comment' : 'comments'} in our captions ${comments === 1 ? 'is' : 'are'} not sorted by side yet`
          : `no public speakers ${where}`
        : `${fmt(e.speakers)} public ${e.speakers === 1 ? 'speaker' : 'speakers'} ${where}`
  }
  // #1330: every recorded position counts toward the minimum, so the facts say how many meetings had one.
  const positions =
    e.positionMeetings != null
      ? e.positionMeetings === 0
        ? 'no meeting read has a public or official position'
        : `the public or officials took a position in ${meetings(e.positionMeetings)} read`
      : null
  return `${[votes, speakers, positions].filter(Boolean).join('; ')}.`
}

/** "Recorded votes went the other way: 3 of 3 decisions went for data centers." (#1290), or the summed votes without sides. */
export function voteSideClause(e: RecordedEvidence, topic: string): string {
  const side = voteSide(e)
  if (!side || e.decisionsFor == null || e.decisionsAgainst == null) return voteClause(e)
  const d = e.decisionsFor + e.decisionsAgainst
  const k = side === 'for' ? e.decisionsFor : e.decisionsAgainst
  return `Recorded votes went the other way: ${fmt(k)} of ${fmt(d)} ${d === 1 ? 'decision' : 'decisions'} with a recorded vote went ${side} ${topic}.`
}


/** "Recorded votes: 79 for and 10 against, in 12 decisions." */
export function voteClause(e: RecordedEvidence): string {
  const d = e.decisions ?? 0
  return `Recorded votes: ${fmt(e.votesFor)} for and ${fmt(e.votesAgainst)} against, in ${fmt(d)} ${d === 1 ? 'decision' : 'decisions'}.`
}

/**
 * Named people on each side of the scope's decisions (#1330), from #1327's `supported_by` / `opposed_by` (never a second
 * parse of `held_by`): distinct names, so a councilor who backed three decisions counts once. Null when no decision carries
 * the fields (an older server, or nothing named).
 */
export function namedSides(
  items: ReadonlyArray<{ supported_by?: { name: string }[]; opposed_by?: { name: string }[] }> | null | undefined,
): { supporters: number; opposers: number } | null {
  if (!items || !items.some((d) => d.supported_by !== undefined || d.opposed_by !== undefined)) return null
  const sup = new Set<string>()
  const opp = new Set<string>()
  for (const d of items) {
    for (const p of d.supported_by ?? []) sup.add(p.name)
    for (const p of d.opposed_by ?? []) opp.add(p.name)
  }
  return { supporters: sup.size, opposers: opp.size }
}

/** "named supporters 5 · opposers 2" for the officials line (#1330); null when no one is named. */
export function namedSidesClause(n: { supporters: number; opposers: number } | null): string | null {
  if (!n || n.supporters + n.opposers === 0) return null
  return `named supporters ${fmtN(n.supporters)} · opposers ${fmtN(n.opposers)}`
}
