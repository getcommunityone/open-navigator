// People and position on a topic story's "What was said" cards, and the split of its decisions (#1293).
//
// Every word here restates a real field: the quoted speaker from their self-introduction (meeting_passage_speaker), the named
// commenters whose own words matched the topic (meeting_comment), the meeting's public position in the AI reading
// (topic_meeting_lean, the map's thresholds) and what the council or board did (its outcome_group, the Votes screen's
// source). A meeting-level position is always labelled as the meeting's, never as the speaker's. No source, no chip.
import type { DecisionPeople, DecisionPerson, TopicMeeting, TopicSaidCounts } from '../api/topics'
import { actionLabels, FIVE_POSITION_STYLE } from './topicPolicy'
import { topicPositions } from './topicPositions'

export type ChipSide = 'for' | 'against' | 'neutral'

export interface PositionChip {
  /** "Public at this meeting: Oppose, each community decides" */
  label: string
  side: ChipSide
  source: 'speaker' | 'meeting' | 'vote'
}

const fmt = (n: number) => n.toLocaleString('en-US')
const meetings = (n: number) => `${fmt(n)} ${n === 1 ? 'meeting' : 'meetings'}`
const lowerFirst = (s: string) => (s ? s.charAt(0).toLowerCase() + s.slice(1) : s)

/** The public's side in the topic's own words; a five-position reading in its own plain words when served. */
function publicWords(slug: string, stance: string, five: string | null | undefined): string | null {
  const w = topicPositions(slug)
  if (five && FIVE_POSITION_STYLE[five]) return FIVE_POSITION_STYLE[five]!.label
  if (stance === 'against') return w.against
  if (stance === 'for') return w.for
  if (stance === 'split') return w.split
  return null
}

const VOTE_SIDE: Record<string, ChipSide> = { advanced: 'for', blocked: 'against', tabled_or_deferred: 'neutral' }

/**
 * The card's chips, most specific first: the meeting's public position (labelled as the meeting's), then what the council or
 * board did. Both come from the same meeting's AI reading; a card with neither has no chip.
 */
export function positionChips(slug: string, m: Pick<TopicMeeting, 'public_stance' | 'public_position' | 'vote'>): PositionChip[] {
  const out: PositionChip[] = []
  const stance = m.public_stance
  if (stance === 'against' || stance === 'for' || stance === 'split') {
    const words = publicWords(slug, stance, m.public_position)
    if (words) out.push({ label: `Public at this meeting: ${words}`, side: stance === 'split' ? 'neutral' : stance, source: 'meeting' })
  }
  if (m.vote && VOTE_SIDE[m.vote]) {
    out.push({ label: `Council or board: ${actionLabels(slug)[m.vote]}`, side: VOTE_SIDE[m.vote]!, source: 'vote' })
  }
  return out
}

/** "Amy N. · Resident", the name as served; null when the record names nobody (the card then says so). */
export function speakerLine(m: Pick<TopicMeeting, 'speaker_display_name' | 'speaker_role'>): string | null {
  if (!m.speaker_display_name) return null
  return [m.speaker_display_name, m.speaker_role].filter(Boolean).join(' · ')
}

/** "Also spoke on it: Tracy B., Lee K. and 2 more"; null with no named commenter. */
export function commentersLine(m: Pick<TopicMeeting, 'commenters' | 'commenter_count'>, lead = 'Also spoke on it'): string | null {
  const names = m.commenters ?? []
  if (names.length === 0) return null
  const more = Math.max(0, (m.commenter_count ?? names.length) - names.length)
  return `${lead}: ${names.join(', ')}${more > 0 ? ` and ${fmt(more)} more` : ''}`
}

/**
 * The summary line over the cards, from the scope's real counts: "Of 9 meetings: the public took no position at any of them.
 * At 4, the council or board voted to keep or start fluoridation. 5 only mentioned it in passing."
 */
