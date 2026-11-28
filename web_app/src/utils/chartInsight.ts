/**
 * The takeaway title for a map or chart (#1409, owner: "tell them the most interesting, impactful thing"). A pure picker:
 * it scores the findings the real data supports for the scope and leads with the most impactful one. Every number comes
 * from the input; a finding below its minimum counts is not a headline, and the fallback is volume and place.
 *
 * Order: 1 change in heat over time, 2 officials siding against the public, 3 a sharp rise in attention, 4 a clear public
 * lean (with its top concern only when that concern is really the top cue in the opposing or heated turns), 5 volume.
 * No title claims a cause without evidence: "led by noise" appears only with a `concern` whose basis is stated.
 */

export type InsightKind = 'heat' | 'officials' | 'attention' | 'lean' | 'volume' | 'none'

export interface InsightYear {
  year: string
  meetings: number
  /** Share of all recorded meetings (0-1); null when it can't be computed. */
  share?: number | null
  recorded?: number | null
}

export interface InsightInput {
  /** Lower-case subject, "short-term rentals". */
  subject: string
  /** "Florida", or "the United States" nationally. */
  place: string
  totalMeetings?: number
  /** The topic's meetings per year (the timeline). The latest year may be partial, so attention compares shares. */
  years?: InsightYear[]
  /** Average comment heat (1-5) per year over rated speakers (classifier / ai_meeting_analysis). */
  heatByYear?: { year: string; mean: number; rated: number }[]
  /** Meetings where officials sided against the public, of the meetings read (read may be unknown). */
  officials?: { meetings: number; read?: number | null }
  /** The public's lean: counts of speakers or of meetings read. */
  lean?: { unit: 'speakers' | 'meetings'; against: number; for: number; other: number }
  /** The most-cited concern in the opposing or heated turns; `of` is how many such turns were read. Never a guess. */
  concern?: { label: string; count: number; of: number; basis: 'opposing' | 'heated' | 'objections' }
  topPlaces?: string[]
}

export interface Insight {
  kind: InsightKind
  title: string
  /** The numbers behind the title, for a tap or tooltip. */
  support: string | null
}

export const MIN_MEETINGS = 5
export const MIN_SPEAKERS = 20
const MAX_TITLE = 90

const fmt = (n: number) => n.toLocaleString('en-US')
const cap = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s)
const meetingsWord = (n: number) => `${fmt(n)} ${n === 1 ? 'meeting' : 'meetings'}`
const num = (y: string) => Number.parseInt(y, 10)

function latestTwo<T extends { year: string }>(rows: T[] | undefined): [T, T] | null {
  const r = [...(rows ?? [])].filter((x) => Number.isFinite(num(x.year))).sort((a, b) => num(a.year) - num(b.year))
  if (r.length < 2) return null
  const cur = r[r.length - 1]!
  const prev = r[r.length - 2]!
  return num(cur.year) - num(prev.year) === 1 ? [prev, cur] : null
}

function heatFinding(i: InsightInput): Insight | null {
  const two = latestTwo(i.heatByYear)
  if (!two) return null
  const [prev, cur] = two
  if (prev.rated < MIN_SPEAKERS || cur.rated < MIN_SPEAKERS || prev.mean <= 0) return null
  const ratio = cur.mean / prev.mean
  if (ratio < 1.25 || cur.mean - prev.mean < 0.4) return null
  const how = ratio >= 1.9 ? `heat roughly doubled in ${cur.year}` : `average heat rose from ${prev.mean.toFixed(1)} to ${cur.mean.toFixed(1)} in ${cur.year}`
  return {
    kind: 'heat',
    title: `${cap(i.subject)} meetings in ${i.place} are getting heated: ${how}`,
    support: `Average comment heat (1 to 5): ${prev.mean.toFixed(1)} in ${prev.year} (${fmt(prev.rated)} speakers rated), ${cur.mean.toFixed(1)} in ${cur.year} (${fmt(cur.rated)} rated).`,
  }
}

