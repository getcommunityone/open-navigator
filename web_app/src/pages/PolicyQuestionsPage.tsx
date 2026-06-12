import { Fragment, useMemo, useState } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Dialog, Transition } from '@headlessui/react'
import {
  ArrowLeftIcon,
  MagnifyingGlassIcon,
  AdjustmentsHorizontalIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import {
  fetchPolicyQuestions,
  fetchPolicyQuestion,
  type PolicyQuestionSummary,
  type PolicyQuestionDetail,
  type QuestionTrendPoint,
} from '../api/policyQuestions'
import DecisionCardList from '../components/DecisionCardList'

// ────────────────────────────────────────────────────────────────────────────
// Questions That Keep Coming Up — restyled to match Browse Topics / Causes:
// a row of question pills scopes a DecisionCardList (the shared StoryCard grid,
// with its search bar + advanced filters) shown immediately at the top — no
// click-into-a-separate-view. Picking a question also surfaces a compact detail
// panel with its REAL stats (approval, money & talk, arguments, trend).
//
// EVERY figure is REAL (CLAUDE.md: No Fabricated Data):
//   • approval, theme, instances        → /api/policy-question (rollup mart)
//   • Money & Talk bars + tags          → money_total / money_share / talk_share
//   • "by quarter" trend                → /api/policy-question/{id}.trend
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

const approvalRate = (q: PolicyQuestionSummary) =>
  q.jurisdictions_total > 0 ? (q.jurisdictions_approved / q.jurisdictions_total) * 100 : null

export default function PolicyQuestionsPage() {
  const navigate = useNavigate()
  const routerLocation = useLocation()
  // Place filter carried over from the homepage (e.g. ?state=GA&city=Atlanta) —
  // passed straight through to the scoped MeetingCardList, like Browse Topics.
  const [searchParams] = useSearchParams()
  const stateCode = (searchParams.get('state') || '').trim().toUpperCase() || undefined
  const cityName = (searchParams.get('city') || '').trim() || undefined

  // Picking a question SCOPES the meeting cards shown below — it no longer drills
  // into a separate accordion view. The cards stay at the top the whole time.
  const [selectedQuestion, setSelectedQuestion] = useState<PolicyQuestionSummary | null>(null)
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

  const pickQuestion = (q: PolicyQuestionSummary | null) => {
    setSelectedQuestion(q)
    setFlyoutOpen(false)
  }

  const listTitle = selectedQuestion
    ? 'Decisions on this question'
    : `Most contested decisions${stateCode ? ` · ${stateCode}` : ''}`

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
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h1 className="text-3xl font-bold text-gray-900">
            Questions That Keep Coming Up{stateCode ? ` · ${stateCode}` : ''}
          </h1>

          {/* Top questions inline — pick one to scope the meeting cards below. The
              rest of the catalog + keyword search live in the "More questions" flyout. */}
          {isError ? (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              Couldn&apos;t load questions.{' '}
              {(error as { message?: string } | undefined)?.message ?? 'Please try again.'}
            </div>
          ) : (
            <div className="mt-4 flex flex-wrap items-center gap-2">
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
                      onClick={() => pickQuestion(q)}
                      title={q.canonical_text ?? undefined}
                      className={chipClass(on)}
                    >
                      {pillLabel(q)}
                    </button>
                  )
                })
              )}
              {!isLoading && questions.length > 0 && (
                <button
                  type="button"
                  onClick={() => setFlyoutOpen(true)}
                  className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border border-dashed border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:border-indigo-400 hover:text-indigo-700"
                >
                  <AdjustmentsHorizontalIcon className="h-4 w-4" />
                  More questions
                </button>
              )}
            </div>
          )}
        </div>

        {/* Selected-question detail panel — REAL stats only. Hidden on "All". */}
        {selectedQuestion && <QuestionDetailPanel question={selectedQuestion} />}

        {/* Decision cards — the shared Contested StoryCard grid with YouTube
            previews, search bar, and advanced filters (matching Browse Topics).
            Picking a question scopes this list; the `key` remounts it so the new
            scope applies cleanly. */}
        <DecisionCardList
          key={selectedQuestion?.question_id ?? 'all-questions'}
          questionId={selectedQuestion?.question_id}
          state={stateCode}
          city={cityName}
          title={listTitle}
          showAdvancedFilters
        />
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
                        const r = approvalRate(q)
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
                              {r != null && <>{r.toFixed(0)}% approved · </>}
                              {q.instances_total} {q.instances_total === 1 ? 'instance' : 'instances'}
                              {q.primary_theme && q.primary_theme !== '__unthemed__' && <> · {q.primary_theme}</>}
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

