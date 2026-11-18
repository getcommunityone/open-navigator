import { Fragment, useCallback, useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Dialog, Transition } from '@headlessui/react'
import {
  ArrowLeftIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
  ChartBarIcon,
  ArrowRightIcon,
  MapPinIcon,
  BuildingOffice2Icon,
} from '@heroicons/react/24/outline'
import {
  fetchPolicyQuestions,
  fetchPolicyQuestion,
  fetchQuestionMeetings,
  fetchQuestionInstances,
  OUTCOME_FAMILIES,
  type OutcomeFamily,
  type PolicyQuestionSummary,
  type PolicyQuestionDetail,
  type QuestionTrendPoint,
  type QuestionMeeting,
  type QuestionInstance,
} from '../api/policyQuestions'
import DecisionCardList from '../components/DecisionCardList'
import { highlightSnippet } from '../lib/highlight'
import { themeLabel } from '../lib/themeLabel'
import { companyMentionLabel, companyMentionLink } from '../lib/companyMention'
import { questionSummary } from '../lib/questionSummary'

// ────────────────────────────────────────────────────────────────────────────
// Questions That Keep Coming Up — restyled to match Browse Topics / Causes:
// a row of question pills scopes a DecisionCardList (the shared StoryCard grid,
// with its search bar + advanced filters) shown immediately at the top — no
// click-into-a-separate-view. Picking a question also surfaces a compact detail
// panel with its REAL stats (approval, money & talk, arguments, trend).
//
// EVERY figure is REAL (CLAUDE.md: No Fabricated Data) and counted for the
// active place scope (?state=&city=, #499) — the header names that scope:
//   • outcome breakdown, decisions      → /api/policy-question/{id}?state=&city=
//   • $ in linked decisions             → money_sources (listed, so it traces)
//   • discussed in N meetings           → question_transcript_link, same scope
//   • dashboard summary sentence        → scoped rollup / outcome_rollup (#508)
//   • dashboard money & talk            → money_sources (absolute $) + decision/meeting counts
//   • "by quarter" trend                → /api/policy-question/{id}.trend (scoped; 2+ quarters)
//   • dashboard decision rows           → /instances (headline, place_label, companies, nearby)
//   • case for / against, instances     → question detail (arguments + instances)
// ────────────────────────────────────────────────────────────────────────────

// How many question pills to surface inline before the rest move to the flyout.
// The API returns featured questions ordered by display_order, so the first few
// are the most prominent.
const TOP_PILL_COUNT = 5

const SPEND_COLOR = '#0d9488' // teal — money
const TALK_COLOR = '#d97706' // amber — talk / how often

const fmtMoney = (v: number) =>
  v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B`
  : v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M`
  : v >= 1e3 ? `$${Math.round(v / 1e3)}K`
  : `$${Math.round(v)}`

// "2024-04-01" → "Q2'24"
const quarterLabel = (iso: string) => {
  const d = new Date(iso)
  const q = Math.floor(d.getUTCMonth() / 3) + 1
  return `Q${q}'${String(d.getUTCFullYear()).slice(2)}`
}

// Show the full question text in the chip; the title attribute mirrors it.
const pillLabel = (q: PolicyQuestionSummary) => {
  return (q.canonical_text || 'Untitled question').trim()
}

const OUTCOME_LABEL: Record<OutcomeFamily, string> = {
  approved: 'Approved',
  denied: 'Denied',
  moratorium: 'Moratorium',
  deferred: 'Deferred',
  other: 'Other',
}

const OUTCOME_COLOR: Record<OutcomeFamily, string> = {
  approved: 'text-teal-700',
  denied: 'text-rose-700',
  moratorium: 'text-amber-700',
  deferred: 'text-slate-600',
  other: 'text-gray-500',
}

const outcomeCount = (d: PolicyQuestionDetail, f: OutcomeFamily) =>
  ({
    approved: d.rollup.approved_count,
    denied: d.rollup.denied_count,
    moratorium: d.rollup.moratorium_count,
    deferred: d.rollup.deferred_count,
    other: d.rollup.other_count,
  })[f] ?? 0

const parseOutcome = (raw: string | null): OutcomeFamily | undefined => {
  const v = (raw ?? '').trim().toLowerCase()
  return (OUTCOME_FAMILIES as string[]).includes(v) ? (v as OutcomeFamily) : undefined
}

