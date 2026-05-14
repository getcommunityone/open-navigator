import { Link, useLocation } from 'react-router-dom'
import { useLayoutEffect, Fragment, useState, type ReactNode } from 'react'
import { ChevronRightIcon } from '@heroicons/react/24/outline'
import {
  BUILD_PHASE,
  EXPLORE_BUILD_ID,
  EXPLORE_CAUSES_ID,
  EXPLORE_FIND_HELP_ID,
  EXPLORE_PLAN_ID,
  EXPLORE_PRIMARY_NAV,
  EXPLORE_SECTION_SCROLL_MARGIN_CLASS,
  EXPLORE_TRACK_DECISIONS_ID,
  FIND_HELP_SECTION,
  LEGACY_EXPLORE_HASH_REDIRECT,
  PLAN_DEFINE_SUCCESS_BY_BRANCH,
  PLAN_IDENTIFY_ALLIES_BY_BRANCH,
  PLAN_PATH_BRANCH_OPTIONS,
  TRACK_DECISIONS_SECTION,
  explorePlanSubsectionId,
  type ExploreCard,
  type PlanPathBranchId,
} from '../data/exploreActionPhases'
import { CAUSES } from '../data/causes'
import { flyoutIcons } from '../data/homeQuickNavFlyouts'

const CARD_CTA = 'Take the next step →'

const PLAN_BRANCH_TAG_CLASS: Record<PlanPathBranchId, string> = {
  personal: 'rounded-full bg-sky-100 px-3 py-0.5 text-xs font-semibold text-sky-900 ring-1 ring-sky-200',
  macro: 'rounded-full bg-amber-50 px-3 py-0.5 text-xs font-semibold text-amber-900 ring-1 ring-amber-200',
  professional:
    'rounded-full bg-violet-50 px-3 py-0.5 text-xs font-semibold text-violet-900 ring-1 ring-violet-200',
}

const PLAN_SUP_TAG_CLASS: Record<'allies' | 'success', string> = {
  allies: 'rounded-full bg-sky-100 px-3 py-0.5 text-xs font-semibold text-sky-900 ring-1 ring-sky-200',
  success: 'rounded-full bg-sky-100 px-3 py-0.5 text-xs font-semibold text-sky-900 ring-1 ring-sky-200',
}