function officialsFinding(i: InsightInput): Insight | null {
  const o = i.officials
  if (!o || o.meetings < MIN_MEETINGS) return null
  const read = o.read != null && o.read >= o.meetings ? o.read : null
  if (read != null && o.meetings / read < 0.25) return null
  const title = read
    ? `${i.place} officials sided against the public in ${fmt(o.meetings)} of ${fmt(read)} ${i.subject} meetings`
    : `${i.place} officials sided against the public in ${meetingsWord(o.meetings)} on ${i.subject}`
  return { kind: 'officials', title, support: `${meetingsWord(o.meetings)} where officials sided against the public${read ? `, of ${fmt(read)} read` : ''}.` }
}

function attentionFinding(i: InsightInput): Insight | null {
  const two = latestTwo(i.years)
  if (!two) return null
  const [prev, cur] = two
  // The current year is partial, so only shares of all recorded meetings are comparable.
  if (prev.share == null || cur.share == null || prev.share <= 0) return null
  if (prev.meetings < MIN_MEETINGS || cur.meetings < MIN_MEETINGS) return null
  const change = Math.round((cur.share / prev.share - 1) * 100)
  if (change < 30) return null
  return {
    kind: 'attention',
    title: `${cap(i.subject)} is up ${change}% as a share of ${i.place} meetings in ${cur.year}`,
    support: `Share of recorded meetings: ${(prev.share * 100).toFixed(1)}% in ${prev.year} (${fmt(prev.meetings)} meetings) to ${(cur.share * 100).toFixed(1)}% in ${cur.year} (${fmt(cur.meetings)} so far).`,
  }
}

function leanFinding(i: InsightInput): Insight | null {
  const l = i.lean
  if (!l) return null
  const total = l.against + l.for + l.other
  const enough = l.unit === 'speakers' ? total >= MIN_SPEAKERS : total >= MIN_MEETINGS
  if (!enough) return null
  const noun = l.unit === 'speakers' ? 'speakers' : 'meetings where the public spoke'
  const side = l.against >= l.for ? 'against' : 'for'
  const n = side === 'against' ? l.against : l.for
  if (n / total < 0.5) return null
  const verb = side === 'against' ? 'opposed' : 'supported'
  let title = `The public mostly ${verb} ${i.subject}: ${fmt(n)} of ${fmt(total)} ${noun}`
  let support = `${fmt(n)} of ${fmt(total)} ${noun} ${side === 'against' ? 'were against' : 'were for'}.`
  const c = i.concern
  if (side === 'against' && c && c.count >= MIN_MEETINGS && c.of > 0 && c.count / c.of >= 0.3) {
    const withCause = `${cap(i.subject)}: ${verb} in ${fmt(n)} of ${fmt(total)} ${noun}; ${c.label} leads the complaints`
    if (withCause.length <= MAX_TITLE) title = withCause
    support += ` ${cap(c.label)} is the top concern in ${fmt(c.count)} of ${fmt(c.of)} ${c.basis} turns read.`
  }
  return { kind: 'lean', title, support }
}

function volumeFinding(i: InsightInput): Insight | null {
  const n = i.totalMeetings ?? 0
  if (n <= 0) return null
  const where = i.topPlaces && i.topPlaces.length > 1 ? `, most in ${i.topPlaces.slice(0, 2).join(' and ')}` : ''
  return { kind: 'volume', title: `${cap(i.subject)} came up in ${meetingsWord(n)} in ${i.place}${where}`, support: null }
}

/** Shortens a title to ~90 characters by dropping its trailing clause (after ";" or ", most in"), never mid-number. */
function fit(title: string): string {
  if (title.length <= MAX_TITLE) return title
  for (const cut of ['; ', ', most in ']) {
    const at = title.indexOf(cut)
    if (at > 0 && at <= MAX_TITLE) return title.slice(0, at)
  }
  return title
}

const FINDERS = [heatFinding, officialsFinding, attentionFinding, leanFinding, volumeFinding] as const

/** The most impactful finding the data supports; "none" (a plain description) when nothing clears its minimum. */
export function pickInsight(input: InsightInput): Insight {
  for (const f of FINDERS) {
    const hit = f(input)
    if (hit) return { ...hit, title: fit(hit.title) }
  }
  return { kind: 'none', title: `${cap(input.subject)} meetings · ${input.place}`, support: null }
}
