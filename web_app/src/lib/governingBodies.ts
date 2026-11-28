/**
 * Who governs a place (#1446): types for GET /api/jurisdictions/{id}/bodies and GET /api/bodies/{id}, and the pure
 * helpers the place page and the body page share. Every figure comes from the API; nothing here invents a body, a
 * member or a count (CLAUDE.md, No Fabricated Data).
 */

export interface BodyMember {
  body_membership_id: string
  person_id: string | null
  member_name: string
  role: string
  role_title: string | null
  district: string | null
  start_date: string | null
  end_date: string | null
  is_current: boolean
  source: string
}

export interface RecentSpeaker {
  person_id: string | null
  member_name: string
  role: string | null
  meetings_heard: number
  last_heard_date: string | null
  moment_url: string | null
  attribution_method: string | null
}

export interface GoverningBody {
  governing_body_id: string
  body_name: string
  body_type: string
  is_primary: boolean
  meeting_count: number
  first_meeting_date: string | null
  last_meeting_date: string | null
  member_count: number
  members: BodyMember[]
  recent_speakers: RecentSpeaker[]
}

export interface JurisdictionBodies {
  jurisdiction_id: string
  jurisdiction_name: string
  state_code: string | null
  state: string | null
  bodies: GoverningBody[]
}

export interface BodyMeeting {
  meeting_body_id: string
  meeting_title: string | null
  meeting_date: string | null
  video_id: string | null
  video_url: string | null
  event_meeting_id: number | null
}

export interface BodyDetailResponse {
  body: Omit<GoverningBody, 'members' | 'recent_speakers'> & {
    jurisdiction_id: string
    jurisdiction_name: string
    state_code: string | null
    state: string | null
  }
  members: BodyMember[]
  recent_speakers: RecentSpeaker[]
  meetings: BodyMeeting[]
}

const ROLE_LABEL: Record<string, string> = {
  mayor: 'Mayor',
  president: 'President',
  president_pro_tem: 'President pro tem',
  vice_mayor: 'Vice mayor',
  chair: 'Chair',
  vice_chair: 'Vice chair',
  council_member: 'Council member',
  alderman: 'Alderman',
  commissioner: 'Commissioner',
  supervisor: 'Supervisor',
  member: 'Member',
  legislator: 'Legislator',
  clerk: 'Clerk',
  staff: 'Staff',
}

/** The role as the source titles it when it has one ("City Councilor"), else our label for the role key. */
export function roleLabel(role: string | null | undefined, roleTitle?: string | null): string {
  const t = (roleTitle ?? '').trim()
  if (t) return t
  return (role && ROLE_LABEL[role]) || 'Member'
}

/** "City Councilor · District 2" */
export function memberLine(m: Pick<BodyMember, 'role' | 'role_title' | 'district'>): string {
  const parts = [roleLabel(m.role, m.role_title)]
  if (m.district) parts.push(m.district)
  return parts.join(' · ')
}

/**
 * One entry per person: a council member who is also president pro tem shows once with both roles. Current seats
 * first; a seat that ended (a vacancy) keeps its end date so the page can say so.
 */
export interface PersonSeat {
  key: string
  person_id: string | null
  member_name: string
  lines: string[]
  is_current: boolean
  end_date: string | null
}

export function groupMembers(members: BodyMember[]): PersonSeat[] {
  const out: PersonSeat[] = []
  const index = new Map<string, PersonSeat>()
  for (const m of members) {
    const key = `${m.person_id ?? m.member_name}|${m.is_current ? 'c' : 'p'}`
    let seat = index.get(key)
    if (!seat) {
      seat = { key, person_id: m.person_id, member_name: m.member_name, lines: [], is_current: m.is_current, end_date: m.end_date }
      index.set(key, seat)
      out.push(seat)
    }
    const line = memberLine(m)
    if (!seat.lines.includes(line)) seat.lines.push(line)
  }
  return out
}

/** "36 meetings on file" / "No meetings on file yet" */
export function meetingCountLabel(n: number): string {
  if (!n) return 'No meetings on file yet'
  return `${n.toLocaleString()} meeting${n === 1 ? '' : 's'} on file`
}

export function memberCountLabel(n: number): string {
  if (!n) return 'Members not on file'
  return `${n.toLocaleString()} ${n === 1 ? 'person' : 'people'}`
}

/** A date from the API ('2026-11-17') as "Nov 17, 2026", without a timezone shift. */
export function formatDay(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return '—'
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

const HOW: Record<string, string> = {
  chair_call: 'called on by the chair',
  roll_call: 'answered the roll call',
  self_intro: 'introduced themself',
  official_roster_match: 'introduced themself',
}

export function howHeard(method: string | null | undefined): string {
  return (method && HOW[method]) || 'heard'
}

/**
 * Officials heard most recently across a place's bodies: one row per person, the latest moment wins, with the body
 * it was in. Residents are never in this list: the API returns roster members only.
 */
export interface HeardOfficial extends RecentSpeaker {
  body_name: string
  governing_body_id: string
}

export function officialsHeard(bodies: GoverningBody[], limit = 8): HeardOfficial[] {
  const best = new Map<string, HeardOfficial>()
  for (const b of bodies) {
    for (const s of b.recent_speakers) {
      const key = s.person_id ?? s.member_name
      const cur = best.get(key)
      if (!cur || (s.last_heard_date ?? '') > (cur.last_heard_date ?? '')) {
        best.set(key, { ...s, body_name: b.body_name, governing_body_id: b.governing_body_id })
      }
    }
  }
  return [...best.values()]
    .sort((a, b) => (b.last_heard_date ?? '').localeCompare(a.last_heard_date ?? '') || b.meetings_heard - a.meetings_heard)
    .slice(0, limit)
}

/** Bodies worth listing: a body with meetings or members. Primary first, then by meetings on file (API order). */
export function listedBodies(bodies: GoverningBody[]): GoverningBody[] {
  return bodies.filter((b) => b.meeting_count > 0 || b.member_count > 0)
}