function scrollToExploreTarget(targetId: string) {
  document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

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

const CAUSE_ACCENT = ['#354F52', '#52796F', '#84A98C', '#2f5d62', '#52796F', '#354F52'] as const

function CauseEntryCard({ cause, color }: { cause: (typeof CAUSES)[number]; color: string }) {
  const icon = flyoutIcons[cause.iconKey]()
  const isExternal = cause.to.startsWith('http')
  const inner = (
    <div className="group flex h-full flex-col rounded-xl border border-gray-100 bg-white p-5 shadow-md transition-all duration-300 hover:border-gray-200 hover:shadow-xl">
      <div
        className="mb-3 flex h-12 w-12 items-center justify-center rounded-lg transition-transform group-hover:scale-105"
        style={{ backgroundColor: `${color}18` }}
      >
        <span style={{ color }}>{icon}</span>
      </div>
      <h3 className="mb-1 text-lg font-bold text-gray-900 group-hover:text-[#354F52]">{cause.label}</h3>
      <p className="mb-3 flex-1 text-sm leading-relaxed text-gray-600">{cause.desc}</p>
      <span
        className="mt-auto w-fit rounded-full px-2 py-0.5 text-[10px] font-bold"
        style={{
          background: cause.hot ? '#fff4d6' : `${color}15`,
          color: cause.hot ? '#a06000' : color,
        }}
      >
        {cause.tag}
        {cause.hot ? ' 🔥' : ''}
      </span>
      <div className="mt-3 text-sm font-medium" style={{ color }}>
        <span className="group-hover:translate-x-0.5 inline-block transition-transform">{CARD_CTA}</span>
      </div>
    </div>
  )
  if (isExternal) {
    return (
      <a href={cause.to} target="_blank" rel="noopener noreferrer" className="block h-full">
        {inner}
      </a>
    )
  }
  return (
    <Link to={cause.to} className="block h-full">
      {inner}
    </Link>
  )
}

export default function Explore() {
  const location = useLocation()
  const [planBranch, setPlanBranch] = useState<PlanPathBranchId | null>(null)

  useLayoutEffect(() => {
    const raw = location.hash.replace(/^#/, '')
    if (!raw) {
      window.scrollTo({ top: 0, behavior: 'auto' })
      return
    }
    const targetId = LEGACY_EXPLORE_HASH_REDIRECT[raw] ?? raw
    requestAnimationFrame(() => {
      document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }, [location.pathname, location.hash])

  return (
    <div className="min-h-screen bg-slate-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 sm:pt-8 pb-2">
        <div className="rounded-2xl border border-slate-400/40 bg-white shadow-[0_4px_28px_-10px_rgba(15,23,42,0.18)]">
          <div className="px-4 sm:px-6 lg:px-8 py-8">
            <div className="text-center max-w-3xl mx-auto">
              <p className="text-xs font-semibold uppercase tracking-widest text-teal-800/90 mb-2">Take action</p>
              <h1 className="text-4xl font-bold text-gray-900 mb-3">From information to impact</h1>
              <p className="text-lg text-gray-600">
                Start by choosing a cause, make a plan (learn the record, decide who to work with, then show up), find help when
                someone needs direct support, track the decisions that matter, and build on open data.
              </p>
            </div>

            <div
              className="mt-8 flex flex-col gap-3 md:flex-row md:flex-wrap md:items-stretch md:justify-center max-w-6xl mx-auto"
              aria-label="Explore: choose a cause, make a plan, find help, track decisions, build with data"
            >
              {EXPLORE_PRIMARY_NAV.map((step, i) => {
                const Icon = step.Icon
                const next = EXPLORE_PRIMARY_NAV[i + 1]
                return (
                  <Fragment key={step.key}>
                    <button
                      type="button"
                      onClick={() => scrollToExploreTarget(step.targetId)}
                      className="flex flex-1 min-w-[10rem] cursor-pointer items-start gap-3 rounded-xl border border-gray-200 bg-slate-50/90 px-4 py-3 text-left shadow-sm transition-colors hover:border-teal-700/40 hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
                    >
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-teal-800 text-white">
                        <Icon className="h-5 w-5" aria-hidden />
                      </span>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-gray-900">{step.title}</span>
                        </div>
                        <p className="mt-1 text-xs leading-snug text-gray-600">{step.blurb}</p>
                      </div>
                    </button>
                    {next ? (
                      <button
                        type="button"
                        className="hidden md:flex shrink-0 items-center self-center rounded-full p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-teal-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
                        aria-label={`Jump to ${next.title}`}
                        onClick={() => scrollToExploreTarget(next.targetId)}
                      >
                        <ChevronRightIcon className="h-6 w-6" aria-hidden />
                      </button>
                    ) : null}
                  </Fragment>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-16">
        <section
          id={EXPLORE_CAUSES_ID}
          className={EXPLORE_SECTION_SCROLL_MARGIN_CLASS}
          aria-labelledby="explore-causes-heading"
        >
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-gray-200 pb-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-teal-800">Start</p>
              <h2 id="explore-causes-heading" className="text-2xl font-bold text-gray-900">
                Choose a cause
              </h2>
              <p className="mt-1 max-w-3xl text-gray-600">
                Pick where you are starting — each card sends you to search, services, or a formal route that fits.
              </p>
            </div>
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-900 ring-1 ring-emerald-200">
              Start here if you are new
            </span>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {CAUSES.map((cause, i) => (
              <CauseEntryCard key={cause.id} cause={cause} color={CAUSE_ACCENT[i % CAUSE_ACCENT.length]!} />
            ))}
          </div>
        </section>

        <section
          id={EXPLORE_PLAN_ID}
          className={`${EXPLORE_SECTION_SCROLL_MARGIN_CLASS} space-y-16`}
          aria-labelledby="explore-plan-heading"
        >
          <div className="flex flex-wrap items-end justify-between gap-3 border-b border-gray-200 pb-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-teal-800">Plan</p>
              <h2 id="explore-plan-heading" className="text-2xl font-bold text-gray-900">
                Make a plan
              </h2>
              <p className="mt-1 max-w-3xl text-gray-600">
                Choose <strong>Personal Path</strong>, <strong>Macro Path</strong>, or <strong>Professional Path</strong>{' '}
                (one at a time). Your Identify Allies and Define Success steps update from that choice.
              </p>
            </div>
          </div>

          <section
            id={explorePlanSubsectionId('path')}
            className={EXPLORE_SECTION_SCROLL_MARGIN_CLASS}
            aria-labelledby="plan-path-heading"
          >
            <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-gray-200 pb-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-teal-800">Plan · Step 1 of 4</p>
                <h3 id="plan-path-heading" className="text-2xl font-bold text-gray-900">
                  Choose your path
                </h3>
                <p className="mt-1 max-w-3xl text-gray-600">
                  Select one branch below. You can switch anytime; only the allies and success tools for that branch are
                  shown.
                </p>
              </div>
            </div>

            <div
              className="grid grid-cols-1 gap-4 md:grid-cols-3"
              role="radiogroup"
              aria-label="Personal path, macro path, or professional path"
            >
              {PLAN_PATH_BRANCH_OPTIONS.map((opt) => {
                const selected = planBranch === opt.branch
                return (
                  <button
                    key={opt.branch}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setPlanBranch(opt.branch)}
                    className={`rounded-xl border-2 p-5 text-left shadow-sm transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 ${
                      selected
                        ? 'border-teal-700 bg-teal-50/60 ring-1 ring-teal-800/15'
                        : 'border-gray-200 bg-white hover:border-teal-300 hover:bg-gray-50/80'
                    }`}
                  >
                    <h4 className="text-xl font-bold text-gray-900">{opt.title}</h4>
                    <p className="mt-2 text-sm leading-relaxed text-gray-600">{opt.subtitle}</p>
                    <p className="mt-3">
                      <span className={PLAN_BRANCH_TAG_CLASS[opt.branch]}>{opt.tag}</span>
                    </p>
                  </button>
                )
              })}
            </div>

            {planBranch ? (
              <>
                {(() => {
                  const opt = PLAN_PATH_BRANCH_OPTIONS.find((o) => o.branch === planBranch)
                  if (!opt) return null
                  return (
                    <>
                      <div className="mb-6 mt-12 flex flex-wrap items-end justify-between gap-3 border-b border-gray-200 pb-4">
                        <div>
                          <p className="text-xs font-bold uppercase tracking-widest text-teal-800">Plan · Step 2 of 4</p>
                          <h3 className="text-2xl font-bold text-gray-900">{opt.title}</h3>
                          <p className="mt-1 max-w-3xl text-gray-600">{opt.subtitle}</p>
                          <p className="mt-2">
                            <span className={PLAN_BRANCH_TAG_CLASS[opt.branch]}>{opt.tag}</span>
                          </p>
                        </div>
                      </div>
                      <div className={opt.gridClass}>
                        {opt.cards.map((option) => (
                          <ActionCard key={`path-${opt.branch}-${option.title}`} option={option} />
                        ))}
                      </div>
                    </>
                  )
                })()}
              </>
            ) : (
              <p
                className="mt-8 rounded-xl border border-dashed border-gray-300 bg-gray-50 px-4 py-6 text-center text-sm text-gray-600"
                role="status"
              >
                Choose <strong>Personal Path</strong>, <strong>Macro Path</strong>, or{' '}
                <strong>Professional Path</strong> to see your path resources and the Identify Allies and Define Success
                steps.
              </p>
            )}
          </section>

          {planBranch ? (
            <>
              <section
                id={explorePlanSubsectionId('allies')}
                className={EXPLORE_SECTION_SCROLL_MARGIN_CLASS}
                aria-labelledby="plan-allies-heading"
              >
                <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-gray-200 pb-4">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-widest text-teal-800">Plan · Step 3 of 4</p>
                    <h3 id="plan-allies-heading" className="text-2xl font-bold text-gray-900">
                      Identify Allies
                    </h3>
                    <p className="mt-1 max-w-3xl text-gray-600">
                      {PLAN_IDENTIFY_ALLIES_BY_BRANCH[planBranch].subtitle}
                    </p>
                    <p className="mt-2">
                      <span className={PLAN_SUP_TAG_CLASS.allies}>Strategy</span>
                    </p>
                  </div>
                </div>
                <div className={PLAN_IDENTIFY_ALLIES_BY_BRANCH[planBranch].gridClass}>
                  {PLAN_IDENTIFY_ALLIES_BY_BRANCH[planBranch].cards.map((option) => (
                    <ActionCard key={`allies-${planBranch}-${option.title}`} option={option} />
                  ))}
                </div>
              </section>

              <section
                id={explorePlanSubsectionId('success')}
                className={EXPLORE_SECTION_SCROLL_MARGIN_CLASS}
                aria-labelledby="plan-success-heading"
              >
                <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-gray-200 pb-4">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-widest text-teal-800">Plan · Step 4 of 4</p>
                    <h3 id="plan-success-heading" className="text-2xl font-bold text-gray-900">
                      Define Success
                    </h3>
                    <p className="mt-1 max-w-3xl text-gray-600">
                      {PLAN_DEFINE_SUCCESS_BY_BRANCH[planBranch].subtitle}
                    </p>
                    <p className="mt-2">
                      <span className={PLAN_SUP_TAG_CLASS.success}>Outcomes</span>
                    </p>
                  </div>
                </div>
                <div className={PLAN_DEFINE_SUCCESS_BY_BRANCH[planBranch].gridClass}>
                  {PLAN_DEFINE_SUCCESS_BY_BRANCH[planBranch].cards.map((option) => (
                    <ActionCard key={`success-${planBranch}-${option.title}`} option={option} />
                  ))}
                </div>
              </section>
            </>
          ) : null}
        </section>

        <section
          id={EXPLORE_FIND_HELP_ID}
          className={EXPLORE_SECTION_SCROLL_MARGIN_CLASS}
          aria-labelledby="explore-find-help-heading"
        >
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-gray-200 pb-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-teal-800">Find</p>
              <h2 id="explore-find-help-heading" className="text-2xl font-bold text-gray-900">
                {FIND_HELP_SECTION.title}
              </h2>
              <p className="mt-1 max-w-3xl text-gray-600">{FIND_HELP_SECTION.subtitle}</p>
            </div>
          </div>
          <div className={FIND_HELP_SECTION.gridClass}>
            {FIND_HELP_SECTION.cards.map((option) => (
              <ActionCard key={`find-help-${option.title}`} option={option} />
            ))}
          </div>
        </section>

        <section
          id={EXPLORE_TRACK_DECISIONS_ID}
          className={EXPLORE_SECTION_SCROLL_MARGIN_CLASS}
          aria-labelledby="explore-track-heading"
        >
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-gray-200 pb-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-teal-800">Track</p>
              <h2 id="explore-track-heading" className="text-2xl font-bold text-gray-900">
                {TRACK_DECISIONS_SECTION.title}
              </h2>
              <p className="mt-1 max-w-3xl text-gray-600">{TRACK_DECISIONS_SECTION.subtitle}</p>
            </div>
          </div>
          <div className={TRACK_DECISIONS_SECTION.gridClass}>
            {TRACK_DECISIONS_SECTION.cards.map((option) => (
              <ActionCard key={`track-${option.title}`} option={option} />
            ))}
          </div>
        </section>

        <section
          id={EXPLORE_BUILD_ID}
          className={EXPLORE_SECTION_SCROLL_MARGIN_CLASS}
          aria-labelledby="explore-build-heading"
        >
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-gray-200 pb-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-teal-800">Build</p>
              <h2 id="explore-build-heading" className="text-2xl font-bold text-gray-900">
                {BUILD_PHASE.title}
              </h2>
              <p className="mt-1 max-w-3xl text-gray-600">{BUILD_PHASE.subtitle}</p>
            </div>
          </div>
          <div className={BUILD_PHASE.gridClass}>
            {BUILD_PHASE.cards.map((option) => (
              <ActionCard key={`build-${option.title}`} option={option} />
            ))}
          </div>
        </section>

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
