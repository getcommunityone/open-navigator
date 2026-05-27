import type { ComponentType } from 'react'
import {
  UserGroupIcon,
  BuildingOfficeIcon,
  BuildingLibraryIcon,
  BriefcaseIcon,
  DocumentTextIcon,
  MapIcon,
  ChartBarIcon,
  MicrophoneIcon,
  BellAlertIcon,
  CalendarIcon,
  AcademicCapIcon,
  CheckBadgeIcon,
  PhoneIcon,
  ChatBubbleLeftRightIcon,
  HeartIcon,
  CodeBracketIcon,
  RocketLaunchIcon,
  MapPinIcon,
  ClipboardDocumentListIcon,
} from '@heroicons/react/24/outline'

export interface ExploreCard {
  title: string
  description: string
  icon: ComponentType<{ className?: string }>
  path: string
  color: string
  stats?: string
}

export interface ActionPhase {
  id: string
  step: string
  title: string
  subtitle: string
  cards: ExploreCard[]
  gridClass: string
}

/** Tailwind scroll margin so in-page / hash links clear the fixed `pt-16` header */
export const EXPLORE_SECTION_SCROLL_MARGIN_CLASS = 'scroll-mt-24'

/** DOM id for the cause grid at top of Explore */
export const EXPLORE_CAUSES_ID = 'explore-causes'

export const EXPLORE_PLAN_ID = 'explore-plan'

export const EXPLORE_FIND_HELP_ID = 'explore-find-help'

export const EXPLORE_TRACK_DECISIONS_ID = 'explore-track-decisions'

export const EXPLORE_BUILD_ID = 'explore-build'

export type PlanPathBranchId = 'personal' | 'macro' | 'professional'

export type PlanPlanSubsectionId = 'path' | 'allies' | 'success'

/** Anchor inside **Make a plan** for path / allies / success substeps */
export function explorePlanSubsectionId(id: PlanPlanSubsectionId): string {
  return `explore-plan-${id}`
}

export type HomeQuickNavGroupId = 'cause' | 'plan' | 'find' | 'track' | 'build'

/** Hash target (no `#`) for /explore deep links — order matches sidebar quick nav */
export function homeExploreSectionHash(group: HomeQuickNavGroupId): string {
  switch (group) {
    case 'cause':
      return EXPLORE_CAUSES_ID
    case 'plan':
      return EXPLORE_PLAN_ID
    case 'find':
      return EXPLORE_FIND_HELP_ID
    case 'track':
      return EXPLORE_TRACK_DECISIONS_ID
    case 'build':
      return EXPLORE_BUILD_ID
  }
}

/** Old `#explore-phase-*` and plan subsection bookmarks → current section ids */
export const LEGACY_EXPLORE_HASH_REDIRECT: Record<string, string> = {
  'explore-phase-learn': EXPLORE_TRACK_DECISIONS_ID,
  'explore-phase-decide': EXPLORE_FIND_HELP_ID,
  'explore-phase-act': explorePlanSubsectionId('success'),
  'explore-phase-build': EXPLORE_BUILD_ID,
  'explore-plan-learn': explorePlanSubsectionId('path'),
  'explore-plan-decide': explorePlanSubsectionId('allies'),
  'explore-plan-act': explorePlanSubsectionId('success'),
  'explore-plan-personal': explorePlanSubsectionId('path'),
  'explore-plan-macro': explorePlanSubsectionId('path'),
  'explore-plan-professional': explorePlanSubsectionId('path'),
}

const phaseLearnCards: ExploreCard[] = [
  {
    title: 'Policy Decisions',
    description:
      'Start with the record: agendas, votes, deferrals, and who said what in public meetings across jurisdictions.',
    icon: DocumentTextIcon,
    path: '/documents',
    color: '#354F52',
    stats: '500K+ meeting pages',
  },
  {
    title: 'Budget Analysis',
    description:
      'Follow the money — compare budgets to meeting rhetoric so you know what is funded versus what is only talked about.',
    icon: ChartBarIcon,
    path: '/analytics',
    color: '#52796F',
    stats: 'Rhetoric vs. reality',
  },
  {
    title: 'Policy Map',
    description:
      'See how issues move through state capitols: bills, sponsors, and status so you are arguing from the text, not the headline.',
    icon: MapIcon,
    path: '/policy-map',
    color: '#84A98C',
    stats: '13K+ bills',
  },
  {
    title: 'Fact-Checking',
    description:
      'Stress-test claims from meetings and campaigns against trusted fact-check sources before you repeat them.',
    icon: MicrophoneIcon,
    path: '/fact-checking',
    color: '#CAD2C5',
    stats: 'Verify, then share',
  },
  {
    title: 'ACS map & scorecard',
    description:
      'Layer census context — browse the national map, drill into states, then open the scorecard for multi-year trends.',
    icon: MapIcon,
    path: '/data-explorer',
    color: '#2f5d62',
    stats: 'National → state → trends',
  },
]

