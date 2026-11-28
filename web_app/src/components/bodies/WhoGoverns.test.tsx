import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { OfficialsHeard, WhoGoverns } from './WhoGoverns'
import type { JurisdictionBodies } from '../../lib/governingBodies'

const data: JurisdictionBodies = {
  jurisdiction_id: 'tuscaloosa_0177256',
  jurisdiction_name: 'Tuscaloosa',
  state_code: 'AL',
  state: 'Alabama',
  bodies: [
    {
      governing_body_id: 'g-council',
      body_name: 'City Council',
      body_type: 'council',
      is_primary: true,
      meeting_count: 361,
      first_meeting_date: '2020-01-07',
      last_meeting_date: '2026-11-17',
      member_count: 7,
      members: [
        { body_membership_id: 'a', person_id: 'p-maddox', member_name: 'Walt Maddox', role: 'mayor', role_title: 'Mayor', district: null, start_date: null, end_date: null, is_current: true, source: 'officials' },
      ],
      recent_speakers: [
        { person_id: 'p-maddox', member_name: 'Walt Maddox', role: 'mayor', meetings_heard: 9, last_heard_date: '2026-11-17', moment_url: 'https://www.youtube.com/watch?v=abc&t=331s', attribution_method: 'chair_call' },
      ],
    },
    {
      governing_body_id: 'g-pz',
      body_name: 'Planning and Zoning Commission',
      body_type: 'planning_zoning',
      is_primary: false,
      meeting_count: 42,
      first_meeting_date: null,
      last_meeting_date: null,
      member_count: 0,
      members: [],
      recent_speakers: [],
    },
  ],
}

const html = (el: JSX.Element) => renderToStaticMarkup(<MemoryRouter>{el}</MemoryRouter>)

describe('WhoGoverns', () => {
  it('names the place in the heading and links each body to its page', () => {
    const out = html(<WhoGoverns data={data} />)
    expect(out).toContain('Who governs Tuscaloosa')
    expect(out).toContain('/bodies/g-council')
    expect(out).toContain('361 meetings on file · 7 people')
    // A body with no members on file says so; no number is invented.
    expect(out).toContain('42 meetings on file · Members not on file')
  })

  it('shows an explicit empty state', () => {
    const out = html(<WhoGoverns data={{ ...data, bodies: [] }} />)
    expect(out).toContain('No governing bodies on file for Tuscaloosa yet.')
  })
})

describe('OfficialsHeard', () => {
  it('links the official to their person page and the play button to the moment', () => {
    const out = html(<OfficialsHeard data={data} />)
    expect(out).toContain('/person/p-maddox')
    expect(out).toContain('https://www.youtube.com/watch?v=abc&amp;t=331s')
    expect(out).toContain('Last called on by the chair Nov 17, 2026')
  })

  it('says when nobody matched', () => {
    const out = html(<OfficialsHeard data={{ ...data, bodies: [data.bodies[1]] }} />)
    expect(out).toContain('No officials matched in recent recordings for Tuscaloosa yet.')
  })
})
