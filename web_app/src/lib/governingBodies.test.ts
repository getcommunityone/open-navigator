import { describe, expect, it } from 'vitest'
import {
  formatDay,
  groupMembers,
  listedBodies,
  meetingCountLabel,
  memberCountLabel,
  memberLine,
  officialsHeard,
  roleLabel,
  type BodyMember,
  type GoverningBody,
} from './governingBodies'

const m = (over: Partial<BodyMember>): BodyMember => ({
  body_membership_id: Math.random().toString(36),
  person_id: null,
  member_name: 'X',
  role: 'council_member',
  role_title: null,
  district: null,
  start_date: null,
  end_date: null,
  is_current: true,
  source: 'officials',
  ...over,
})

const body = (over: Partial<GoverningBody>): GoverningBody => ({
  governing_body_id: 'b',
  body_name: 'City Council',
  body_type: 'council',
  is_primary: true,
  meeting_count: 0,
  first_meeting_date: null,
  last_meeting_date: null,
  member_count: 0,
  members: [],
  recent_speakers: [],
  ...over,
})

describe('governingBodies helpers', () => {
  it('labels roles with the source title when there is one', () => {
    expect(roleLabel('council_member', 'City Councilor')).toBe('City Councilor')
    expect(roleLabel('president_pro_tem', null)).toBe('President pro tem')
    expect(roleLabel(null)).toBe('Member')
    expect(memberLine({ role: 'council_member', role_title: 'City Councilor', district: 'District 2' })).toBe(
      'City Councilor · District 2',
    )
  })

  it('groups one person with two roles, and keeps a past seat apart', () => {
    const seats = groupMembers([
      m({ person_id: 'p1', member_name: 'Raevan Howard', role_title: 'City Councilor', district: 'District 2' }),
      m({ person_id: 'p1', member_name: 'Raevan Howard', role: 'president_pro_tem', role_title: 'President Pro Tempore', district: 'District 2' }),
      m({ person_id: 'p2', member_name: 'Kip Tyner', is_current: false, end_date: '2026-09-18', district: 'District 5' }),
    ])
    expect(seats).toHaveLength(2)
    expect(seats[0].lines).toEqual(['City Councilor · District 2', 'President Pro Tempore · District 2'])
    expect(seats[1].is_current).toBe(false)
    expect(seats[1].end_date).toBe('2026-09-18')
  })

  it('says when there are no meetings or members instead of a number', () => {
    expect(meetingCountLabel(0)).toBe('No meetings on file yet')
    expect(meetingCountLabel(1)).toBe('1 meeting on file')
    expect(meetingCountLabel(361)).toBe('361 meetings on file')
    expect(memberCountLabel(0)).toBe('Members not on file')
    expect(memberCountLabel(7)).toBe('7 people')
  })

  it('formats API dates without a timezone shift', () => {
    expect(formatDay('2026-11-17')).toBe('Nov 17, 2026')
    expect(formatDay(null)).toBe('—')
  })

  it('lists each official once with their latest moment, newest first', () => {
    const heard = officialsHeard([
      body({
        governing_body_id: 'council',
        recent_speakers: [
          { person_id: 'p1', member_name: 'Walt Maddox', role: 'mayor', meetings_heard: 9, last_heard_date: '2026-11-03', moment_url: 'u1', attribution_method: 'chair_call' },
        ],
      }),
      body({
        governing_body_id: 'finance',
        body_name: 'Finance Committee',
        recent_speakers: [
          { person_id: 'p1', member_name: 'Walt Maddox', role: 'mayor', meetings_heard: 2, last_heard_date: '2026-11-17', moment_url: 'u2', attribution_method: 'chair_call' },
          { person_id: 'p2', member_name: 'Lee Busby', role: 'council_member', meetings_heard: 6, last_heard_date: '2026-10-27', moment_url: null, attribution_method: 'roll_call' },
        ],
      }),
    ])
    expect(heard.map((h) => [h.member_name, h.body_name, h.moment_url])).toEqual([
      ['Walt Maddox', 'Finance Committee', 'u2'],
      ['Lee Busby', 'Finance Committee', null],
    ])
  })

  it('hides bodies with neither meetings nor members', () => {
    expect(listedBodies([body({ meeting_count: 0, member_count: 0 }), body({ meeting_count: 3 })])).toHaveLength(1)
  })
})