const phaseDecideCards: ExploreCard[] = [
  {
    title: 'Nonprofits & Churches',
    description:
      'Find partners already doing the work — financials and program footprints help you choose who to support or cite.',
    icon: BuildingOfficeIcon,
    path: '/nonprofits',
    color: '#354F52',
    stats: '43K+ organizations',
  },
  {
    title: 'Advocacy Topics',
    description:
      'See what communities are organizing around now so your action matches real demand, not a generic template.',
    icon: BellAlertIcon,
    path: '/advocacy-topics',
    color: '#52796F',
    stats: 'Live issues',
  },
  {
    title: 'Grants & Funding',
    description:
      'Map funding streams and outcomes so proposals, testimony, or coalition asks are grounded in how money flows.',
    icon: BriefcaseIcon,
    path: '/analytics',
    color: '#84A98C',
    stats: 'Funding intelligence',
  },
  {
    title: 'Elected Officials',
    description:
      'Know who holds the pen: local, state, and school decision-makers before you call, write, or show up.',
    icon: UserGroupIcon,
    path: '/people',
    color: '#CAD2C5',
    stats: '100K+ officials',
  },
]

const phaseActCards: ExploreCard[] = [
  {
    title: 'Community Events',
    description: 'Put what you learned on the calendar — hearings, town halls, and public sessions where decisions open up.',
    icon: CalendarIcon,
    path: '/events',
    color: '#354F52',
    stats: 'Show up',
  },
  {
    title: 'Training & Services',
    description: 'Use programs and workshops to build skills (and connect neighbors) after you have identified gaps.',
    icon: AcademicCapIcon,
    path: '/services',
    color: '#52796F',
    stats: 'Learn & grow',
  },
  {
    title: 'Voter Registration',
    description: 'Channel insight into ballots — registration, polling places, and election context for your area.',
    icon: CheckBadgeIcon,
    path: '/analytics?topic=elections',
    color: '#84A98C',
    stats: 'Vote informed',
  },
  {
    title: 'Contact Your Representatives',
    description: 'Turn research into outreach — direct lines for councils, legislatures, and school boards.',
    icon: PhoneIcon,
    path: '/people?view=contact',
    color: '#CAD2C5',
    stats: 'Make the call',
  },
  {
    title: 'Submit Feedback',
    description: 'Use formal comment windows and public feedback routes so your position is on the record.',
    icon: ChatBubbleLeftRightIcon,
    path: '/opportunities?type=feedback',
    color: '#52796F',
    stats: 'Official input',
  },
  {
    title: 'Community Resources',
    description: 'Connect people to food, housing, health, and family supports when data surfaces unmet needs.',
    icon: HeartIcon,
    path: '/nonprofits?category=family-services',
    color: '#84A98C',
    stats: 'Help neighbors',
  },
]

const phaseBuildCards: ExploreCard[] = [
  {
    title: 'Jurisdiction Data Quality',
    description:
      'County (NACo), city (USCM / mayors-style directories), and school district (NCES) website mapping rates — plus dbt gold tables for LLM exports.',
    icon: ChartBarIcon,
    path: '/data-explorer/jurisdiction-quality',
    color: '#1d7874',
    stats: 'Coverage & sources',
  },
  {
    title: 'Explore data',
    description:
      'ACS map and scorecard — browse the national map, drill into states and places, and compare multi-year trends.',
    icon: MapIcon,
    path: '/data-explorer',
    color: '#2f5d62',
    stats: 'Interactive',
  },
  {
    title: 'Open Source Projects',
    description: 'Fork pipelines, models, and civic UX so the same evidence others read can power your own tools.',
    icon: CodeBracketIcon,
    path: '/opensource',
    color: '#354F52',
    stats: 'Ship together',
  },
  {
    title: 'Hackathons for Good',
    description: 'Prototype fixes fast — from transparency dashboards to intake bots — alongside other builders.',
    icon: RocketLaunchIcon,
    path: '/hackathons',
    color: '#52796F',
    stats: '48-hour impact',
  },
]

