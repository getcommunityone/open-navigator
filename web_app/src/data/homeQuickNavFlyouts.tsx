import type { ReactNode } from 'react'
import type { HomeQuickNavGroupId } from './exploreActionPhases'
import { CAUSES } from './causes'

const S = '#2d6b65'

function Ico({ children, stroke = S }: { children: ReactNode; stroke?: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {children}
    </svg>
  )
}

export const flyoutIcons = {
  roads: (stroke = S) => (
    <Ico stroke={stroke}>
      <path d="M3 17l6-12 6 12" />
      <path d="M9 17l6-12 6 12" />
    </Ico>
  ),
  schools: (stroke = S) => (
    <Ico stroke={stroke}>
      <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
      <path d="M6 12v5c3 3 9 3 12 0v-5" />
    </Ico>
  ),
  safety: (stroke = S) => (
    <Ico stroke={stroke}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </Ico>
  ),
  family: (stroke = S) => (
    <Ico stroke={stroke}>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </Ico>
  ),
  health: (stroke = S) => (
    <Ico stroke={stroke}>
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </Ico>
  ),
  other: (stroke = S) => (
    <Ico stroke={stroke}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </Ico>
  ),
  person: (stroke = S) => (
    <Ico stroke={stroke}>
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </Ico>
  ),
  globe: (stroke = S) => (
    <Ico stroke={stroke}>
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </Ico>
  ),
  people: (stroke = S) => (
    <Ico stroke={stroke}>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </Ico>
  ),
  target: (stroke = S) => (
    <Ico stroke={stroke}>
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </Ico>
  ),
  building: (stroke = S) => (
    <Ico stroke={stroke}>
      <rect x="4" y="2" width="16" height="20" rx="2" ry="2" />
      <path d="M9 22v-4h6v4" />
      <path d="M8 6h.01M12 6h.01M16 6h.01M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01" />
    </Ico>
  ),
  capitol: (stroke = S) => (
    <Ico stroke={stroke}>
      <path d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-4h6v4" />
      <path d="M9 10h6M9 14h6" />
    </Ico>
  ),
  dollar: (stroke = S) => (
    <Ico stroke={stroke}>
      <line x1="12" y1="1" x2="12" y2="23" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </Ico>
  ),
  phone: (stroke = S) => (
    <Ico stroke={stroke}>
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 13a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 2.18h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 9.91a16 16 0 0 0 6.06 6.06l.9-.9a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 21.73 17z" />
    </Ico>
  ),
  vote: (stroke = S) => (
    <Ico stroke={stroke}>
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </Ico>
  ),
  monitor: (stroke = S) => (
    <Ico stroke={stroke}>
      <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </Ico>
  ),
  calendar: (stroke = S) => (
    <Ico stroke={stroke}>
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </Ico>
  ),
  bell: (stroke = S) => (
    <Ico stroke={stroke}>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </Ico>
  ),
  database: (stroke = S) => (
    <Ico stroke={stroke}>
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </Ico>
  ),
  lightning: (stroke = S) => (
    <Ico stroke={stroke}>
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </Ico>
  ),
  code: (stroke = S) => (
    <Ico stroke={stroke}>
      <polyline points="16 18 22 12 16 6" />
      <polyline points="8 6 2 12 8 18" />
    </Ico>
  ),
  globeAlt: (stroke = S) => (
    <Ico stroke={stroke}>
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a14.5 14.5 0 0 1 0 20 14.5 14.5 0 0 1 0-20" />
    </Ico>
  ),
} as const

export type FlyoutIconKey = keyof typeof flyoutIcons

export type HomeFlyoutItem = {
  id: string
  label: string
  description: string
  tag: string
  hot?: boolean
  to: string
  external?: boolean
  iconKey: FlyoutIconKey
}

function apiDocsUrl(): string {
  return import.meta.env.PROD ? 'https://www.communityone.com/api/docs' : 'http://localhost:8000/docs'
}

function causesToReportFlyoutItems(): HomeFlyoutItem[] {
  return CAUSES.map((c) => ({
    id: c.id,
    iconKey: c.iconKey,
    label: c.label,
    description: c.desc,
    tag: c.tag,
    hot: c.hot,
    to: c.to,
    external: c.to.startsWith('http'),
  }))
}