export function saidSummary(slug: string, total: number, c: TopicSaidCounts | null | undefined): string | null {
  if (!c || total <= 0) return null
  const w = topicPositions(slug)
  const a = actionLabels(slug)
  const parts: string[] = []
  const sided = c.public_position_meetings
  if (c.unread >= total) {
    parts.push(`no AI reading of where the public stood yet`)
  } else if (sided === 0) {
    parts.push(`the public took no position at any of them`)
  } else {
    const sides = [
      c.against ? `${fmt(c.against)} ${w.against.toLowerCase()}` : null,
      c.for ? `${fmt(c.for)} ${w.for.toLowerCase()}` : null,
      c.split ? `${fmt(c.split)} split` : null,
    ].filter(Boolean)
    parts.push(`the public took a position at ${fmt(sided)} (${sides.join(', ')})`)
  }
  let line = `Of ${meetings(total)}: ${parts[0]}.`
  const acted = c.vote_advanced + c.vote_blocked + c.vote_tabled
  if (acted > 0) {
    const votes = [
      c.vote_advanced ? `${fmt(c.vote_advanced)} ${lowerFirst(a.advanced)}` : null,
      c.vote_blocked ? `${fmt(c.vote_blocked)} ${lowerFirst(a.blocked)}` : null,
      c.vote_tabled ? `${fmt(c.vote_tabled)} ${lowerFirst(a.tabled_or_deferred)}` : null,
    ].filter(Boolean)
    line += ` A council or board acted at ${fmt(acted)} (${votes.join(', ')}).`
  }
  if (c.with_person > 0) line += ` At ${fmt(c.with_person)}, the record names who spoke.`
  if (c.in_passing > 0) line += ` ${fmt(c.in_passing)} only mentioned it in passing.`
  return line
}

/** "2 decisions on gun control; 7 more mention guns in passing." from the endpoint's real totals. */
export function decisionsSummary(onTotal: number, passingTotal: number, topicWord: string, mentionWord: string): string {
  const dec = (n: number) => `${fmt(n)} ${n === 1 ? 'decision' : 'decisions'}`
  const on = onTotal > 0 ? `${dec(onTotal)} on ${topicWord}` : `No decision on ${topicWord} itself`
  if (passingTotal <= 0) return `${on}.`
  const verb = passingTotal === 1 ? 'mentions' : 'mention'
  return `${on}; ${onTotal > 0 ? `${fmt(passingTotal)} more` : dec(passingTotal)} ${verb} ${mentionWord} in passing.`
}

/** "John Faile (City Councilor), Lee Busby (Councilor) +3": names as served, a role only where the API gives one. */
export function peopleList(people: DecisionPerson[] | null | undefined, max = 3): string | null {
  const list = people ?? []
  if (list.length === 0) return null
  const shown = list.slice(0, max).map((p) => (p.role ? `${p.name} (${p.role})` : p.name))
  return `${shown.join(', ')}${list.length > max ? ` +${fmt(list.length - max)}` : ''}`
}

/**
 * The lines a decision card shows about its people and vote (#1320): "Supported by: …", "Opposed by: …" or "No opposition
 * recorded" (only when the record names supporters and lists no counter view), "Also spoke: …" and "Vote: 7–0". Nothing
 * when the record has none of it.
 */
export function decisionPeopleLines(d: DecisionPeople): string[] {
  const out: string[] = []
  const sup = peopleList(d.supported_by)
  const opp = peopleList(d.opposed_by)
  if (sup) out.push(`Supported by: ${sup}`)
  if (opp) out.push(`Opposed by: ${opp}`)
  else if (d.opposition_recorded === true) out.push('Opposition recorded; no names on record')
  else if (d.opposition_recorded === false && sup) out.push('No opposition recorded')
  const also = peopleList(d.spoke_on_it)
  if (also) out.push(`${sup || opp ? 'Also spoke' : 'Spoke on it'}: ${also}`)
  if (d.vote_yes != null) out.push(`Vote: ${fmt(d.vote_yes)}–${d.vote_no != null ? fmt(d.vote_no) : '?'}`)
  return out
}