const trackDecisionsCards: ExploreCard[] = [
  {
    title: 'Vote Tracker',
    description: 'See how officials voted on the issues that matter to you — meeting pages and roll calls in one place.',
    icon: DocumentTextIcon,
    path: '/documents',
    color: '#354F52',
    stats: 'Real-time',
  },
  {
    title: 'Budget Watch',
    description: 'Flag when line items shift year over year so rhetoric can be checked against appropriations.',
    icon: ChartBarIcon,
    path: '/analytics',
    color: '#52796F',
    stats: 'Analysis',
  },
  {
    title: 'Upcoming Meetings',
    description: 'Agendas, dates, and how to attend or comment before the window closes.',
    icon: CalendarIcon,
    path: '/events',
    color: '#84A98C',
    stats: '90K+ jurisdictions',
  },
  {
    title: 'Set Alerts',
    description: 'Get notified when your keywords hit an agenda or new filing lands in search.',
    icon: BellAlertIcon,
    path: '/search',
    color: '#2f5d62',
    stats: 'Free',
  },
]

const findHelpCards: ExploreCard[] = [
  {
    title: 'Nonprofits Near Me',
    description:
      'Organizations mapped across multiple states — filter by issue and location before you reach out.',
    icon: BuildingOfficeIcon,
    path: '/nonprofits',
    color: '#354F52',
    stats: '1.8M+ organizations',
  },
  {
    title: 'Elected Officials',
    description: 'Voting patterns, contact info, and who holds the pen on the issues that matter to you.',
    icon: UserGroupIcon,
    path: '/people',
    color: '#52796F',
    stats: '75K+ leaders',
  },
  {
    title: 'Grants & Funding',
    description: 'Federal, state, and foundation opportunities grounded in your topic and geography.',
    icon: BriefcaseIcon,
    path: '/opportunities',
    color: '#84A98C',
    stats: '1,000s available',
  },
  {
    title: 'Community Services',
    description: 'Government services, hotlines, and local resources when someone needs direct help.',
    icon: PhoneIcon,
    path: '/services',
    color: '#CAD2C5',
    stats: 'Services',
  },
]

const defineSuccessPlanCards: ExploreCard[] = [...trackDecisionsCards, ...phaseActCards]

const planPersonalAlliesCards: ExploreCard[] = [
  findHelpCards[3]!,
  findHelpCards[0]!,
  findHelpCards[1]!,
  findHelpCards[2]!,
  phaseActCards[1]!,
]

const planMacroAlliesCards: ExploreCard[] = [...phaseDecideCards]

const planPersonalSuccessCards: ExploreCard[] = [
  trackDecisionsCards[3]!,
  trackDecisionsCards[2]!,
  phaseActCards[3]!,
  phaseActCards[1]!,
  phaseActCards[2]!,
  phaseActCards[5]!,
]

const planMacroSuccessCards: ExploreCard[] = [...defineSuccessPlanCards]

const planProfessionalPathCards: ExploreCard[] = [
  {
    title: 'State Legislator',
    description:
      'Follow bills, committees, and roll calls in your chamber — work from the statutory text, sponsors, and status before hearings and votes.',
    icon: MapIcon,
    path: '/policy-map',
    color: '#354F52',
    stats: '13K+ bills',
  },
  {
    title: 'County Administrator',
    description:
      'Navigate counties, cities, and school districts you serve — meeting records, portals, and discovery status in one directory.',
    icon: MapPinIcon,
    path: '/jurisdictions',
    color: '#52796F',
    stats: '90K+ jurisdictions',
  },
  {
    title: 'Nonprofit Champions',
    description:
      'Spotlight 501(c)(3) partners — financial transparency, programs, and coalitions you can cite in budgets, boards, and public meetings.',
    icon: BuildingLibraryIcon,
    path: '/nonprofits',
    color: '#84A98C',
    stats: '43K+ organizations',
  },
]

const planProfessionalAlliesCards: ExploreCard[] = [
  phaseLearnCards[0]!,
  phaseLearnCards[2]!,
  phaseDecideCards[0]!,
  phaseDecideCards[3]!,
  phaseDecideCards[1]!,
  phaseDecideCards[2]!,
]

const planProfessionalSuccessCards: ExploreCard[] = [...defineSuccessPlanCards]