export const HOME_QUICK_NAV_FLYOUTS: Record<HomeQuickNavGroupId, HomeFlyoutItem[]> = {
  cause: causesToReportFlyoutItems(),
  plan: [
    {
      id: 'personal',
      iconKey: 'person',
      label: 'Personal Path',
      description: 'I need help — find services and information for me',
      tag: 'For me',
      to: '/services',
    },
    {
      id: 'macro',
      iconKey: 'globe',
      label: 'Macro Path',
      description: 'I want to create change in my community',
      tag: 'For my community',
      hot: true,
      to: '/explore',
    },
    {
      id: 'professional',
      iconKey: 'capitol',
      label: 'Professional Path',
      description: 'State legislators, county administrators, and nonprofit champions',
      tag: 'For my role',
      to: '/explore#explore-plan-path',
    },
    {
      id: 'allies',
      iconKey: 'people',
      label: 'Identify Allies',
      description: 'Find officials, nonprofits, and neighbors fighting for your cause',
      tag: 'Strategy',
      to: '/people',
    },
    {
      id: 'success',
      iconKey: 'target',
      label: 'Define Success',
      description: 'Set measurable goals and track your progress',
      tag: 'Outcomes',
      to: '/analytics',
    },
  ],
  find: [
    {
      id: 'np',
      iconKey: 'building',
      label: 'Nonprofits Near Me',
      description: '1.8M organizations mapped across 5 states',
      tag: 'Free',
      to: '/nonprofits',
    },
    {
      id: 'officials',
      iconKey: 'capitol',
      label: 'Elected Officials',
      description: 'Voting records, contact info, decision patterns',
      tag: '75K+ leaders',
      to: '/people',
    },
    {
      id: 'grants',
      iconKey: 'dollar',
      label: 'Grants & Funding',
      description: 'Federal, state, and foundation opportunities',
      tag: '1,000s available',
      // Grants search: historical 990 grantmaking + open Grants.gov funding.
      // (The bare /opportunities route is the unrelated advocacy-opportunities page.)
      to: '/search?types=grants,grant_opportunities',
    },
    {
      id: 'svc',
      iconKey: 'phone',
      label: 'Community Services',
      description: 'Government services, hotlines, local resources',
      tag: 'Services',
      to: '/services',
    },
  ],
  track: [
    {
      id: 'vote',
      iconKey: 'vote',
      label: 'Vote Tracker',
      description: 'How officials voted on issues that matter to you',
      tag: 'Real-time',
      hot: true,
      to: '/documents',
    },
    {
      id: 'budget',
      iconKey: 'monitor',
      label: 'Budget Watch',
      description: 'Flag when line items shift year over year',
      tag: 'Analysis',
      to: '/analytics',
    },
    {
      id: 'meetings',
      iconKey: 'calendar',
      label: 'Upcoming Meetings',
      description: 'Agendas, dates, how to attend or comment',
      tag: '90K+ jurisdictions',
      to: '/events',
    },
    {
      id: 'alerts',
      iconKey: 'bell',
      label: 'Set Alerts',
      description: 'Get notified when your keywords hit an agenda',
      tag: 'Free',
      to: '/search',
    },
  ],
  build: [
    {
      id: 'data-explorer',
      iconKey: 'globeAlt',
      label: 'Explore data',
      description: 'ACS map and scorecard — national, state, and place trends',
      tag: 'Interactive',
      hot: true,
      to: '/data-explorer',
    },
    {
      id: 'hf',
      iconKey: 'database',
      label: 'HuggingFace Datasets',
      description: 'Meeting transcripts, legislation — MIT license',
      tag: 'Open source',
      hot: true,
      to: 'https://huggingface.co/datasets/CommunityOne/open-navigator-data',
      external: true,
    },
    {
      id: 'playbooks',
      iconKey: 'lightning',
      label: 'Strategy Playbooks',
      description: 'Fork civic tools: vote tracker, meeting monitor',
      tag: 'GitHub',
      to: '/opensource',
    },
    {
      id: 'api',
      iconKey: 'code',
      label: 'API Reference',
      description: 'Query jurisdictions, decisions, and nonprofits',
      tag: 'Developers',
      to: '__API_DOCS__',
      external: true,
    },
    {
      id: 'ecosystem',
      iconKey: 'globeAlt',
      label: 'Civic Tech Ecosystem',
      description: 'Code for America, OpenStates, MySociety',
      tag: 'Community',
      to: 'https://www.openstates.org/',
      external: true,
    },
  ],
}

/** Resolve special `to` tokens after import.meta is available */
export function resolveHomeFlyoutHref(to: string): string {
  if (to === '__API_DOCS__') return apiDocsUrl()
  return to
}

export function homeQuickNavFlyoutItems(id: HomeQuickNavGroupId): HomeFlyoutItem[] {
  return HOME_QUICK_NAV_FLYOUTS[id]
}