// "m:ss" (or "h:mm:ss") for a jump link.
const clock = (secs: number) => {
  const t = Math.max(0, Math.floor(secs))
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const ss = String(t % 60).padStart(2, '0')
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

const MEETINGS_ANCHOR = 'discussed-in-meetings'

export default function PolicyQuestionsPage() {
  const navigate = useNavigate()
  const routerLocation = useLocation()
  // Place filter carried over from the homepage (e.g. ?state=GA&city=Atlanta) —
  // passed straight through to the scoped DecisionCardList, like Browse Topics.
  const [searchParams, setSearchParams] = useSearchParams()
  const stateCode = (searchParams.get('state') || '').trim().toUpperCase() || undefined
  const cityName = (searchParams.get('city') || '').trim() || undefined
  const questionIdParam = (searchParams.get('question_id') || '').trim() || undefined
  // ?outcome=<family> (#499): a header outcome count drills the decision list to it.
  const outcomeParam = parseOutcome(searchParams.get('outcome'))
  const [placeScope, setPlaceScope] = useState<'city' | 'state'>('city')
  const scopedCity = cityName && placeScope === 'city' ? cityName : undefined
  const placeLabel = scopedCity || stateCode
  const isScoped = Boolean(stateCode || scopedCity)
  // The scope label the header, the list title and the meetings all share.
  const scopeLabel = scopedCity ? [scopedCity, stateCode].filter(Boolean).join(', ') : stateCode ?? 'Nationwide'

  // Picking a question SCOPES the decision cards shown below — ?question_id=
  // in the URL is the source of truth so deep links, refresh, and homepage picks
  // stay in sync with the pills + decision cards.
  // The full question catalog + keyword search lives in a slide-over flyout so
  // the main view stays focused on the top handful of questions.
  const [flyoutOpen, setFlyoutOpen] = useState(false)
  const [query, setQuery] = useState('')

  // Go back to wherever the user came from; fall back to the home page when
  // this is the first in-app view (direct link / refresh).
  const handleBack = () => {
    if (routerLocation.key !== 'default') {
      navigate(-1)
    } else {
      navigate('/')
    }
  }

  // For now we focus the whole site on the curated/pinned "big questions" only,
  // so this registry lists the featured set. Swap to { limit: 200 } for the full
  // clustered registry.
  const { data, isLoading, isError, error } = useQuery<PolicyQuestionSummary[]>({
    queryKey: ['policy-questions-registry', 'featured'],
    queryFn: () => fetchPolicyQuestions({ featured: true }),
  })

  const questions = useMemo(() => data ?? [], [data])

  const selectedQuestion = useMemo(
    () =>
      questionIdParam
        ? questions.find((q) => q.question_id === questionIdParam) ?? null
        : null,
    [questions, questionIdParam],
  )

  const pickQuestion = useCallback(
    (q: PolicyQuestionSummary | null) => {
      const next = new URLSearchParams(searchParams)
      if (q?.question_id) next.set('question_id', q.question_id)
      else next.delete('question_id')
      // An outcome belongs to one question; picking another clears it.
      next.delete('outcome')
      setSearchParams(next, { replace: true })
      setFlyoutOpen(false)
    },
    [searchParams, setSearchParams],
  )

  // Drill the decision list to one outcome family (or back to all), in the URL
  // alongside state/city so it survives refresh / back / deep links.
  const setOutcome = useCallback(
    (f: OutcomeFamily | null) => {
      const next = new URLSearchParams(searchParams)
      if (f) next.set('outcome', f)
      else next.delete('outcome')
      setSearchParams(next)
    },
    [searchParams, setSearchParams],
  )

  // Broaden to nationwide: drop state/city, keep the question and outcome.
  const broadenToNation = useCallback(() => {
    const next = new URLSearchParams(searchParams)
    next.delete('state')
    next.delete('city')
    setPlaceScope('city')
    setSearchParams(next)
  }, [searchParams, setSearchParams])

  const activeQuestionId = selectedQuestion?.question_id ?? questionIdParam

  // Every header figure, counted for the active scope (#499).
  const { data: scopedDetail, isLoading: detailLoading } = useQuery<PolicyQuestionDetail>({
    queryKey: ['policy-question-detail', activeQuestionId, stateCode ?? null, scopedCity ?? null],
    queryFn: () => fetchPolicyQuestion(activeQuestionId as string, { state: stateCode, city: scopedCity }),
    enabled: Boolean(activeQuestionId),
    staleTime: 5 * 60 * 1000,
  })
  // Nationwide figures, only for the "See all N nationwide" broaden links.
  const { data: nationalDetail } = useQuery<PolicyQuestionDetail>({
    queryKey: ['policy-question-detail', activeQuestionId, null, null],
    queryFn: () => fetchPolicyQuestion(activeQuestionId as string),
    enabled: Boolean(activeQuestionId) && isScoped,
    staleTime: 5 * 60 * 1000,
  })
  const nationalDecisions = nationalDetail
    ? outcomeParam
      ? outcomeCount(nationalDetail, outcomeParam)
      : nationalDetail.rollup.decisions_total
    : 0

  // Full catalog filtered by the flyout keyword search (text or theme).
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return questions
    return questions.filter((item) => {
      if ((item.canonical_text ?? '').toLowerCase().includes(q)) return true
      return (item.primary_theme ?? '').toLowerCase().includes(q)
    })
  }, [questions, query])

  // Inline pills: the top N featured questions, plus the active one if the user
  // picked something further down the list via the flyout.
  const topPills = useMemo(() => {
    const top = questions.slice(0, TOP_PILL_COUNT)
    if (selectedQuestion && !top.some((q) => q.question_id === selectedQuestion.question_id)) {
      return [...top, selectedQuestion]
    }
    return top
  }, [questions, selectedQuestion])

  // Pill styling for the question filter row — solid indigo when active.
  const chipClass = (on: boolean) =>
    `inline-flex max-w-full shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
      on
        ? 'border-indigo-600 bg-indigo-600 text-white'
        : 'border-gray-200 bg-white text-gray-700 hover:border-indigo-300 hover:text-indigo-700'
    }`

  const pickQuestionToggle = useCallback(
    (q: PolicyQuestionSummary) => {
      pickQuestion(selectedQuestion?.question_id === q.question_id ? null : q)
    },
    [pickQuestion, selectedQuestion],
  )

  const listTitle = selectedQuestion
    ? `${outcomeParam ? `${OUTCOME_LABEL[outcomeParam]} decisions` : 'Decisions'} on this question · ${scopeLabel}`
    : `Most contested decisions${placeLabel ? ` in ${placeLabel}` : ''}`

  // Empty scoped list → one click to the same question (and outcome) nationwide.
  const broadenLink = (noun: string, n: number): ReactNode =>
    isScoped && n > 0 ? (
      <span className="flex flex-col items-center gap-2">
        <span>No {noun} in {scopeLabel} yet.</span>
        <button
          type="button"
          onClick={broadenToNation}
          className="rounded-full bg-indigo-600 px-4 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
        >
          See all {n.toLocaleString()} {noun} nationwide
        </button>
      </span>
    ) : undefined

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        <button
          type="button"
          onClick={handleBack}
          className="inline-flex items-center gap-2 mb-4 text-sm font-medium text-gray-600 hover:text-indigo-600 transition-colors"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          Back
        </button>

        {/* Header card — title + description; the full question search lives in
            the flyout, matching Browse Topics. */}
        <div className="bg-white rounded-lg shadow-sm p-4 mb-4">
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
            <h1 className="text-2xl font-bold text-gray-900">
              Browse Questions{placeLabel ? ` · ${placeLabel}` : ''}
            </h1>
            {cityName && stateCode && (
              <div className="inline-flex rounded-full border border-gray-200 bg-gray-50 p-0.5 text-sm">
                <button
                  type="button"
                  onClick={() => setPlaceScope('city')}
                  className={`rounded-full px-3 py-1 font-medium transition-colors ${
                    placeScope === 'city' ? 'bg-indigo-600 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  📍 {cityName}
                </button>
                <button
                  type="button"
                  onClick={() => setPlaceScope('state')}
                  className={`rounded-full px-3 py-1 font-medium transition-colors ${
                    placeScope === 'state' ? 'bg-indigo-600 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  All of {stateCode}
                </button>
              </div>
            )}
          </div>

          {/* Top questions inline — pick one to scope the decision cards below. */}
          {isError ? (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              Couldn&apos;t load questions.{' '}
              {(error as { message?: string } | undefined)?.message ?? 'Please try again.'}
            </div>
          ) : (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button type="button" onClick={() => pickQuestion(null)} className={chipClass(selectedQuestion === null)}>
                All questions
              </button>
              {isLoading ? (
                <span className="px-2 py-1.5 text-sm text-gray-400">Loading questions…</span>
              ) : (
                topPills.map((q) => {
                  const on = selectedQuestion?.question_id === q.question_id
                  return (
                    <button
                      key={q.question_id}
                      type="button"
                      onClick={() => pickQuestionToggle(q)}
                      title={q.canonical_text ?? undefined}
                      className={chipClass(on)}
                    >
                      {pillLabel(q)}
                    </button>
                  )
                })
              )}
            </div>
          )}
        </div>

        {/* Selected-question detail panel — REAL stats only. Hidden on "All". */}
        {selectedQuestion && (
          <QuestionDetailPanel
            question={selectedQuestion}
            detail={scopedDetail}
            loading={detailLoading}
            scopeLabel={scopeLabel}
            outcome={outcomeParam}
            onOutcome={setOutcome}
            stateCode={stateCode}
            city={scopedCity}
          />
        )}

        {/* Decision cards — the shared Contested StoryCard grid with YouTube
            previews, search bar, and advanced filters (matching Browse Topics).
            Picking a question scopes this list; the `key` remounts it so the new
            scope applies cleanly. */}
        <DecisionCardList
          key={`${activeQuestionId ?? 'all-questions'}-${stateCode ?? 'national'}-${scopedCity ?? 'state'}-${outcomeParam ?? 'all'}`}
          questionId={activeQuestionId ?? undefined}
          outcome={activeQuestionId ? outcomeParam : undefined}
          state={stateCode}
          city={scopedCity}
          title={listTitle}
          emptyState={
            activeQuestionId
              ? broadenLink(outcomeParam ? `${OUTCOME_LABEL[outcomeParam].toLowerCase()} decisions` : 'decisions', nationalDecisions)
              : undefined
          }
          showAdvancedFilters
          scopeFilter={
            <label className="flex flex-col gap-1 text-xs font-semibold text-gray-600">
              Question
              <select
                value={selectedQuestion?.question_id ?? ''}
                onChange={(e) => {
                  const id = e.target.value
                  pickQuestion(id ? questions.find((q) => String(q.question_id) === id) ?? null : null)
                }}
                disabled={isLoading || questions.length === 0}
                className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-normal text-gray-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50 disabled:text-gray-400"
              >
                <option value="">All questions</option>
                {questions.map((q) => (
                  <option key={q.question_id} value={q.question_id}>
                    {q.canonical_text || 'Untitled question'}
                  </option>
                ))}
              </select>
            </label>
          }
        />

        {/* Transcript fallback — real meetings whose transcript discusses this
            question's alias keywords. Many questions (e.g. water fluoridation)
            have zero structured decisions but are debated in real meetings; this
            surfaces them honestly (keyword match, NOT an AI-extracted decision). */}
        {selectedQuestion && (
          <QuestionMeetingList
            key={`meetings-${selectedQuestion.question_id}-${stateCode ?? 'national'}-${scopedCity ?? 'state'}`}
            question={selectedQuestion}
            total={scopedDetail?.discussion_meeting_count ?? 0}
            totalLoading={detailLoading}
            state={stateCode}
            city={scopedCity}
            scopeLabel={scopeLabel}
            emptyState={broadenLink('meetings', nationalDetail?.discussion_meeting_count ?? 0)}
          />
        )}
      </div>

      {/* Filter flyout — full question catalog + keyword search, slid in from the
          right. Drilldowns (selecting any question) happen here too. */}
      <Transition appear show={flyoutOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => setFlyoutOpen(false)}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/30" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-hidden">
            <div className="absolute inset-y-0 right-0 flex max-w-full pl-10">
              <Transition.Child
                as={Fragment}
                enter="transform transition ease-out duration-200"
                enterFrom="translate-x-full"
                enterTo="translate-x-0"
                leave="transform transition ease-in duration-150"
                leaveFrom="translate-x-0"
                leaveTo="translate-x-full"
              >
                <Dialog.Panel className="flex h-full w-screen max-w-md flex-col bg-white shadow-xl">
                  <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
                    <Dialog.Title className="text-lg font-semibold text-gray-900">All questions</Dialog.Title>
                    <button
                      type="button"
                      onClick={() => setFlyoutOpen(false)}
                      className="rounded-full p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
                    >
                      <XMarkIcon className="h-6 w-6" />
                    </button>
                  </div>

                  <div className="border-b border-gray-200 px-6 py-4">
                    <div className="relative">
                      <MagnifyingGlassIcon className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
                      <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Filter questions or themes (e.g. housing, zoning)…"
                        className="w-full rounded-lg border-2 border-gray-300 px-10 py-2 text-sm text-gray-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>
                  </div>

                  <div className="flex-1 overflow-y-auto px-6 py-4">
                    <div className="flex flex-col gap-2">
                      <button
                        type="button"
                        onClick={() => pickQuestion(null)}
                        className={`rounded-lg border px-3 py-2 text-left text-sm font-medium transition-colors ${
                          selectedQuestion === null
                            ? 'border-indigo-600 bg-indigo-50 text-indigo-800'
                            : 'border-gray-200 bg-white text-gray-700 hover:border-indigo-300'
                        }`}
                      >
                        All questions
                      </button>
                      {filtered.map((q) => {
                        const on = selectedQuestion?.question_id === q.question_id
                        return (
                          <button
                            key={q.question_id}
                            type="button"
                            onClick={() => pickQuestion(q)}
                            className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                              on
                                ? 'border-indigo-600 bg-indigo-50'
                                : 'border-gray-200 bg-white hover:border-indigo-300'
                            }`}
                          >
                            <span className="block font-medium text-gray-800">{q.canonical_text || 'Untitled question'}</span>
                            <span className="mt-0.5 block text-xs text-gray-500">
                              {q.instances_total} {q.instances_total === 1 ? 'decision' : 'decisions'} nationwide
                              {themeLabel(q.primary_theme) && <> · {themeLabel(q.primary_theme)}</>}
                            </span>
                          </button>
                        )
                      })}
                      {filtered.length === 0 && (
                        <span className="px-1 py-1.5 text-sm text-gray-400">
                          No questions match &ldquo;{query.trim()}&rdquo;.
                        </span>
                      )}
                    </div>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </div>
  )
}

// ── Selected-question summary card ──
// Every figure is counted for the active place scope and labelled with it
// (CLAUDE.md "Scope label must match the active filter", #499). Each figure is a
// drill-down: an outcome filters the decision list (?outcome=), the decision
// count clears it, the meetings count jumps to the meetings section, the theme
// links to Browse Topics, and the money figure lists the decisions it adds up.
function QuestionDetailPanel({
  question,
  detail,
  loading,
  scopeLabel,
  outcome,
  onOutcome,
  stateCode,
  city,
}: {
  question: PolicyQuestionSummary
  detail: PolicyQuestionDetail | undefined
  loading: boolean
  scopeLabel: string
  outcome: OutcomeFamily | undefined
  onOutcome: (f: OutcomeFamily | null) => void
  stateCode?: string
  city?: string
}) {
  const [dashboardOpen, setDashboardOpen] = useState(false)
  const [moneyOpen, setMoneyOpen] = useState(false)
  const theme = themeLabel(detail?.primary_theme ?? question.primary_theme)

  // Theme → its Browse Topics topic (e.g. "Data centers") when one is named like an
  // alias of the question; otherwise Browse Topics in the same place scope.
  const topicHref = (() => {
    const q = new URLSearchParams()
    if (detail?.topic_id != null) q.set('topic_id', String(detail.topic_id))
    if (stateCode) q.set('state', stateCode)
    if (city) q.set('city', city)
    const qs = q.toString()
    return `/browse-topics${qs ? `?${qs}` : ''}`
  })()

  const decisions = detail?.rollup.decisions_total ?? 0
  const meetings = detail?.discussion_meeting_count ?? 0
  const money = detail?.money_total ?? 0
  const moneySources = detail?.money_sources ?? []
  const sep = <span className="text-gray-300">·</span>
  const chip = (on: boolean) =>
    `rounded-full px-2 py-0.5 transition-colors hover:bg-indigo-50 hover:text-indigo-700 ${
      on ? 'bg-indigo-100 text-indigo-800 ring-1 ring-indigo-300' : ''
    }`

  return (
    <>
      <div className="mb-6 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold leading-snug text-gray-900">
                {question.canonical_text || 'Untitled question'}
              </h2>
              <span
                data-testid="question-scope-label"
                className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700"
              >
                {outcome ? `${OUTCOME_LABEL[outcome]} · ` : ''}
                {scopeLabel === 'Nationwide' ? 'Nationwide' : `in ${scopeLabel}`}
              </span>
            </div>
            {loading || !detail ? (
              <div className="mt-2 h-5 w-64 animate-pulse rounded bg-gray-100" />
            ) : (
              <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-gray-500">
                <button
                  type="button"
                  onClick={() => onOutcome(null)}
                  className={`${chip(!outcome)} font-semibold text-gray-800`}
                  title="Show every decision in this scope"
                >
                  {decisions.toLocaleString()} {decisions === 1 ? 'decision' : 'decisions'}
                </button>
                {OUTCOME_FAMILIES.filter((f) => outcomeCount(detail, f) > 0).map((f) => (
                  <Fragment key={f}>
                    {sep}
                    <button
                      type="button"
                      onClick={() => onOutcome(outcome === f ? null : f)}
                      className={`${chip(outcome === f)} ${OUTCOME_COLOR[f]}`}
                      title={`Show only ${OUTCOME_LABEL[f].toLowerCase()} decisions`}
                    >
                      {outcomeCount(detail, f).toLocaleString()} {OUTCOME_LABEL[f].toLowerCase()}
                    </button>
                  </Fragment>
                ))}
                {theme && (
                  <>
                    {sep}
                    <Link
                      to={topicHref}
                      className={chip(false)}
                      title={detail.topic_name ? `Browse the ${detail.topic_name} topic` : 'Browse topics'}
                    >
                      {theme}
                      {detail.topic_name && <span className="text-gray-400"> › {detail.topic_name}</span>}
                    </Link>
                  </>
                )}
                {money !== 0 && moneySources.length > 0 && (
                  <>
                    {sep}
                    <button
                      type="button"
                      onClick={() => setMoneyOpen((v) => !v)}
                      className={chip(moneyOpen)}
                      aria-expanded={moneyOpen}
                    >
                      {fmtMoney(money)} in {moneySources.length} linked{' '}
                      {moneySources.length === 1 ? 'decision' : 'decisions'}
                    </button>
                  </>
                )}
                {meetings > 0 && (
                  <>
                    {sep}
                    <a
                      href={`#${MEETINGS_ANCHOR}`}
                      onClick={(e) => {
                        e.preventDefault()
                        document.getElementById(MEETINGS_ANCHOR)?.scrollIntoView({ behavior: 'smooth' })
                      }}
                      className={chip(false)}
                    >
                      discussed in {meetings.toLocaleString()} {meetings === 1 ? 'meeting' : 'meetings'}
                    </a>
                  </>
                )}
              </div>
            )}

            {/* Where the dollar figure comes from: the linked decisions' own amounts. */}
            {moneyOpen && moneySources.length > 0 && (
              <ul className="mt-3 space-y-1 rounded-md border border-gray-100 bg-gray-50 px-3 py-2 text-sm">
                {moneySources.map((m) => (
                  <li key={m.event_decision_id} className="flex flex-wrap items-baseline justify-between gap-2">
                    <Link to={`/decisions/${m.event_decision_id}`} className="text-indigo-700 hover:underline">
                      {m.title || 'Untitled decision'}
                    </Link>
                    <span className="text-xs text-gray-500">
                      {[m.jurisdiction_name, m.state_code].filter(Boolean).join(', ')}
                      {m.outcome_family && <> · {m.outcome_family}</>} ·{' '}
                      <span className="font-semibold text-gray-700">{fmtMoney(m.net_dollar_impact)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Attractive drill-down — opens the full money & talk dashboard. */}
          <button
            type="button"
            onClick={() => setDashboardOpen(true)}
            className="group inline-flex shrink-0 items-center gap-2.5 rounded-xl bg-gradient-to-r from-teal-600 to-indigo-600 px-4 py-3 text-left text-white shadow-sm transition-all hover:from-teal-500 hover:to-indigo-500 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2"
          >
            <ChartBarIcon className="h-6 w-6 shrink-0" />
            <span className="flex flex-col leading-tight">
              <span className="text-sm font-semibold">View dashboard</span>
              <span className="text-[11px] text-white/80">Summary · where &amp; who · trend</span>
            </span>
            <ArrowRightIcon className="h-4 w-4 shrink-0 transition-transform group-hover:translate-x-0.5" />
          </button>
        </div>
      </div>

      <QuestionDashboardModal
        question={question}
        open={dashboardOpen}
        onClose={() => setDashboardOpen(false)}
        scopeLabel={scopeLabel}
        stateCode={stateCode}
        city={city}
        outcome={outcome}
      />
    </>
  )
}

// ── Full question dashboard, rendered in a drill-down modal ──
// Follows the page's scope (?state=&city=&outcome=) and says so. Opens with a plain
// sentence built from the scoped counts, then absolute money & talk figures, the
// quarterly history (only with 2+ quarters), the arguments, and one readable row per
// decision: what was decided (headline), when, the outcome, and — only when the
// warehouse can back it — where (a street-level address that agrees with the
// decision's government) and who (a company the decision's own text names, quoted).
// All REAL data (#508); a missing place or company is simply not shown.
function QuestionDashboardModal({
  question,
  open,
  onClose,
  scopeLabel,
  stateCode,
  city,
  outcome,
}: {
  question: PolicyQuestionSummary
  open: boolean
  onClose: () => void
  scopeLabel: string
  stateCode?: string
  city?: string
  outcome?: OutcomeFamily
}) {
  const { data: detail, isLoading } = useQuery<PolicyQuestionDetail>({
    queryKey: ['policy-question-detail', question.question_id, stateCode ?? null, city ?? null, outcome ?? null],
    queryFn: () => fetchPolicyQuestion(question.question_id, { state: stateCode, city, outcome }),
    staleTime: 5 * 60 * 1000,
    enabled: open,
  })
  const { data: instances, isLoading: instancesLoading } = useQuery<QuestionInstance[]>({
    queryKey: ['policy-question-instances', question.question_id, stateCode ?? null, city ?? null, outcome ?? null],
    queryFn: () =>
      fetchQuestionInstances(question.question_id, { state: stateCode, city, outcome, order: 'recent', limit: 100 }),
    staleTime: 5 * 60 * 1000,
    enabled: open,
  })

  const rollup = outcome ? detail?.outcome_rollup : detail?.rollup
  const summary = detail
    ? questionSummary(rollup, { outcome, meetings: detail.discussion_meeting_count ?? 0 })
    : null
  const decisionsInScope = rollup?.decisions_total ?? 0
  const meetings = detail?.discussion_meeting_count ?? 0
  const moneySources = (detail?.money_sources ?? []).filter((m) => !outcome || m.outcome_family === outcome)
  const money = moneySources.reduce((s, m) => s + m.net_dollar_impact, 0)
  const trend = detail?.trend ?? []
  const rows = instances ?? []
  const scopeChip = `${outcome ? `${OUTCOME_LABEL[outcome]} · ` : ''}${scopeLabel === 'Nationwide' ? 'Nationwide' : `in ${scopeLabel}`}`

  const pros = detail?.arguments.filter((a) => a.stance === 'pro') ?? []
  const cons = detail?.arguments.filter((a) => a.stance === 'con') ?? []

  return (
    <Transition appear show={open} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/40" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-200"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-150"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-2xl transform overflow-hidden rounded-xl bg-white shadow-xl transition-all">
                <div className="flex items-start justify-between gap-4 border-b border-gray-200 px-6 py-4">
                  <div className="min-w-0">
                    <Dialog.Title className="text-base font-semibold leading-snug text-gray-900">
                      {question.canonical_text || 'Untitled question'}
                    </Dialog.Title>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gray-500">
                      <span
                        data-testid="dashboard-scope-label"
                        className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700"
                      >
                        {scopeChip}
                      </span>
                      {themeLabel(question.primary_theme) && <span>{themeLabel(question.primary_theme)}</span>}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={onClose}
                    aria-label="Close dashboard"
                    className="rounded-full p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
                  >
                    <XMarkIcon className="h-6 w-6" />
                  </button>
                </div>

                <div className="max-h-[70vh] overflow-y-auto px-6 py-5">
                  {isLoading || !detail ? (
                    <div className="my-4 h-5 w-5 animate-spin rounded-full border-b-2 border-indigo-600" />
                  ) : (
                    <>
                      {/* Plain summary — every number is a scoped count from the API. */}
                      <p data-testid="dashboard-summary" className="text-[15px] leading-relaxed text-gray-800">
                        {summary}
                      </p>

                      {/* Money & talk — absolute, labelled figures for this scope. */}
                      <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2.5">
                          <div className="text-[10px] uppercase tracking-widest" style={{ color: SPEND_COLOR }}>Money</div>
                          {money !== 0 && moneySources.length > 0 ? (
                            <>
                              <div className="text-lg font-semibold text-gray-900">
                                {fmtMoney(money)}{' '}
                                <span className="text-sm font-normal text-gray-500">
                                  in {moneySources.length} {moneySources.length === 1 ? 'decision' : 'decisions'}
                                </span>
                              </div>
                              <ul className="mt-1 space-y-0.5 text-xs text-gray-500">
                                {moneySources.slice(0, 3).map((m) => (
                                  <li key={m.event_decision_id} className="truncate">
                                    <Link to={`/decisions/${m.event_decision_id}`} className="text-indigo-700 hover:underline">
                                      {m.title || 'Untitled decision'}
                                    </Link>{' '}
                                    · {[m.jurisdiction_name, m.state_code].filter(Boolean).join(', ')} · {fmtMoney(m.net_dollar_impact)}
                                  </li>
                                ))}
                              </ul>
                            </>
                          ) : (
                            <div className="text-sm text-gray-500">No dollar amount in these decisions.</div>
                          )}
                        </div>
                        <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2.5">
                          <div className="text-[10px] uppercase tracking-widest" style={{ color: TALK_COLOR }}>Talk</div>
                          <div className="text-lg font-semibold text-gray-900">
                            {decisionsInScope.toLocaleString()}{' '}
                            <span className="text-sm font-normal text-gray-500">
                              {decisionsInScope === 1 ? 'decision' : 'decisions'}
                              {outcome ? ` (${OUTCOME_LABEL[outcome].toLowerCase()})` : ''}
                            </span>
                          </div>
                          <div className="text-xs text-gray-500">
                            {meetings > 0
                              ? <>discussed in {meetings.toLocaleString()} {meetings === 1 ? 'meeting' : 'meetings'} (transcript keyword match)</>
                              : 'No meeting transcripts mention it in this scope.'}
                          </div>
                        </div>
                      </div>

                      {/* By quarter — only when there is a history to show. */}
                      <div className="mt-4 rounded-md border border-gray-100 bg-gray-50 px-3 py-2.5">
                        <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                          <span className="text-[10px] uppercase tracking-widest text-gray-500">By quarter</span>
                          {trend.length >= 2 && (
                            <span className="flex items-center gap-3 text-[11px] text-gray-500">
                              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: SPEND_COLOR }} />money</span>
                              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: TALK_COLOR }} />how often</span>
                            </span>
                          )}
                        </div>
                        {trend.length >= 2 ? (
                          <Trend points={trend} />
                        ) : (
                          <p data-testid="dashboard-trend-empty" className="text-sm text-gray-500">
                            Not enough history yet
                            {trend.length === 1 && (
                              <>
                                {': '}every decision here is from {quarterLabel(trend[0].quarter_start)}
                              </>
                            )}
                            .
                          </p>
                        )}
                      </div>

                      {/* Arguments for / against */}
                      {(pros.length > 0 || cons.length > 0) && (
                        <div className="mt-4 grid gap-4 sm:grid-cols-2">
                          <div>
                            <div className="mb-1.5 text-[10px] uppercase tracking-widest text-teal-700">The case for</div>
                            {pros.length ? (
                              pros.map((a) => (
                                <p key={a.argument_id} className="mb-1.5 text-sm leading-snug text-gray-600">— {a.label || a.summary}</p>
                              ))
                            ) : (
                              <p className="text-sm text-gray-400">No arguments captured yet.</p>
                            )}
                          </div>
                          <div>
                            <div className="mb-1.5 text-[10px] uppercase tracking-widest text-rose-700">The case against</div>
                            {cons.length ? (
                              cons.map((a) => (
                                <p key={a.argument_id} className="mb-1.5 text-sm leading-snug text-gray-600">— {a.label || a.summary}</p>
                              ))
                            ) : (
                              <p className="text-sm text-gray-400">No arguments captured yet.</p>
                            )}
                          </div>
                        </div>
                      )}

                      {/* The decisions — what, when, outcome, and where/who when the data backs it. */}
                      <div className="mt-5">
                        <div className="mb-1.5 flex items-baseline justify-between gap-2">
                          <span className="text-[10px] uppercase tracking-widest text-gray-500">
                            {outcome ? `${OUTCOME_LABEL[outcome]} decisions` : 'Decisions'}, newest first
                          </span>
                          {rows.length > 0 && (
                            <span className="text-[11px] text-gray-400">
                              {rows.length.toLocaleString()} of {(rollup?.instances_total ?? rows.length).toLocaleString()}
                            </span>
                          )}
                        </div>
                        {instancesLoading ? (
                          <div className="my-3 h-5 w-5 animate-spin rounded-full border-b-2 border-indigo-600" />
                        ) : rows.length === 0 ? (
                          <p className="text-sm text-gray-400">No decisions in this scope.</p>
                        ) : (
                          <ul className="divide-y divide-gray-100">
                            {rows.map((ex) => (
                              <InstanceRow key={ex.instance_id} ex={ex} />
                            ))}
                          </ul>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  )
}

// One decision in the dashboard: headline (linked), place + date + outcome, and the
// where / who lines only when dbt could back them (decision_place_label,
// decision_company_mention, decision_nearby_data_center_site).
function InstanceRow({ ex }: { ex: QuestionInstance }) {
  const fam = ex.outcome_family as OutcomeFamily | null | undefined
  const gov = [ex.city || ex.jurisdiction_name, ex.state_code].filter(Boolean).join(', ') || 'Unknown jurisdiction'
  const title = ex.headline || `${ex.source_type === 'state_bill' ? 'State bill' : 'Decision'} in ${gov}`
  const mentions = ex.company_mentions ?? []
  const nearby = ex.nearby_sites ?? []
  return (
    <li data-testid="dashboard-instance" className="py-2.5 text-sm">
      <div className="flex items-start justify-between gap-3">
        {ex.event_decision_id ? (
          <Link to={`/decisions/${ex.event_decision_id}`} className="font-medium leading-snug text-indigo-700 hover:underline">
            {title}
          </Link>
        ) : (
          <span className="font-medium leading-snug text-gray-800">{title}</span>
        )}
        {fam && (
          <span className={`shrink-0 text-xs font-semibold ${OUTCOME_COLOR[fam] ?? 'text-gray-500'}`}>
            {OUTCOME_LABEL[fam] ?? fam}
          </span>
        )}
      </div>
      <div className="mt-0.5 text-xs text-gray-500">
        {gov}
        {ex.occurred_at && (
          <> · {new Date(ex.occurred_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</>
        )}
      </div>
      {ex.place_label && (
        <div className="mt-1 flex items-start gap-1 text-xs text-gray-700" data-testid="dashboard-instance-place">
          <MapPinIcon className="mt-px h-3.5 w-3.5 shrink-0 text-gray-400" aria-hidden />
          <span>
            <span className="text-gray-400">Where: </span>
            {ex.place_label}
          </span>
        </div>
      )}
      {mentions.map((m) => (
        <div key={m.operator_name} className="mt-1 flex items-start gap-1 text-xs text-gray-700" data-testid="dashboard-instance-company">
          <BuildingOffice2Icon className="mt-px h-3.5 w-3.5 shrink-0 text-gray-400" aria-hidden />
          <span>
            <span className="text-gray-400">{companyMentionLabel(m)}: </span>
            <span className="font-medium">{m.operator_name}</span>
            {m.evidence && <span className="text-gray-500"> — “{highlightSnippet(m.evidence)}”</span>}
            {companyMentionLink(m) && (
              <>
                {' '}
                <a
                  href={companyMentionLink(m) as string}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-indigo-600 hover:underline"
                  data-testid="dashboard-instance-company-recording"
                >
                  Watch the meeting
                </a>
              </>
            )}
          </span>
        </div>
      ))}
      {nearby.map((s) => (
        <div key={s.data_center_site_id} className="mt-1 text-xs text-gray-500">
          Nearby tracked site: {s.site_name}
          {s.owner && <> ({s.owner})</>}
          <span className="text-gray-400"> — near this government, not necessarily what was decided</span>
        </div>
      ))}
    </li>
  )
}

// ── "Discussed in N meetings" — transcript-keyword fallback ──
// Real meetings whose transcript matched this question's alias keyword(s)
// (dbt question_transcript_link via /api/policy-question/{id}/meetings), scoped
// server-side to the page's state/city and newest first. A HIGH-RECALL keyword
// signal, NOT an AI-extracted decision — labelled as such. Every tile quotes the
// matched passage (ts_headline <mark> → highlightSnippet, never innerHTML) with a
// jump to the moment it is said; a meeting with no passage is not shown (#499).
const MEETING_PAGE = 24

function QuestionMeetingList({
  question,
  total,
  totalLoading,
  state,
  city,
  scopeLabel,
  emptyState,
}: {
  question: PolicyQuestionSummary
  total: number
  totalLoading: boolean
  state?: string
  city?: string
  scopeLabel: string
  emptyState?: ReactNode
}) {
  const { data, isLoading, isFetchingNextPage, hasNextPage, fetchNextPage } = useInfiniteQuery<QuestionMeeting[]>({
    queryKey: ['policy-question-meetings', question.question_id, state ?? null, city ?? null],
    queryFn: ({ pageParam }) =>
      fetchQuestionMeetings(question.question_id, {
        state,
        city,
        limit: MEETING_PAGE,
        offset: Number(pageParam) || 0,
      }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) =>
      last.length === MEETING_PAGE ? pages.length * MEETING_PAGE : undefined,
    staleTime: 5 * 60 * 1000,
    enabled: total > 0,
  })

  // No passage, no tile: the evidence is what shows why the meeting matched.
  const meetings = useMemo(
    () => (data?.pages ?? []).flat().filter((m) => (m.evidence ?? '').includes('<mark>')),
    [data],
  )

  if (!totalLoading && total === 0 && !emptyState) return null

  return (
    <div id={MEETINGS_ANCHOR} className="mt-6 scroll-mt-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h3 className="text-lg font-semibold text-gray-900">
          Discussed in meetings · {scopeLabel}
          <span className="ml-2 text-sm font-normal text-gray-500">
            {total.toLocaleString()} meeting{total === 1 ? '' : 's'} mention it · newest first
          </span>
        </h3>
      </div>
      <p className="mb-3 text-xs text-gray-400">
        Real meetings whose transcript mentions this topic (keyword match), quoted where it comes up — not
        yet captured as a formal decision.
      </p>

      {totalLoading || (total > 0 && isLoading) ? (
        <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-400">
          Loading meetings…
        </div>
      ) : meetings.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-200 bg-white p-6 text-center text-sm text-gray-500">
          {emptyState ?? `No meetings in ${scopeLabel} yet.`}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {meetings.map((m) => {
              const place = [m.city || m.jurisdiction_name, m.state_code].filter(Boolean).join(', ')
              const date = m.event_date
                ? new Date(`${m.event_date}T00:00:00`).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  })
                : null
              const watchHref = m.jump_url || m.video_url
              return (
                <div
                  key={m.video_id}
                  data-testid="question-meeting-tile"
                  className="flex flex-col rounded-lg border border-gray-200 bg-white p-3 shadow-sm"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-indigo-700">{place || 'Unknown place'}</span>
                    {date && <span className="text-xs text-gray-400">{date}</span>}
                  </div>
                  <p className="mt-1.5 line-clamp-2 text-sm font-medium text-gray-800">
                    {m.event_title || 'Untitled meeting'}
                  </p>
                  <blockquote className="mt-2 line-clamp-4 border-l-2 border-amber-300 pl-2 text-xs italic leading-relaxed text-gray-600">
                    “{highlightSnippet(m.evidence ?? '')}”
                  </blockquote>
                  {watchHref && (
                    <a
                      href={watchHref}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 self-start text-xs font-semibold text-indigo-600 hover:underline"
                    >
                      {m.jump_url && m.start_seconds != null ? `▶ Watch at ${clock(m.start_seconds)}` : '▶ Watch the meeting'}
                    </a>
                  )}
                </div>
              )
            })}
          </div>
          <div className="mt-3 flex items-center gap-3 text-sm">
            <span className="text-gray-500">
              Showing {meetings.length.toLocaleString()} of {total.toLocaleString()}
            </span>
            {hasNextPage && (
              <button
                type="button"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className="font-medium text-indigo-600 hover:underline disabled:text-gray-400"
              >
                {isFetchingNextPage ? 'Loading…' : 'Show more meetings'}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// Compact money line + per-quarter instance bars over the real trend points.
function Trend({ points }: { points: QuestionTrendPoint[] }) {
  const w = 560
  const h = 70
  const pad = 4
  const mMax = Math.max(...points.map((p) => p.money), 1) * 1.15
  const px = (i: number) => pad + (points.length <= 1 ? 0 : (i / (points.length - 1)) * (w - pad * 2))
  const py = (v: number) => h - pad - (v / mMax) * (h - pad * 2)
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${px(i).toFixed(1)},${py(p.money).toFixed(1)}`).join('')
  const maxInst = Math.max(...points.map((p) => p.instances), 1)
  const anyMoney = points.some((p) => p.money > 0)

  return (
    <div>
      {anyMoney ? (
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
          <path d={path} fill="none" stroke={SPEND_COLOR} strokeWidth="2" strokeLinejoin="round" />
        </svg>
      ) : (
        <div className="py-1 text-[11px] text-gray-400">
          No dollar impact recorded for this question (e.g. bills, or non-financial votes).
        </div>
      )}
      <div className="mt-1 flex h-6 items-end gap-[2px]">
        {points.map((p) => (
          <div
            key={p.quarter_start}
            className="flex-1 rounded-t-sm"
            style={{ height: `${Math.max(8, (p.instances / maxInst) * 100)}%`, background: TALK_COLOR, opacity: 0.55 }}
            title={`${quarterLabel(p.quarter_start)}: came up ${p.instances}×${p.money > 0 ? `, ${fmtMoney(p.money)}` : ''}`}
          />
        ))}
      </div>
      <div className="mt-0.5 flex justify-between text-[9px] text-gray-400">
        <span>{quarterLabel(points[0].quarter_start)}</span>
        <span>amber bars: how often it came up</span>
        <span>{quarterLabel(points[points.length - 1].quarter_start)}</span>
      </div>
    </div>
  )
}