export const PLAN_PATH_BRANCH_OPTIONS: {
  branch: PlanPathBranchId
  title: string
  subtitle: string
  tag: string
  cards: ExploreCard[]
  gridClass: string
}[] = [
  {
    branch: 'personal',
    title: 'Personal Path',
    subtitle: 'I need help — find services and information for me',
    tag: 'For me',
    cards: findHelpCards,
    gridClass: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6',
  },
  {
    branch: 'macro',
    title: 'Macro Path',
    subtitle: 'I want to create change in my community',
    tag: 'For my community',
    cards: phaseLearnCards,
    gridClass: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6',
  },
  {
    branch: 'professional',
    title: 'Professional Path',
    subtitle: 'I work in government or the nonprofit sector and need institutional tools',
    tag: 'For my role',
    cards: planProfessionalPathCards,
    gridClass: 'grid grid-cols-1 md:grid-cols-3 gap-6',
  },
]

export const PLAN_IDENTIFY_ALLIES_BY_BRANCH: Record<
  PlanPathBranchId,
  { subtitle: string; cards: ExploreCard[]; gridClass: string }
> = {
  personal: {
    subtitle:
      'Find programs, officials, and funds you can use — services, nonprofits, and support close to home.',
    cards: planPersonalAlliesCards,
    gridClass: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6',
  },
  macro: {
    subtitle: 'Find officials, nonprofits, and neighbors fighting for your cause',
    cards: planMacroAlliesCards,
    gridClass: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6',
  },
  professional: {
    subtitle: 'Policy decisions, maps, nonprofits, officials, advocacy topics, and funding streams for your role',
    cards: planProfessionalAlliesCards,
    gridClass: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6',
  },
}

export const PLAN_DEFINE_SUCCESS_BY_BRANCH: Record<
  PlanPathBranchId,
  { subtitle: string; cards: ExploreCard[]; gridClass: string }
> = {
  personal: {
    subtitle: 'Get reminders, show up when it counts, and track steps that matter to you.',
    cards: planPersonalSuccessCards,
    gridClass: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6',
  },
  macro: {
    subtitle: 'Set measurable goals and track your progress',
    cards: planMacroSuccessCards,
    gridClass: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6',
  },
  professional: {
    subtitle: 'Set measurable goals and track your progress',
    cards: planProfessionalSuccessCards,
    gridClass: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6',
  },
}

export const FIND_HELP_SECTION = {
  title: 'Find help',
  subtitle:
    'Nonprofits, programs, and family supports — start where someone already solved the intake problem.',
  cards: findHelpCards,
  gridClass: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6',
} as const

export const TRACK_DECISIONS_SECTION = {
  title: 'Track decisions',
  subtitle: 'Meetings, budgets, maps, and verification — stay oriented before you speak or file.',
  cards: trackDecisionsCards,
  gridClass: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6',
} as const

export const BUILD_PHASE: ActionPhase = {
  id: 'build',
  step: '',
  title: 'Build with data',
  subtitle: 'Extend the commons — open source and hackathons for teams who ship.',
  cards: phaseBuildCards,
  gridClass: 'grid grid-cols-1 md:grid-cols-3 gap-6',
}

/** Top-of-page Explore buttons — same order and labels as sidebar quick nav */
export const EXPLORE_PRIMARY_NAV: {
  key: HomeQuickNavGroupId
  targetId: string
  title: string
  blurb: string
  Icon: ComponentType<{ className?: string }>
}[] = [
  {
    key: 'cause',
    targetId: EXPLORE_CAUSES_ID,
    title: 'Choose a cause',
    blurb: 'Roads, schools, safety, family, health, or something else.',
    Icon: MapPinIcon,
  },
  {
    key: 'plan',
    targetId: EXPLORE_PLAN_ID,
    title: 'Make a plan',
    blurb: 'Issues, officials, and funding streams.',
    Icon: ClipboardDocumentListIcon,
  },
  {
    key: 'find',
    targetId: EXPLORE_FIND_HELP_ID,
    title: 'Find help',
    blurb: 'Nonprofits, programs, and family supports.',
    Icon: HeartIcon,
  },
  {
    key: 'track',
    targetId: EXPLORE_TRACK_DECISIONS_ID,
    title: 'Track decisions',
    blurb: 'Meetings, budgets, maps, and verification.',
    Icon: ChartBarIcon,
  },
  {
    key: 'build',
    targetId: EXPLORE_BUILD_ID,
    title: 'Build with data',
    blurb: 'Open datasets, APIs, and civic tooling.',
    Icon: CodeBracketIcon,
  },
]
