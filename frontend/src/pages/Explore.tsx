import { Link } from 'react-router-dom'
import { useEffect, Fragment } from 'react'
import type { ReactNode } from 'react'
import {
  UserGroupIcon,
  BuildingOfficeIcon,
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
  LightBulbIcon,
  MegaphoneIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline'

interface ExploreCard {
  title: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  path: string
  color: string
  stats?: string
}

interface ActionPhase {
  id: string
  step: string
  title: string
  subtitle: string
  cards: ExploreCard[]
  gridClass: string
}

const CARD_CTA = 'Take the next step →'

/** Step 1 — Pull primary sources: meetings, money, law, verification, census. */
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

/** Step 2 — Interpret and align with people, orgs, and movements. */
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

/** Step 3 — Concrete civic participation. */
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

const ACTION_PHASES: ActionPhase[] = [
  {
    id: 'learn',
    step: '1',
    title: 'Learn what happened',
    subtitle: 'Gather authoritative sources before you speak, fund, or file.',
    cards: phaseLearnCards,
    gridClass: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6',
  },
  {
    id: 'decide',
    step: '2',
    title: 'Decide who to work with',
    subtitle: 'Interpret the record — align with organizations, issues, funders, and decision-makers.',
    cards: phaseDecideCards,
    gridClass: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6',
  },
  {
    id: 'act',
    step: '3',
    title: 'Show up & act',
    subtitle: 'Move from screens to rooms — events, services, ballots, calls, and public comment.',
    cards: phaseActCards,
    gridClass: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6',
  },
  {
    id: 'build',
    step: '4',
    title: 'Build on the data',
    subtitle: 'Extend the commons — open source and hackathons for teams who ship.',
    cards: phaseBuildCards,
    gridClass: 'grid grid-cols-1 md:grid-cols-2 gap-6',
  },
]

const PROCESS_STEPS: { n: string; title: string; blurb: string; icon: typeof LightBulbIcon }[] = [
  { n: '1', title: 'Learn', blurb: 'Meetings, budgets, law, census, fact checks', icon: LightBulbIcon },
  { n: '2', title: 'Decide', blurb: 'Partners, issues, officials, funding', icon: MegaphoneIcon },
  { n: '3', title: 'Act', blurb: 'Events, services, ballots, contact, comment', icon: WrenchScrewdriverIcon },
]

function ActionCard({ option, cta = CARD_CTA }: { option: ExploreCard; cta?: string }): ReactNode {
  const Icon = option.icon
  const isExternal = option.path.startsWith('http')
  const inner = (
    <div className="group bg-white rounded-xl shadow-md hover:shadow-xl transition-all duration-300 overflow-hidden border border-gray-100 hover:border-gray-200">
      <div className="p-6">
        <div
          className="w-14 h-14 rounded-lg flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300"
          style={{ backgroundColor: `${option.color}15` }}
        >
          <div style={{ color: option.color }}>
            <Icon className="h-7 w-7" />
          </div>
        </div>
        <div className="mb-3">
          <h3 className="text-xl font-bold text-gray-900 mb-1 group-hover:text-[#354F52] transition-colors">{option.title}</h3>
          {option.stats ? (
            <p className="text-sm font-medium" style={{ color: option.color }}>
              {option.stats}
            </p>
          ) : null}
        </div>
        <p className="text-gray-600 text-sm leading-relaxed">{option.description}</p>
        <div className="mt-4 flex items-center text-sm font-medium" style={{ color: option.color }}>
          <span className="group-hover:translate-x-1 transition-transform duration-300">{cta}</span>
        </div>
      </div>
      <div
        className="h-1 w-full transform scale-x-0 group-hover:scale-x-100 transition-transform duration-300 origin-left"
        style={{ backgroundColor: option.color }}
      />
    </div>
  )

  if (isExternal) {
    return (
      <a href={option.path} target="_blank" rel="noopener noreferrer">
        {inner}
      </a>
    )
  }
  return <Link to={option.path}>{inner}</Link>
}

export default function Explore() {
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="bg-white shadow-sm border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center max-w-3xl mx-auto">
            <p className="text-xs font-semibold uppercase tracking-widest text-teal-800/90 mb-2">Take action</p>
            <h1 className="text-4xl font-bold text-gray-900 mb-3">From information to impact</h1>
            <p className="text-lg text-gray-600">
              CommunityOne is built as a path: pull the public record, decide who to work with, then show up where decisions
              are made. Pick a step below — each card opens a concrete workflow.
            </p>
          </div>

          <div
            className="mt-8 flex flex-col gap-3 md:flex-row md:flex-wrap md:items-stretch md:justify-center max-w-4xl mx-auto"
            aria-label="Action path: learn, decide, act"
          >
            {PROCESS_STEPS.map((s, i) => {
              const Icon = s.icon
              return (
                <Fragment key={s.n}>
                  <div className="flex flex-1 min-w-[10rem] items-start gap-3 rounded-xl border border-gray-200 bg-slate-50/80 px-4 py-3 text-left shadow-sm">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-teal-800 text-sm font-bold text-white">
                      {s.n}
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <Icon className="h-5 w-5 text-teal-800" aria-hidden />
                        <span className="font-semibold text-gray-900">{s.title}</span>
                      </div>
                      <p className="mt-1 text-xs leading-snug text-gray-600">{s.blurb}</p>
                    </div>
                  </div>
                  {i < PROCESS_STEPS.length - 1 ? (
                    <span
                      className="hidden md:flex shrink-0 items-center self-center px-1 text-lg font-light text-gray-300"
                      aria-hidden
                    >
                      →
                    </span>
                  ) : null}
                </Fragment>
              )
            })}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-16">
        {ACTION_PHASES.map((phase, idx) => (
          <section key={phase.id} aria-labelledby={`phase-${phase.id}`}>
            <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-gray-200 pb-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-teal-800">Step {phase.step}</p>
                <h2 id={`phase-${phase.id}`} className="text-2xl font-bold text-gray-900">
                  {phase.title}
                </h2>
                <p className="mt-1 max-w-3xl text-gray-600">{phase.subtitle}</p>
              </div>
              {idx === 0 ? (
                <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-900 ring-1 ring-emerald-200">
                  Start here if you are new
                </span>
              ) : null}
            </div>
            <div className={phase.gridClass}>
              {phase.cards.map((option) => (
                <ActionCard key={`${phase.id}-${option.title}`} option={option} />
              ))}
            </div>
          </section>
        ))}

        <div className="text-center">
          <div className="bg-white rounded-xl shadow-md p-8 max-w-2xl mx-auto border border-gray-100">
            <h2 className="text-2xl font-bold text-gray-900 mb-3">Need the raw files?</h2>
            <p className="text-gray-600 mb-6">
              Bulk tables, APIs, and documentation for teams building their own workflows on top of the same data.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <a
                href="https://huggingface.co/datasets/CommunityOne/open-navigator-data"
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-3 rounded-lg text-white font-semibold hover:shadow-lg transition-all"
                style={{ backgroundColor: '#354F52' }}
              >
                View on HuggingFace
              </a>
              <a
                href={
                  import.meta.env.PROD
                    ? 'https://www.communityone.com/docs/data-sources/data-model-erd'
                    : 'http://localhost:3000/docs/data-sources/data-model-erd'
                }
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-3 rounded-lg font-semibold hover:shadow-lg transition-all border-2"
                style={{ borderColor: '#354F52', color: '#354F52' }}
              >
                Data model diagram
              </a>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-12 text-center">
        <Link to="/" className="inline-flex items-center text-gray-600 hover:text-gray-900 font-medium transition-colors">
          ← Back to Home
        </Link>
      </div>
    </div>
  )
}