// ── Selected-question detail panel: approval + money & talk + arguments + trend ──
// Reuses the summary's already-loaded shares for the bars, and lazily fetches
// the full detail (arguments, trend, recent instances). All REAL data.
function QuestionDetailPanel({ question }: { question: PolicyQuestionSummary }) {
  const { data: detail, isLoading } = useQuery<PolicyQuestionDetail>({
    queryKey: ['policy-question-detail', question.question_id],
    queryFn: () => fetchPolicyQuestion(question.question_id),
    staleTime: 5 * 60 * 1000,
  })

  const r = approvalRate(question)
  const mShare = question.money_share ?? 0
  const tShare = question.talk_share ?? 0
  const maxS = Math.max(mShare, tShare, 1)

  const pros = detail?.arguments.filter((a) => a.stance === 'pro') ?? []
  const cons = detail?.arguments.filter((a) => a.stance === 'con') ?? []

  return (
    <div className="mb-6 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold leading-snug text-gray-900">
        {question.canonical_text || 'Untitled question'}
      </h2>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gray-500">
        {r != null && (
          <span className="font-semibold text-teal-700">
            {question.jurisdictions_approved}/{question.jurisdictions_total} approved ({r.toFixed(0)}%)
          </span>
        )}
        {question.primary_theme && question.primary_theme !== '__unthemed__' && (
          <span className="uppercase tracking-wide text-gray-500">{question.primary_theme}</span>
        )}
        <span className="text-gray-300">·</span>
        <span>
          {question.instances_total} {question.instances_total === 1 ? 'instance' : 'instances'}
        </span>
      </div>

      {/* Money & talk — REAL shares of all decisions */}
      <div className="mt-4 rounded-md border border-gray-100 bg-gray-50 px-3 py-2.5">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <span className="text-[10px] uppercase tracking-widest text-gray-500">Money &amp; talk · share of all decisions</span>
          <span className="text-[11px] text-gray-500">
            {fmtMoney(question.money_total ?? 0)} moved · came up {question.instances_total}×
          </span>
        </div>
        <div className="grid items-center gap-x-2 gap-y-1" style={{ gridTemplateColumns: '3.5rem minmax(0,1fr) 2.8rem' }}>
          <span className="text-[10px] uppercase tracking-wider text-gray-500">Money</span>
          <div className="h-3 overflow-hidden rounded-sm bg-gray-200/60">
            <div className="h-full rounded-sm" style={{ width: `${Math.max(1.5, (mShare / maxS) * 100)}%`, background: SPEND_COLOR }} />
          </div>
          <span className="text-right text-xs text-gray-500">{mShare.toFixed(1)}%</span>
          <span className="text-[10px] uppercase tracking-wider text-gray-500">Talk</span>
          <div className="h-3 overflow-hidden rounded-sm bg-gray-200/60">
            <div className="h-full rounded-sm" style={{ width: `${Math.max(1.5, (tShare / maxS) * 100)}%`, background: TALK_COLOR }} />
          </div>
          <span className="text-right text-xs text-gray-500">{tShare.toFixed(1)}%</span>
        </div>
      </div>

      {isLoading ? (
        <div className="my-4 h-5 w-5 animate-spin rounded-full border-b-2 border-indigo-600" />
      ) : (
        detail && (
          <>
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

            {/* By quarter — real money line + instance bars */}
            {detail.trend.length > 0 && (
              <div className="mt-4 rounded-md border border-gray-100 bg-gray-50 px-3 py-2.5">
                <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[10px] uppercase tracking-widest text-gray-500">By quarter</span>
                  <span className="flex items-center gap-3 text-[11px] text-gray-500">
                    <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: SPEND_COLOR }} />money</span>
                    <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: TALK_COLOR }} />how often</span>
                  </span>
                </div>
                <Trend points={detail.trend} />
              </div>
            )}

            {/* Recent instances — real decisions/bills that instantiate the question */}
            {detail.sample_instances.length > 0 && (
              <div className="mt-4">
                <div className="mb-1.5 text-[10px] uppercase tracking-widest text-gray-500">Recent instances</div>
                {detail.sample_instances.slice(0, 6).map((ex) => (
                  <div key={ex.instance_id} className="flex items-start justify-between gap-3 py-1.5 text-sm">
                    <div className="min-w-0">
                      <span className="text-gray-700">
                        {[ex.city || ex.jurisdiction_name, ex.state_code].filter(Boolean).join(', ') || 'Unknown jurisdiction'}
                      </span>
                      {ex.occurred_at && (
                        <span className="ml-2 text-xs text-gray-400">
                          {new Date(ex.occurred_at).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}
                        </span>
                      )}
                    </div>
                    {ex.outcome_normalized && (
                      <span
                        className="shrink-0 text-xs capitalize"
                        style={{ color: ex.outcome_normalized === 'approved' || ex.outcome_normalized === 'enacted' ? SPEND_COLOR : '#78716c' }}
                      >
                        {ex.outcome_normalized}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )
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
